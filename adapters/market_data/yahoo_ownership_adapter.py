import yfinance as yf
from .ownership_adapter import OwnershipAdapter

class YahooOwnershipAdapter(OwnershipAdapter):
    def get_ownership_breakdown(self, ticker: str):
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            
            # If info is missing, return explicit None-valued keys so callers
            # can render a consistent shape instead of treating it as absent.
            if not info:
                return {'institutional': None, 'retail': None, 'insider': None}

            insider = info.get('heldPercentInsiders')
            institutional = info.get('heldPercentInstitutions')

            # If both values are missing, return explicit None keys
            if insider is None and institutional is None:
                return {'institutional': None, 'retail': None, 'insider': None}

            try:
                insider_val = float(insider) if insider is not None else 0.0
            except Exception:
                insider_val = 0.0
            try:
                inst_val = float(institutional) if institutional is not None else 0.0
            except Exception:
                inst_val = 0.0

            retail_val = max(0.0, 1.0 - insider_val - inst_val)

            def format_pct(val):
                try:
                    return f"{val * 100:.1f}%"
                except Exception:
                    return None

            return {
                'institutional': format_pct(inst_val) if inst_val is not None else None,
                'retail': format_pct(retail_val) if retail_val is not None else None,
                'insider': format_pct(insider_val) if insider_val is not None else None,
            }
        except Exception as e:
            print(f"Error fetching ownership breakdown for {ticker}: {e}")
            return {'institutional': None, 'retail': None, 'insider': None}
