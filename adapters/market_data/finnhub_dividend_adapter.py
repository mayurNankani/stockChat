import os
import requests
from datetime import datetime, timedelta


class FinnhubDividendAdapter:
    def get_dividend_history(self, ticker: str):
        """Fetch dividend history from Finnhub API.

        Returns list of dicts: [{'date': 'YYYY-MM-DD', 'amount': float}, ...]
        """
        token = os.environ.get('FINNHUB_API_KEY', '')
        if not token:
            return []

        # Fetch last 5 years by default
        to_date = datetime.utcnow().date()
        from_date = to_date - timedelta(days=5 * 365)
        url = (
            f"https://finnhub.io/api/v1/stock/dividend?symbol={ticker}&from={from_date.isoformat()}&to={to_date.isoformat()}&token={token}"
        )
        try:
            resp = requests.get(url, timeout=6)
            if resp.status_code != 200:
                return []
            data = resp.json()
            if not isinstance(data, list):
                return []
            out = []
            for item in data:
                # Finnhub returns {'paymentDate': '2020-02-06', 'amount': 0.205}
                date_key = item.get('paymentDate') or item.get('date') or item.get('date')
                amt = item.get('amount') or item.get('dividend') or item.get('adjDividend')
                if not date_key or amt is None:
                    continue
                out.append({'date': date_key, 'amount': float(amt)})
            # Sort descending by date
            out.sort(key=lambda x: x['date'], reverse=True)
            return out
        except Exception:
            return []
