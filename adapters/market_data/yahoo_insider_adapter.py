import yfinance as yf
from .insider_adapter import InsiderAdapter

class YahooInsiderAdapter(InsiderAdapter):
    def get_insider_transactions(self, ticker: str):
        try:
            stock = yf.Ticker(ticker)
            df = stock.insider_transactions
            
            if df is None or df.empty:
                return []
                
            transactions = []
            
            if df.index.name == 'Date' or 'Date' not in df.columns:
                df = df.reset_index()
                
            for _, row in df.head(10).iterrows():
                name = row.get('Insider', row.get('Name', ''))
                position = row.get('Position', '')
                trans_type = row.get('Transaction', row.get('Text', ''))
                
                shares = row.get('Shares', 0)
                try:
                    shares = int(float(shares)) if str(shares).lower() != 'nan' else 0
                except (ValueError, TypeError):
                    shares = 0
                    
                value = row.get('Value', 0)
                try:
                    value = float(value) if str(value).lower() != 'nan' else 0.0
                except (ValueError, TypeError):
                    value = 0.0
                    
                price = abs(value / shares) if value and shares else 0.0
                
                date_val = ''
                if 'Start Date' in row and str(row['Start Date']).lower() != 'nan':
                    date_val = str(row['Start Date']).split(' ')[0]
                elif 'Date' in row and str(row['Date']).lower() != 'nan':
                    date_val = str(row['Date']).split(' ')[0]
                    
                transactions.append({'insider_name': str(name), 'relationship': str(position), 'transaction_type': str(trans_type), 'shares': shares, 'date': date_val, 'price': round(price, 2)})
                
            return transactions
        except Exception as e:
            print(f"Error fetching insider transactions from Yahoo for {ticker}: {e}")
            return []
