import os
import requests
import yfinance as yf
from concurrent.futures import ThreadPoolExecutor
from .peer_adapter import PeerAdapter

class YahooPeerAdapter(PeerAdapter):
    def get_peer_comparison(self, ticker: str):
        peers = []
        
        # 1. Try getting peer symbols via Finnhub
        token = os.environ.get('FINNHUB_API_KEY', '')
        if token:
            try:
                resp = requests.get(f"https://finnhub.io/api/v1/stock/peers?symbol={ticker}&token={token}", timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, list):
                        peers = data
            except Exception as e:
                print(f"Finnhub peers error for {ticker}: {e}")
                
        # 2. Fallback to Yahoo Finance recommendations by symbol if Finnhub didn't work
        if not peers:
            try:
                headers = {'User-Agent': 'Mozilla/5.0'}
                url = f"https://query2.finance.yahoo.com/v6/finance/recommendationsbysymbol/{ticker}"
                resp = requests.get(url, headers=headers, timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    results = data.get('finance', {}).get('result', [])
                    if results:
                        recs = results[0].get('recommendedSymbols', [])
                        peers = [r.get('symbol') for r in recs if r.get('symbol')]
            except Exception as e:
                print(f"Yahoo peers fallback error for {ticker}: {e}")
                
        # Remove the target ticker itself and limit to top 5
        peers = [p for p in peers if p != ticker][:5]
        
        if not peers:
            return []
            
        def fetch_peer_data(peer_ticker):
            try:
                t = yf.Ticker(peer_ticker)
                info = t.info
                if not info:
                    return None
                    
                price = info.get('regularMarketPrice') or info.get('currentPrice')
                if price is None:
                    try:
                        price = t.fast_info.last_price
                    except Exception:
                        price = None
                    
                mc = info.get('marketCap')
                if mc:
                    if mc >= 1e12:
                        mc_str = f"${mc / 1e12:.2f}T"
                    elif mc >= 1e9:
                        mc_str = f"${mc / 1e9:.2f}B"
                    else:
                        mc_str = f"${mc / 1e6:.2f}M"
                else:
                    mc_str = "N/A"
                    
                pe = info.get('trailingPE') or info.get('forwardPE')
                
                return {
                    'ticker': peer_ticker,
                    'name': info.get('shortName') or info.get('longName') or peer_ticker,
                    'pe_ratio': round(pe, 2) if pe else "N/A",
                    'market_cap': mc_str,
                    'price': round(price, 2) if price else "N/A",
                    'sector': info.get('sector', 'N/A')
                }
            except Exception as e:
                print(f"Error fetching peer {peer_ticker}: {e}")
                return None
                
        results = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            for res in executor.map(fetch_peer_data, peers):
                if res:
                    results.append(res)
                    
        return results
