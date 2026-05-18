"""Yahoo Finance market screener adapter implementation."""
from __future__ import annotations
from typing import List
from datetime import datetime
import logging
import yfinance as yf
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from core.models.market import MarketListItem, MarketOverview
from .screener_interface import MarketScreenerAdapter


logger = logging.getLogger(__name__)


class YahooFinanceScreenerAdapter(MarketScreenerAdapter):
    """Concrete adapter using yfinance for market screener data."""

    # A liquid universe so we can compute movers/active reliably without Yahoo screener APIs.
    UNIVERSE_SYMBOLS = [
        "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "BRK-B", "AVGO", "TSM",
        "SPY", "QQQ", "AMD", "JPM", "NFLX",
    ]

    TOP_MARKET_CAP_SYMBOLS = [
        "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "BRK-B", "AVGO", "TSM",
    ]
    
    def __init__(self):
        self.logger = logger
        self.request_timeout = 20  # seconds per request
    
    def get_market_overview(self) -> MarketOverview:
        """
        Fetch comprehensive market overview using yfinance screeners.
        Uses parallel execution with timeouts to prevent hanging.
        
        Returns:
            MarketOverview with all five sections (fails open on individual failures).
        """
        try:
            with ThreadPoolExecutor(max_workers=2) as executor:
                combined_symbols = list(dict.fromkeys(self.UNIVERSE_SYMBOLS + self.TOP_MARKET_CAP_SYMBOLS))
                futures = {
                    'combined': executor.submit(self._fetch_snapshots, combined_symbols),
                    'indices': executor.submit(self._get_indices),
                }
                
                raw_results = {}
                for key, future in futures.items():
                    try:
                        raw_results[key] = future.result(timeout=self.request_timeout)
                    except (FuturesTimeoutError, Exception) as e:
                        self.logger.warning(f"Timeout/error fetching {key}: {e}")
                        raw_results[key] = []

            combined = raw_results.get('combined', [])
            indices = raw_results.get('indices', [])
            universe = [x for x in combined if x.symbol in self.UNIVERSE_SYMBOLS]
            market_caps = [x for x in combined if x.symbol in self.TOP_MARKET_CAP_SYMBOLS]

            movers = sorted(universe, key=lambda x: abs(x.change_percent), reverse=True)[:5]
            gainers = sorted(universe, key=lambda x: x.change_percent or 0, reverse=True)[:5]
            losers = sorted(universe, key=lambda x: x.change_percent)[:5]
            most_active = sorted(universe, key=lambda x: x.volume or 0, reverse=True)[:5]
            
            return MarketOverview(
                movers=movers,
                gainers=gainers,
                losers=losers,
                most_active=most_active,
                indices=indices,
                timestamp=datetime.utcnow()
            )
        except Exception as e:
            self.logger.error(f"Error fetching market overview: {e}")
            # Return empty overview on catastrophic failure
            return MarketOverview(
                movers=[],
                gainers=[],
                losers=[],
                most_active=[],
                indices=[],
                timestamp=datetime.utcnow()
            )
    
    def _fetch_snapshots(self, symbols: List[str]) -> List[MarketListItem]:
        """Fetch quote-like snapshot data for a list of symbols.

        First attempt: use `yfinance.Tickers` to batch-fetch lightweight info
        objects where available. This reduces HTTP overhead and is usually
        faster. If batching fails for any reason, fall back to the parallel
        per-symbol fetch implemented below.
        """
        items: List[MarketListItem] = []

        def _build_item_from_ticker(symbol: str, ticker) -> MarketListItem | None:
            try:
                price = None
                prev_close = None
                volume = None
                market_cap = None
                week_52_high = None
                week_52_low = None
                name = symbol

                try:
                    fi = getattr(ticker, 'fast_info', {}) or {}

                    def _first_available(*keys):
                        for key in keys:
                            try:
                                value = fi.get(key)
                            except Exception:
                                value = None
                            if value is not None:
                                return value
                        return None

                    price = _first_available('last_price', 'lastPrice', 'regularMarketPrice')
                    prev_close = _first_available('previous_close', 'previousClose', 'regularMarketPreviousClose')
                    volume = _first_available('last_volume', 'lastVolume', 'volume', 'three_month_average_volume', 'threeMonthAverageVolume')
                    market_cap = _first_available('market_cap', 'marketCap')
                    week_52_high = _first_available('year_high', 'yearHigh', 'fifty_two_week_high', 'fiftyTwoWeekHigh')
                    week_52_low = _first_available('year_low', 'yearLow', 'fifty_two_week_low', 'fiftyTwoWeekLow')
                except Exception:
                    pass

                try:
                    info = getattr(ticker, 'info', {}) or {}
                    name = (
                        info.get('shortName')
                        or info.get('longName')
                        or info.get('displayName')
                        or info.get('name')
                        or name
                    )
                except Exception:
                    pass

                if price is None:
                    try:
                        hist = getattr(ticker, 'history')(period="2d", interval="1d")
                        if hist is not None and not hist.empty:
                            last_close = hist['Close'].iloc[-1]
                            price = float(last_close) if last_close is not None else None
                            if len(hist) > 1:
                                prev = hist['Close'].iloc[-2]
                                prev_close = float(prev) if prev is not None else prev_close
                    except Exception:
                        pass

                if price is None:
                    return None

                change_pct = 0.0
                if prev_close:
                    change_pct = ((float(price) - float(prev_close)) / float(prev_close)) * 100

                return MarketListItem(
                    symbol=symbol,
                    name=name,
                    price=float(price),
                    currency="USD",
                    change_percent=float(change_pct),
                    change_absolute=(float(price) - float(prev_close)) if prev_close else None,
                    volume=float(volume) if volume is not None else None,
                    market_cap=float(market_cap) if market_cap is not None else None,
                    week_52_high=float(week_52_high) if week_52_high is not None else None,
                    week_52_low=float(week_52_low) if week_52_low is not None else None,
                )
            except Exception as e:
                self.logger.warning(f"Error building item for {symbol}: {e}")
                return None

        # Try batching via yfinance.Tickers
        try:
            # yfinance accepts space-separated tickers
            batch = yf.Tickers(' '.join(symbols))
            # `batch.tickers` is a dict-like of ticker objects on most versions
            batch_map = getattr(batch, 'tickers', None)
            for sym in symbols:
                try:
                    ticker_obj = None
                    if batch_map and sym in batch_map:
                        ticker_obj = batch_map[sym]
                    else:
                        # fallback to attribute access (some yfinance builds)
                        ticker_obj = getattr(batch, sym, None)
                    if ticker_obj is None:
                        ticker_obj = yf.Ticker(sym)
                    itm = _build_item_from_ticker(sym, ticker_obj)
                    if itm is not None:
                        items.append(itm)
                except Exception as e:
                    self.logger.warning(f"Batch fetch error for {sym}: {e}")
            # If batching produced any items, return them
            if items:
                return items
        except Exception as e:
            self.logger.info(f"Batching via yfinance.Tickers failed, falling back: {e}")

        # Fallback: parallel per-symbol fetch
        def _fetch_one(symbol: str) -> MarketListItem | None:
            try:
                ticker = yf.Ticker(symbol)

                price = None
                prev_close = None
                volume = None
                market_cap = None
                week_52_high = None
                week_52_low = None
                name = symbol

                try:
                    fi = ticker.fast_info

                    def _first_available(*keys):
                        for key in keys:
                            try:
                                value = fi.get(key)
                            except Exception:
                                value = None
                            if value is not None:
                                return value
                        return None

                    price = _first_available('last_price', 'lastPrice', 'regularMarketPrice')
                    prev_close = _first_available('previous_close', 'previousClose', 'regularMarketPreviousClose')
                    volume = _first_available('last_volume', 'lastVolume', 'volume', 'three_month_average_volume', 'threeMonthAverageVolume')
                    market_cap = _first_available('market_cap', 'marketCap')
                    week_52_high = _first_available('year_high', 'yearHigh', 'fifty_two_week_high', 'fiftyTwoWeekHigh')
                    week_52_low = _first_available('year_low', 'yearLow', 'fifty_two_week_low', 'fiftyTwoWeekLow')
                except Exception:
                    pass

                try:
                    info = ticker.info or {}
                    name = (
                        info.get('shortName')
                        or info.get('longName')
                        or info.get('displayName')
                        or info.get('name')
                        or name
                    )
                except Exception:
                    pass

                if price is None:
                    try:
                        hist = ticker.history(period="2d", interval="1d")
                        if hist is not None and not hist.empty:
                            last_close = hist['Close'].iloc[-1]
                            price = float(last_close) if last_close is not None else None
                            if len(hist) > 1:
                                prev = hist['Close'].iloc[-2]
                                prev_close = float(prev) if prev is not None else prev_close
                    except Exception:
                        pass

                if price is None:
                    return None

                change_pct = 0.0
                if prev_close:
                    change_pct = ((float(price) - float(prev_close)) / float(prev_close)) * 100

                return MarketListItem(
                    symbol=symbol,
                    name=name,
                    price=float(price),
                    currency="USD",
                    change_percent=float(change_pct),
                    change_absolute=(float(price) - float(prev_close)) if prev_close else None,
                    volume=float(volume) if volume is not None else None,
                    market_cap=float(market_cap) if market_cap is not None else None,
                    week_52_high=float(week_52_high) if week_52_high is not None else None,
                    week_52_low=float(week_52_low) if week_52_low is not None else None,
                )
            except Exception as e:
                self.logger.warning(f"Error fetching snapshot for {symbol}: {e}")
                return None

        per_symbol_timeout = min(8, max(2, int(self.request_timeout // 2)))
        with ThreadPoolExecutor(max_workers=min(8, len(symbols) or 1)) as executor:
            futures = {executor.submit(_fetch_one, s): s for s in symbols}
            for fut in futures:
                sym = futures[fut]
                try:
                    res = fut.result(timeout=per_symbol_timeout)
                    if res is not None:
                        items.append(res)
                except (FuturesTimeoutError, Exception) as e:
                    self.logger.warning(f"Timeout/error fetching snapshot for {sym}: {e}")
                    continue

        return items
    
    def _get_indices(self) -> List[MarketListItem]:
        """Fetch major market indices (faster than screeners)."""
        indices_symbols = ['^GSPC', '^IXIC', '^DJI', '^RUT']  # Reduced set for speed
        return self._fetch_snapshots(indices_symbols)

