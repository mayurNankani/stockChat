from typing import Protocol, List, Dict

class InsiderAdapter(Protocol):
    def get_insider_transactions(self, ticker: str) -> List[Dict]:
        """Returns recent insider transactions for a ticker."""
        ...
