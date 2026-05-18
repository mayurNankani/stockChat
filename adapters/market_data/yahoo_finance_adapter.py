"""Yahoo Finance market data adapter implementation.

Wraps yfinance to produce domain models without exposing library-specific
structures to the rest of the application.
"""
from __future__ import annotations
from typing import Optional, List
from datetime import datetime
import yfinance as yf
from core.models import StockQuote, PriceHistory, Candle
from .interface import MarketDataAdapter

class YahooFinanceAdapter(MarketDataAdapter):
    """Concrete adapter using yfinance for quotes and price history."""

    def get_quote(self, symbol: str) -> StockQuote:
        try:
            stock = yf.Ticker(symbol)
            # fast_info returns the live last price; fall back to info dict if unavailable
            try:
                price = stock.fast_info.last_price
            except Exception:
                price = None
            info = stock.info or {}
            if price is None:
                price = info.get("regularMarketPrice") or info.get("currentPrice")
            name = info.get("shortName") or info.get("longName") or symbol
            return StockQuote(symbol=symbol.upper(), price=price, currency=info.get("currency", "USD"), name=name)
        except Exception:
            return StockQuote(symbol=symbol.upper(), price=None, currency="USD", name=symbol.upper())

    def get_price_history(self, symbol: str, period: str = "1mo") -> PriceHistory:
        try:
            ticker = yf.Ticker(symbol)
            # Interval selection for granularity (restore intraday detail for short periods)
            interval_map = {
                '1d': '5m',
                '5d': '15m',
                '1mo': '1d',
                '3mo': '1d',
                '6mo': '1d',
                '1y': '1d'
            }
            interval = interval_map.get(period, '1d')
            # yfinance limits: intraday intervals require shorter periods; fall back if invalid
            try:
                hist = ticker.history(period=period, interval=interval)
                if hist is None or hist.empty:
                    # Fallback to default daily if granular request failed
                    hist = ticker.history(period=period)
            except Exception:
                hist = ticker.history(period=period)
            if hist is None or hist.empty:
                return PriceHistory(symbol=symbol.upper(), candles=[])
            candles: List[Candle] = []
            for idx, row in hist.iterrows():
                ts = idx.to_pydatetime() if hasattr(idx, "to_pydatetime") else datetime.fromtimestamp(idx)
                candles.append(
                    Candle(
                        timestamp=ts,
                        open=row.get("Open"),
                        high=row.get("High"),
                        low=row.get("Low"),
                        close=row.get("Close"),
                        volume=row.get("Volume"),
                    )
                )
            return PriceHistory(symbol=symbol.upper(), candles=candles)
        except Exception:
            return PriceHistory(symbol=symbol.upper(), candles=[])

    def get_dividend_history(self, symbol: str, years: int = 5) -> list:
        """Return recent dividend history using yfinance Ticker.dividends

        Returns list of dicts: [{'date': 'YYYY-MM-DD', 'amount': float}, ...]
        """
        try:
            ticker = yf.Ticker(symbol)
            divs = ticker.dividends
            if divs is None or divs.empty:
                return []
            out = []
            cutoff = datetime.utcnow().date().replace(year=datetime.utcnow().year - years)
            for idx, amt in divs.items():
                try:
                    d = idx.to_pydatetime().date() if hasattr(idx, 'to_pydatetime') else idx
                except Exception:
                    d = idx
                if isinstance(d, datetime):
                    d = d.date()
                if d < cutoff:
                    continue
                out.append({'date': d.isoformat(), 'amount': float(amt)})
            out.sort(key=lambda x: x['date'], reverse=True)
            return out
        except Exception:
            return []
