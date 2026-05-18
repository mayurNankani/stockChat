"""
Stock Data Repository
Data access layer for stock information from external sources
"""

import sys
import os
from datetime import date, datetime
from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from adapters.company_lookup.yahoo_company_lookup_adapter import YahooCompanyLookupAdapter
from adapters.market_data.yahoo_finance_adapter import YahooFinanceAdapter
from src.agent_improved import StockAnalysisAgentImproved as StockAnalysisAgent
from adapters.news.finnhub_adapter import FinnhubNewsAdapter

# Ensure web/ directory is on sys.path so sibling packages (utils) can be imported
_web_dir = os.path.abspath(os.path.dirname(__file__) + '/..')
if _web_dir not in sys.path:
    sys.path.insert(0, _web_dir)
from utils.cache import quote_cache, news_cache, history_cache


class IStockRepository(ABC):
    """Interface for stock data access"""
    
    @abstractmethod
    def search_company(self, query: str) -> Optional[Dict[str, Any]]:
        """Search for company by name or ticker"""
        pass
    
    @abstractmethod
    def get_quote(self, ticker: str) -> Dict[str, Any]:
        """Get current stock quote"""
        pass
    
    @abstractmethod
    def get_recommendations(self, ticker: str) -> Dict[str, Any]:
        """Get stock recommendations"""
        pass
    
    @abstractmethod
    def get_news(self, ticker: str) -> Dict[str, Any]:
        """Get news articles"""
        pass
    
    @abstractmethod
    def get_price_history(self, ticker: str, period: str) -> Dict[str, List]:
        """Get historical price data"""
        pass
    
    @abstractmethod
    def get_earnings(self, ticker: str) -> Dict[str, Any]:
        """Get earnings data"""
        pass


class StockRepository(IStockRepository):
    """
    Concrete implementation of stock data repository
    Aggregates data from multiple sources
    """
    
    def __init__(self):
        self.company_lookup = YahooCompanyLookupAdapter()
        self.market_data = YahooFinanceAdapter()
        self.analysis_agent = StockAnalysisAgent()
        self.news_adapter = FinnhubNewsAdapter()
        # New adapters
        from adapters.market_data.yahoo_ownership_adapter import YahooOwnershipAdapter
        from adapters.market_data.yahoo_insider_adapter import YahooInsiderAdapter
        from adapters.market_data.yahoo_peer_adapter import YahooPeerAdapter
        from adapters.market_data.finnhub_insider_adapter import FinnhubInsiderAdapter
        from adapters.market_data.finnhub_dividend_adapter import FinnhubDividendAdapter
        self.ownership_adapter = YahooOwnershipAdapter()
        self.insider_adapter = YahooInsiderAdapter()
        self.peer_adapter = YahooPeerAdapter()
        self.fallback_insider_adapter = FinnhubInsiderAdapter()
        self.fallback_dividend_adapter = FinnhubDividendAdapter()
        # end of __init__ assignments
    
    def search_company(self, query: str) -> Optional[Dict[str, Any]]:
        """Search for company and return best match (transitional dict)."""
        print(f"[DEBUG] Repository search_company called with: '{query}'")
        identities = self.company_lookup.search(query, limit=5)
        if not identities:
            print("[DEBUG] No identities found")
            return None
        top = identities[0]
        result = {
            'symbol': top.symbol,
            'long_name': top.long_name,
            'short_name': top.short_name,
        }
        print(f"[DEBUG] Returning match: {result}")
        return result
    
    def validate_ticker(self, ticker: str) -> bool:
        """Validate ticker by ensuring quote has a price."""
        quote = self.market_data.get_quote(ticker)
        return quote.price is not None
    
    def get_quote(self, ticker: str) -> Dict[str, Any]:
        """Get current stock quote (transitional wrapper, cached)."""
        key = f"quote:{ticker}"
        cached = quote_cache.get(key)
        if cached is not None:
            return cached
        quote = self.market_data.get_quote(ticker)
        result = {
            "status": "ok" if quote.price is not None else "error",
            "data": {
                "symbol": quote.symbol,
                "price": quote.price,
                "currency": quote.currency,
                "name": quote.name
            },
            "error": None if quote.price is not None else "Quote unavailable"
        }
        if quote.price is not None:
            quote_cache.set(key, result)
        return result
    
    def get_recommendations(self, ticker: str) -> Dict[str, Any]:
        """Get stock analysis recommendations"""
        return self.analysis_agent.get_recommendation(ticker)
    
    def get_news(self, ticker: str) -> Dict[str, Any]:
        """Get news articles for ticker (adapter-backed, cached)."""
        key = f"news:{ticker}"
        cached = news_cache.get(key)
        if cached is not None:
            return cached
        articles = self.news_adapter.get_company_news(ticker, limit=15)
        # Transitional shape preserving existing expectations
        serialized = []
        for a in articles:
            serialized.append({
                "headline": a.headline,
                "summary": a.summary,
                "url": a.url,
                "source": a.source or "Finnhub",
                "datetime": a.published_at.strftime('%Y-%m-%d %H:%M'),
            })
        result = {"news": serialized}
        news_cache.set(key, result)
        return result
    
    def get_price_history(self, ticker: str, period: str = '1mo') -> Dict[str, List]:
        """Fetch historical price data (simplified adapter-backed, cached)."""
        key = f"history:{ticker}:{period}"
        cached = history_cache.get(key)
        if cached is not None:
            return cached
        history = self.market_data.get_price_history(ticker, period)
        # Include time component for intraday periods
        if period in ('1d', '5d'):
            dates = [c.timestamp.strftime('%Y-%m-%d %H:%M') for c in history.candles]
        else:
            dates = [c.timestamp.strftime('%Y-%m-%d') for c in history.candles]
        prices = [round(c.close, 2) if c.close is not None else None for c in history.candles]
        result = {"dates": dates, "prices": prices}
        history_cache.set(key, result)
        return result
    
    def get_earnings(self, ticker: str) -> Dict[str, Any]:
        """Get earnings data from yfinance in a stable response shape."""
        import yfinance as yf

        def _normalize_calendar_value(value: Any):
            """Convert yfinance calendar values into JSON-friendly, readable primitives."""
            if isinstance(value, (date, datetime)):
                return value.isoformat()
            if isinstance(value, list):
                normalized = [_normalize_calendar_value(v) for v in value if v is not None]
                if not normalized:
                    return None
                if len(normalized) == 1:
                    return normalized[0]
                return normalized
            return str(value) if value is not None else None

        symbol = ticker.upper()
        try:
            stock = yf.Ticker(symbol)

            next_earnings: Optional[Dict[str, Any]] = None
            try:
                calendar = stock.calendar
                if isinstance(calendar, dict):
                    next_earnings = {
                        key: _normalize_calendar_value(value)
                        for key, value in calendar.items()
                        if value is not None
                    }
                elif isinstance(calendar, list) and calendar:
                    first = calendar[0]
                    if isinstance(first, dict):
                        next_earnings = {
                            key: _normalize_calendar_value(value)
                            for key, value in first.items()
                            if value is not None
                        }
                elif calendar is not None and not calendar.empty:
                    first = calendar.iloc[0]
                    next_earnings = {
                        col: _normalize_calendar_value(first[col])
                        for col in calendar.columns
                    }
            except Exception:
                next_earnings = None

            # Enrich with timestamp hints from info when available.
            # yfinance often exposes call timing as unix timestamps in info,
            # while calendar may only include date/session text.
            try:
                info = stock.info or {}
                if next_earnings is None:
                    next_earnings = {}
                for key in (
                    "earningsTimestamp",
                    "earningsCallTimestampStart",
                    "earningsCallTimestampEnd",
                    "isEarningsDateEstimate",
                ):
                    value = info.get(key)
                    if value is not None and key not in next_earnings:
                        next_earnings[key] = _normalize_calendar_value(value)
                if not next_earnings:
                    next_earnings = None
            except Exception:
                pass

            earnings_history: List[Dict[str, Any]] = []
            try:
                earnings_dates = stock.earnings_dates
                if earnings_dates is not None and not earnings_dates.empty:
                    for idx, row in earnings_dates.head(10).iterrows():
                        record = {k: (None if row[k] is None else str(row[k])) for k in earnings_dates.columns}
                        record["date"] = str(idx)
                        earnings_history.append(record)
            except Exception:
                earnings_history = []

            return {
                "status": "ok",
                "data": {
                    "symbol": symbol,
                    "next_earnings": next_earnings,
                    "earnings_history": earnings_history,
                },
                "error": None,
            }
        except Exception as e:
            return {
                "status": "error",
                "data": {
                    "symbol": symbol,
                    "next_earnings": None,
                    "earnings_history": [],
                },
                "error": str(e),
            }
    
    def get_stock_info(self, ticker: str) -> Dict[str, Any]:
        """Get comprehensive stock info from yfinance"""
        import yfinance as yf
        
        try:
            stock = yf.Ticker(ticker)
            return stock.info
        except Exception as e:
            print(f"Error fetching info for {ticker}: {e}")
            return {"error": str(e)}

    # -------------------------
    # New data access helpers
    # -------------------------
    def get_ownership_breakdown(self, ticker: str) -> dict:
        """Get ownership breakdown (Yahoo primary)."""
        try:
            data = self.ownership_adapter.get_ownership_breakdown(ticker)
            # Normalize to ensure callers always receive keys for rendering.
            if not isinstance(data, dict):
                return {'institutional': None, 'retail': None, 'insider': None}
            return {
                'institutional': data.get('institutional'),
                'retail': data.get('retail'),
                'insider': data.get('insider'),
            }
        except Exception:
            return {"institutional": None, "retail": None, "insider": None}

    def get_insider_transactions(self, ticker: str) -> list:
        """Get insider transactions (Yahoo primary, Finnhub fallback)."""
        try:
            data = self.insider_adapter.get_insider_transactions(ticker)
            if data:
                return data
        except Exception:
            pass
        # Fallback
        try:
            return self.fallback_insider_adapter.get_insider_transactions(ticker)
        except Exception:
            return []

    def get_peer_comparison(self, ticker: str) -> list:
        """Get peer comparison (Yahoo)."""
        try:
            return self.peer_adapter.get_peer_comparison(ticker)
        except Exception:
            return []

    def get_dividend_history(self, ticker: str) -> list:
        """Get dividend history (Yahoo via market_data, Finnhub fallback)."""
        try:
            # Try YahooFinanceAdapter if it supports dividend history
            if hasattr(self.market_data, 'get_dividend_history'):
                data = self.market_data.get_dividend_history(ticker)
                if data:
                    return data
        except Exception:
            pass
        # Fallback
        try:
            return self.fallback_dividend_adapter.get_dividend_history(ticker)
        except Exception:
            return []
