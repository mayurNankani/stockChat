"""Unified stock analysis use-case.

Coordinates adapters (market data, news, sentiment, company lookup) and
legacy analysis agent to produce a domain-level RecommendationReport plus
supporting raw sections. This is an incremental integration layer that
allows the web routes to migrate away from direct agent/repository calls.
"""
from __future__ import annotations
from typing import Dict, Any, Optional
from dataclasses import asdict

from core.models import RecommendationReport, RecommendationDetail
from core.analysis.recommendation_engine import (
    ComponentScores,
    compute_weighted_score,
    derive_rating,
)
from adapters.market_data.interface import MarketDataAdapter
from adapters.news.interface import NewsAdapter
from adapters.sentiment.interface import SentimentAdapter
from adapters.company_lookup.interface import CompanyLookupAdapter
from src.agent_improved import StockAnalysisAgentImproved


class StockAnalysisUseCase:
    """High-level orchestrator for performing a full stock analysis query."""

    def __init__(
        self,
        market_data: MarketDataAdapter,
        news_adapter: NewsAdapter,
        sentiment_adapter: SentimentAdapter,
        company_lookup: CompanyLookupAdapter,
        repository=None,
        legacy_agent: Optional[StockAnalysisAgentImproved] = None,
    ) -> None:
        self.market_data = market_data
        self.news_adapter = news_adapter
        self.sentiment_adapter = sentiment_adapter
        self.company_lookup = company_lookup
        self.repository = repository
        self.legacy_agent = legacy_agent or StockAnalysisAgentImproved()

    def resolve_symbol(self, query: str) -> Optional[str]:
        identities = self.company_lookup.search(query, limit=1)
        if identities:
            return identities[0].symbol
        # Fallback: if user typed something ticker-like
        if query.strip().upper() == query.strip() and 1 <= len(query.strip()) <= 5:
            return query.strip().upper()
        return None

    def run(self, query: str) -> Dict[str, Any]:
        """Execute unified analysis flow.

        Steps:
        1. Resolve ticker
        2. Fetch quote (market data) for name enrichment
        3. Run legacy fundamental/technical/sentiment scoring
        4. Compute horizon recommendations using new weighting engine
        5. Produce RecommendationReport + presentation dict
        """
        symbol = self.resolve_symbol(query)
        if not symbol:
            return {"error": f"Could not resolve symbol for '{query}'"}

        # Quote (for company name display)
        quote = self.market_data.get_quote(symbol)
        company_name = quote.name or symbol

        # Legacy detailed analysis (fundamental + technical + sentiment integration)
        legacy_recs = self.legacy_agent.get_recommendation(symbol)
        fundamental = legacy_recs["fundamental"]
        technical = legacy_recs["technical"]
        sentiment = legacy_recs["sentiment"]

        # Build component scores from legacy outputs
        comp_scores = ComponentScores(
            fundamental=float(fundamental.get("score", 50.0)),
            technical=float(technical.get("score", 50.0)),
            sentiment=float(sentiment.get("score", 50.0)),
        )

        # Horizons using new engine weights (ensures consistency with proposal)
        horizons = {}
        for horizon in ("short", "medium", "long"):
            composite = compute_weighted_score(horizon, comp_scores)
            rating = derive_rating(composite)
            # Reasons reuse summaries from legacy parts (can be refined later)
            if horizon == "short":
                reasons = [technical.get("summary", ""), sentiment.get("summary", "")]
            elif horizon == "medium":
                reasons = [fundamental.get("summary", ""), technical.get("summary", ""), sentiment.get("summary", "")]
            else:  # long
                reasons = [fundamental.get("summary", ""), technical.get("summary", "")]
            # Filter empties
            reasons = [r for r in reasons if r]
            horizons[horizon] = RecommendationDetail(
                horizon=horizon,
                rating=rating,
                score=round(composite, 2),
                reasons=reasons,
            )

        report = RecommendationReport(
            ticker=symbol,
            company_name=company_name,
            horizons=horizons,
            fundamental_score=comp_scores.fundamental,
            technical_score=comp_scores.technical,
            sentiment_score=comp_scores.sentiment,
        )

        # Fetch new data for card sections
        if self.repository:
            ownership = self.repository.get_ownership_breakdown(symbol) if hasattr(self.repository, 'get_ownership_breakdown') else {}
            insiders = self.repository.get_insider_transactions(symbol) if hasattr(self.repository, 'get_insider_transactions') else []
            dividends = self.repository.get_dividend_history(symbol) if hasattr(self.repository, 'get_dividend_history') else []
            peers = self.repository.get_peer_comparison(symbol) if hasattr(self.repository, 'get_peer_comparison') else []
        else:
            ownership = self.market_data.get_ownership_breakdown(symbol) if hasattr(self.market_data, 'get_ownership_breakdown') else {}
            insiders = self.market_data.get_insider_transactions(symbol) if hasattr(self.market_data, 'get_insider_transactions') else []
            dividends = self.market_data.get_dividend_history(symbol) if hasattr(self.market_data, 'get_dividend_history') else []
            peers = self.market_data.get_peer_comparison(symbol) if hasattr(self.market_data, 'get_peer_comparison') else []

        # Presentation dict (still used by existing formatting service)
        presentation = {
            "ticker": symbol,
            "company_name": company_name,
            "quote": {
                "price": quote.price,
                "currency": quote.currency,
                "name": quote.name,
            },
            "recommendation_report": self._serialize_report(report),
            "legacy_components": {
                "fundamental": fundamental,
                "technical": technical,
                "sentiment": sentiment,
            },
            "ownership": ownership,
            "insiders": insiders,
            "dividends": dividends,
            "peers": peers,
        }
        return presentation

    def _serialize_report(self, report: RecommendationReport) -> Dict[str, Any]:
        return {
            "ticker": report.ticker,
            "company_name": report.company_name,
            "horizons": {h: asdict(d) for h, d in report.horizons.items()},
            "fundamental_score": report.fundamental_score,
            "technical_score": report.technical_score,
            "sentiment_score": report.sentiment_score,
        }
