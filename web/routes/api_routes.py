"""
API Routes Blueprint
RESTful endpoints for data fetching
"""

import os
import threading
import time
import urllib.request
from flask import Blueprint, request, jsonify, Response
from services import StockAnalysisService
from utils.cache import TTLCache


market_overview_cache = TTLCache(default_ttl=120)
# Logo bytes cached for 24 hours — logos rarely change
_logo_cache: TTLCache = TTLCache(default_ttl=86400)
_market_refresh_started = False
_market_refresh_lock = threading.Lock()


def _normalize_cache_seconds(cache_seconds: int) -> int:
    if cache_seconds < 15:
        return 15
    if cache_seconds > 600:
        return 600
    return cache_seconds


def _market_overview_cache_key(cache_seconds: int) -> str:
    return f"market_overview:{cache_seconds}"


def _make_logo_url(symbol: str) -> str:
    """Return a server-proxied logo URL so the browser loads from localhost."""
    return f"/api/logo/{symbol}"


def _serialize_item(item) -> dict:
    return {
        'symbol': item.symbol,
        'name': item.name,
        'price': item.price,
        'change_percent': item.change_percent,
        'change_absolute': item.change_absolute,
        'market_cap': item.market_cap,
        'volume': item.volume,
        'week_52_high': item.week_52_high,
        'week_52_low': item.week_52_low,
        'logo_url': _make_logo_url(item.symbol),
    }


def _serialize_market_overview(overview) -> dict:
    return {
        'movers':      [_serialize_item(i) for i in overview.movers],
        'gainers':     [_serialize_item(i) for i in overview.gainers],
        'losers':      [_serialize_item(i) for i in overview.losers],
        'most_active': [_serialize_item(i) for i in overview.most_active],
        'indices':     [_serialize_item(i) for i in overview.indices],
        'timestamp':   overview.timestamp.isoformat() + 'Z',  # Add 'Z' to indicate UTC
    }


def warm_market_overview_cache(stock_service: StockAnalysisService, cache_seconds: int = 120) -> bool:
    """Pre-fetch market overview and store it in the API cache."""
    normalized_cache_seconds = _normalize_cache_seconds(cache_seconds)
    cache_key = _market_overview_cache_key(normalized_cache_seconds)

    try:
        overview = stock_service.get_market_overview()
        payload = _serialize_market_overview(overview)
        # Only set cache if payload contains at least one non-empty section
        has_content = any(
            payload.get(k) for k in ('movers', 'gainers', 'losers', 'most_active', 'indices')
        )
        if has_content:
            market_overview_cache.set(cache_key, payload, ttl=normalized_cache_seconds)
            return True
        # Don't overwrite an existing cache with an empty payload
        existing = market_overview_cache.get(cache_key)
        if existing is not None:
            return True
        # No existing cache and new payload empty -> indicate failure
        print("[WARN] Market overview warm-up returned empty payload")
        return False
    except Exception as exc:
        print(f"[WARN] Market overview warm-up failed: {exc}")
        return False


def start_market_overview_refresh_worker(
    stock_service: StockAnalysisService,
    cache_seconds: int = 120,
    refresh_interval_seconds: int = 90,
) -> bool:
    """Start a daemon worker that refreshes market overview cache periodically."""
    global _market_refresh_started

    normalized_cache_seconds = _normalize_cache_seconds(cache_seconds)
    refresh_interval_seconds = max(15, int(refresh_interval_seconds))

    with _market_refresh_lock:
        if _market_refresh_started:
            return False
        _market_refresh_started = True

    def _refresh_loop() -> None:
        warm_market_overview_cache(stock_service, normalized_cache_seconds)
        while True:
            time.sleep(refresh_interval_seconds)
            warm_market_overview_cache(stock_service, normalized_cache_seconds)

    threading.Thread(
        target=_refresh_loop,
        name="market-overview-refresh",
        daemon=True,
    ).start()
    return True


def init_api_routes(stock_service: StockAnalysisService):
    """
    Initialize API routes with injected dependencies

    Args:
        stock_service: StockAnalysisService instance
    """
    api_bp = Blueprint('api', __name__, url_prefix='/api')

    @api_bp.route('/price-history', methods=['GET'])
    def get_price_history():
        """Fetch price history for chart rendering"""
        ticker = request.args.get('ticker', '')
        period = request.args.get('period', '1mo')

        if not ticker:
            return jsonify({'error': 'Ticker is required'}), 400

        try:
            price_data = stock_service.repository.get_price_history(ticker, period)
            return jsonify(price_data)
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @api_bp.route('/logo/<symbol>', methods=['GET'])
    def get_logo(symbol: str):
        """Proxy company logo from Finnhub, cached server-side for 24 hours."""
        # Basic validation — only uppercase letters/digits, 1-6 chars
        import re
        if not re.match(r'^[A-Z0-9]{1,6}$', symbol.upper()):
            return '', 404
        symbol = symbol.upper()

        cached = _logo_cache.get(symbol)
        if cached is not None:
            data, content_type = cached
            resp = Response(data, status=200, mimetype=content_type)
            resp.headers['Cache-Control'] = 'public, max-age=86400'
            return resp

        import requests
        token = os.environ.get('FINNHUB_API_KEY', '')
        profile_url = f"https://finnhub.io/api/v1/stock/profile2?symbol={symbol}&token={token}"
        try:
            resp_profile = requests.get(profile_url, timeout=5)
            if resp_profile.status_code != 200:
                return '', 404
            profile = resp_profile.json()
            logo_url = profile.get('logo')
            if not logo_url:
                return '', 404
            # Now fetch the logo image itself
            img_resp = requests.get(logo_url, timeout=5)
            if img_resp.status_code != 200 or not img_resp.content:
                return '', 404
            ct = img_resp.headers.get('Content-Type', 'image/png')
            if not ct.startswith('image/') and not ct.startswith('application/octet'):
                return '', 404
            if 'octet' in ct:
                ct = 'image/png'
            _logo_cache.set(symbol, (img_resp.content, ct))
            resp = Response(img_resp.content, status=200, mimetype=ct)
            resp.headers['Cache-Control'] = 'public, max-age=86400'
            return resp
        except Exception:
            return '', 404

    @api_bp.route('/market-overview', methods=['GET'])
    def get_market_overview():
        """Fetch comprehensive market overview (movers, gainers, losers, active, indices)"""
        try:
            cache_seconds = _normalize_cache_seconds(
                request.args.get('cache_seconds', default=120, type=int)
            )

            cache_key = _market_overview_cache_key(cache_seconds)
            cached = market_overview_cache.get(cache_key)
            if cached is not None:
                return jsonify(cached)

            warm_market_overview_cache(stock_service, cache_seconds)
            refreshed = market_overview_cache.get(cache_key)
            if refreshed is not None:
                return jsonify(refreshed)

            return jsonify({'error': 'Unable to fetch market overview right now'}), 503
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @api_bp.route('/health', methods=['GET'])
    def health_check():
        return jsonify({'status': 'ok'}), 200

    @api_bp.route('/stock-info', methods=['GET'])
    def get_stock_info():
        """Return lightweight stock info (quote + ownership + optional extras)."""
        try:
            symbol = request.args.get('symbol', '')
            if not symbol:
                return jsonify({'error': 'symbol is required'}), 400

            info = stock_service.get_stock_info(symbol.upper())
            return jsonify(info)
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    return api_bp
