"""
Domain Models
Data classes representing core business entities
"""

from dataclasses import dataclass
from typing import Dict, Any, List, Optional
from enum import Enum


class RecommendationLabel(Enum):
    """Stock recommendation labels"""
    STRONG_BUY = "STRONG BUY"
    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"
    UNKNOWN = "N/A"


@dataclass
class StockQuote:
    """Stock quote data"""
    symbol: str
    price: Optional[float]
    currency: str
    name: str
    error: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StockQuote':
        """Create from dictionary"""
        return cls(
            symbol=data.get('symbol', ''),
            price=data.get('price'),
            currency=data.get('currency', 'USD'),
            name=data.get('name', ''),
            error=data.get('error')
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'symbol': self.symbol,
            'price': self.price,
            'currency': self.currency,
            'name': self.name,
            'error': self.error
        }


@dataclass
class TimeHorizonRecommendation:
    """Recommendation for a specific time horizon"""
    label: str
    summary: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'label': self.label,
            'summary': self.summary
        }


@dataclass
class StockRecommendations:
    """Complete set of stock recommendations across time horizons"""
    short_term: TimeHorizonRecommendation
    medium_term: TimeHorizonRecommendation
    long_term: TimeHorizonRecommendation
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'short_term': self.short_term.to_dict(),
            'medium_term': self.medium_term.to_dict(),
            'long_term': self.long_term.to_dict()
        }


@dataclass
class NewsArticle:
    """News article information"""
    headline: str
    summary: str
    url: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'headline': self.headline,
            'summary': self.summary,
            'url': self.url
        }


@dataclass
class PriceHistory:
    """Historical price data"""
    dates: List[str]
    prices: List[float]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'dates': self.dates,
            'prices': self.prices
        }
    
    @property
    def is_empty(self) -> bool:
        """Check if history is empty"""
        return not self.dates or not self.prices


@dataclass
class CompanyMatch:
    """Company search result"""
    symbol: str
    long_name: Optional[str]
    short_name: Optional[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'symbol': self.symbol,
            'long_name': self.long_name,
            'short_name': self.short_name
        }
    
    @property
    def display_name(self) -> str:
        """Get best display name"""
        return self.long_name or self.short_name or self.symbol


@dataclass
class StockAnalysis:
    """Complete stock analysis result"""
    ticker: str
    company_name: str
    quote: Dict[str, Any]
    recommendations: Dict[str, Any]
    news: Dict[str, Any]
    price_history: Dict[str, Any]
    ownership: Dict[str, Any] = None
    insiders: list = None
    dividends: list = None
    peers: list = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'ticker': self.ticker,
            'company_name': self.company_name,
            'quote': self.quote,
            'recommendations': self.recommendations,
            'news': self.news,
            'price_history': self.price_history,
            'ownership': self.ownership,
            'insiders': self.insiders,
            'dividends': self.dividends,
            'peers': self.peers
        }
