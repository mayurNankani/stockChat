from typing import Protocol, List, Dict

class OwnershipAdapter(Protocol):
    def get_ownership_breakdown(self, ticker: str) -> Dict:
        """Returns ownership breakdown (institutional, retail, insider) for a ticker."""
        ...
