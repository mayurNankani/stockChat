"""Agent Tools
Defines the tools available to the stock analysis agent, including
their JSON schemas (for Ollama tool calling) and executor functions.
"""
from __future__ import annotations
import json
from typing import Any, Dict, List, Tuple
from repositories.stock_repository import IStockRepository
from src.tools.web_search import ddg_search
from services.tool_schemas import TOOL_SCHEMAS


# ---------------------------------------------------------------------------
# Tool executors — called by the agent loop
# Returns: (result_text, user_facing_label)
# ---------------------------------------------------------------------------

class ToolExecutor:
    def __init__(self, repository: IStockRepository, stock_service, formatting_service=None):
        self.repository = repository
        self.stock_service = stock_service
        self.formatter = formatting_service

    def execute(self, tool_name: str, args: Dict[str, Any]) -> Tuple[str, str]:
        """Execute a tool by name. Returns (result_json_str, user_label)."""
        handlers = {
            "resolve_ticker": self._resolve_ticker,
            "run_full_analysis": self._run_full_analysis,
            "get_stock_snapshot": self._get_stock_snapshot,
            "get_news": self._get_news,
            "get_price_history": self._get_price_history,
            "get_earnings": self._get_earnings,
            "web_search": self._web_search,
        }
        handler = handlers.get(tool_name)
        if not handler:
            return json.dumps({"error": f"Unknown tool: {tool_name}"}), f"Unknown tool: {tool_name}"
        return handler(args)

    def _resolve_ticker(self, args: Dict) -> Tuple[str, str]:
        name = args.get("company_name", "")
        label = f"🔍 Resolving ticker for '{name}'..."
        candidate = name.strip().upper()

        # If input looks like a ticker symbol (1-6 uppercase alphanum chars, optional dot),
        # validate it directly first — avoids fuzzy-search returning the wrong stock.
        import re as _re
        if _re.fullmatch(r'[A-Z0-9]{1,6}(\.[A-Z]{1,2})?', candidate):
            quote = self.repository.get_quote(candidate)
            if quote.get("status") == "ok":
                data = quote.get("data", {})
                return json.dumps({
                    "ticker": candidate,
                    "company_name": data.get("name") or candidate,
                }), label

        # Fall back to fuzzy company name search
        match = self.repository.search_company(name)
        if not match:
            return json.dumps({"error": f"Could not resolve ticker for '{name}'"}), label
        result = {"ticker": match["symbol"], "company_name": match.get("long_name") or match.get("short_name") or name}
        return json.dumps(result), label

    def _run_full_analysis(self, args: Dict) -> Tuple[str, str]:
        ticker = args.get("ticker", "").upper()
        label = f"📊 Running full analysis for {ticker}..."
        try:
            from services.stock_service import StockAnalysisService
            analysis = self.stock_service.get_analysis(ticker, ticker)
            recs = analysis.recommendations or {}
            quote = analysis.quote or {}
            quote_data = quote.get("data", {})

            short = recs.get("short_term", {}) or {}
            medium = recs.get("medium_term", {}) or {}
            long_ = recs.get("long_term", {}) or {}
            fundamental = recs.get("fundamental", {}) or {}
            technical = recs.get("technical", {}) or {}
            sentiment = recs.get("sentiment", {}) or {}

            news_list = analysis.news.get("news", [])[:5]
            news_lines = [f"- {a.get('headline', '')}" for a in news_list]

            # Render the full HTML card using FormattingService (includes chart,
            # heatmap badges, logo, expandable sections).
            rendered_html = ""
            if self.formatter:
                try:
                    rendered_html = self.formatter.format_analysis_html(analysis)
                except Exception as fmt_err:
                    import traceback
                    print(f"[Agent] FormattingService error: {fmt_err}")
                    traceback.print_exc()

            result = {
                "ticker": ticker,
                "company_name": analysis.company_name,
                "price": quote_data.get("price"),
                "currency": quote_data.get("currency", "USD"),
                "recommendations": {
                    "short_term": {"label": short.get("label"), "summary": short.get("summary"), "score": short.get("score")},
                    "medium_term": {"label": medium.get("label"), "summary": medium.get("summary"), "score": medium.get("score")},
                    "long_term": {"label": long_.get("label"), "summary": long_.get("summary"), "score": long_.get("score")},
                    "fundamental": {"summary": fundamental.get("summary"), "score": fundamental.get("score")},
                    "technical": {"summary": technical.get("summary"), "score": technical.get("score")},
                    "sentiment": {"summary": sentiment.get("summary"), "score": sentiment.get("score")},
                },
                "recent_news_headlines": news_lines,
                "analysis_html": rendered_html,
            }
            return json.dumps(result), label
        except Exception as e:
            return json.dumps({"error": str(e)}), label

    def _get_stock_snapshot(self, args: Dict) -> Tuple[str, str]:
        ticker = args.get("ticker", "").upper()
        label = f"⚡ Fetching live snapshot for {ticker}..."
        try:
            import math
            import yfinance as yf
            t = yf.Ticker(ticker)
            fi = t.fast_info
            info = t.info or {}

            def _clean(v):
                """Replace NaN/inf with None so json.dumps produces valid JSON."""
                if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                    return None
                return v

            result = {
                "ticker": ticker,
                "company_name": info.get("shortName") or info.get("longName") or ticker,
                "price": _clean(fi.last_price),
                "currency": info.get("currency", "USD"),
                "pe_ratio": _clean(info.get("trailingPE") or info.get("forwardPE")),
                "market_cap": _clean(info.get("marketCap")),
                "52w_high": _clean(fi.year_high),
                "52w_low": _clean(fi.year_low),
                "volume": _clean(fi.three_month_average_volume),
                "dividend_yield": _clean(info.get("dividendYield")),
                "eps": _clean(info.get("trailingEps")),
            }
            # Try to include ownership breakdown if available from repository or yfinance info
            ownership = {}
            try:
                if hasattr(self.repository, 'get_ownership_breakdown'):
                    ownership = self.repository.get_ownership_breakdown(ticker) or {}
                else:
                    insider = info.get('heldPercentInsiders')
                    institutional = info.get('heldPercentInstitutions')
                    if insider is not None or institutional is not None:
                        try:
                            insider_val = float(insider) if insider is not None else 0.0
                            inst_val = float(institutional) if institutional is not None else 0.0
                            retail_val = max(0.0, 1.0 - insider_val - inst_val)
                            def _fmt(v):
                                return f"{v * 100:.1f}%"
                            ownership = {
                                'institutional': _fmt(inst_val),
                                'retail': _fmt(retail_val),
                                'insider': _fmt(insider_val),
                            }
                        except Exception:
                            ownership = {}
            except Exception:
                ownership = {}

            result['ownership'] = ownership
            return json.dumps(result), label
        except Exception as e:
            return json.dumps({"error": str(e)}), label

    def _get_news(self, args: Dict) -> Tuple[str, str]:
        ticker = args.get("ticker", "").upper()
        label = f"📰 Fetching latest news for {ticker}..."
        try:
            news_data = self.repository.get_news(ticker)
            articles = news_data.get("news", [])[:5]
            result = {"ticker": ticker, "articles": articles}
            return json.dumps(result), label
        except Exception as e:
            return json.dumps({"error": str(e)}), label

    def _get_price_history(self, args: Dict) -> Tuple[str, str]:
        ticker = args.get("ticker", "").upper()
        period = args.get("period", "1mo")
        label = f"📈 Fetching {period} price history for {ticker}..."
        try:
            history = self.repository.get_price_history(ticker, period)
            dates = history.get("dates", [])
            prices = history.get("prices", [])
            if prices:
                result = {
                    "ticker": ticker,
                    "period": period,
                    "start_price": prices[0],
                    "end_price": prices[-1],
                    "high": max(p for p in prices if p is not None),
                    "low": min(p for p in prices if p is not None),
                    "change_pct": round((prices[-1] - prices[0]) / prices[0] * 100, 2) if prices[0] else None,
                    "data_points": len(prices),
                }
            else:
                result = {"ticker": ticker, "period": period, "error": "No price data available"}
            return json.dumps(result), label
        except Exception as e:
            return json.dumps({"error": str(e)}), label

    def _get_earnings(self, args: Dict) -> Tuple[str, str]:
        ticker = args.get("ticker", "").upper()
        label = f"💰 Fetching earnings data for {ticker}..."
        try:
            earnings = self.repository.get_earnings(ticker)
            data = earnings.get("data", {}) if isinstance(earnings, dict) else {}
            next_earnings = data.get("next_earnings")
            earnings_history = data.get("earnings_history", []) or []
            latest_known_date = None
            if earnings_history and isinstance(earnings_history[0], dict):
                latest_known_date = earnings_history[0].get("date")

            result = {
                "ticker": ticker,
                "next_earnings_available": bool(next_earnings),
                "next_earnings": next_earnings,
                "latest_known_earnings_date": latest_known_date,
                "earnings_history_count": len(earnings_history),
                "status": earnings.get("status", "ok") if isinstance(earnings, dict) else "ok",
                "error": earnings.get("error") if isinstance(earnings, dict) else None,
            }
            return json.dumps(result), label
        except Exception as e:
            return json.dumps({"error": str(e)}), label

    def _web_search(self, args: Dict) -> Tuple[str, str]:
        query = args.get("query", "")
        label = f"🌐 Searching web: '{query}'..."
        try:
            results = ddg_search(query, max_results=3)
            snippets = [{"title": r.get("title"), "snippet": r.get("snippet", "")[:200], "url": r.get("url")} for r in results]
            return json.dumps({"results": snippets}), label
        except Exception as e:
            return json.dumps({"error": str(e)}), label
