from typing import Protocol, List, Dict

class PeerAdapter(Protocol):
    def get_peer_comparison(self, ticker: str) -> List[Dict]:
        """Returns a list of peer companies and key metrics for comparison."""
        ...
