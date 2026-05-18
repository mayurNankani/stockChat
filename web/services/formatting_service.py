"""
Formatting Service
HTML formatting utilities for stock analysis display
"""

import os
import re
import time
from datetime import datetime
from typing import Dict, Any, List, Any
from src.tools.web_search import normalize_result_url


# Tooltip definitions
FUNDAMENTAL_TOOLTIPS = {
    "market_cap": "Company size measured as share price × shares outstanding; context for stability/risk.",
    "pe_ratio": "Price divided by last 12 months' earnings; lower often means cheaper relative to earnings.",
    "forward_pe": "Price divided by projected earnings; shows valuation based on expected profit.",
    "peg_ratio": "PE divided by earnings growth rate; adjusts valuation for growth (≈1 ≈ fair).",
    "price_to_book": "Price relative to book value per share; useful for asset-heavy businesses.",
    "revenue_growth": "Year-over-year top-line growth; indicates demand and expansion speed.",
    "earnings_growth": "Growth in net income; shows profit trend and scalability.",
    "profit_margins": "Net profit ÷ revenue; higher = more profit retained per sale.",
    "return_on_equity": "Net income ÷ shareholder equity; how well equity generates profit.",
    "debt_to_equity": "Total debt ÷ shareholders' equity; higher means more leverage risk.",
    "current_ratio": "Current assets ÷ current liabilities; measures short-term liquidity.",
    "dividend_yield": "Annual dividends ÷ share price; income return from holding the stock."
}

TECHNICAL_TOOLTIPS = {
    "current_price": "The most recent closing price; immediate market value reference.",
    "price_change": "Percent change from previous close; shows short-term movement.",
    "rsi": "Relative Strength Index (0–100); <30 often oversold (buy), >70 overbought (sell).",
    "macd": "MACD line (short EMA − long EMA); shows trend direction and momentum.",
    "macd_signal": "Smoothed MACD used for crossovers (trade signal line).",
    "macd_hist": "MACD − signal; rising positive histogram shows strengthening bullish momentum.",
    "adx": "Average Directional Index; measures trend strength (values > ~25 indicate a strong trend).",
    "bb_width": "Width of Bollinger Bands relative to MA; narrow = low volatility, wide = high volatility.",
    "atr": "Average True Range; average size of daily price moves (volatility measure).",
    "mfi": "Money Flow Index; volume-weighted momentum oscillator, extremes suggest overbought/oversold.",
    "sma_20": "20-period Simple Moving Average; price above suggests short-term uptrend.",
    "sma_50": "50-period Simple Moving Average; price above suggests medium-term uptrend.",
    "sma_20_cross_50": "True when SMA20 crosses above SMA50 indicating a bullish trend change (golden cross)."
}


class FormattingService:
    """Utilities for formatting analysis data as HTML"""

    def _format_ownership(self, ownership: dict) -> str:
        # Always render an ownership section so the UI doesn't flicker
        # when data is intermittently unavailable. Use 'N/A' for missing
        # values to make flakiness visible but non-breaking.
        if not isinstance(ownership, dict):
            ownership = {}
        inst = ownership.get('institutional')
        retail = ownership.get('retail')
        insider = ownership.get('insider')
        return (
            "<div class='ownership-section'><b>Ownership Breakdown:</b> "
            f"Institutional: {inst if inst is not None else 'Ownership data unavailable'} | "
            f"Retail: {retail if retail is not None else 'Ownership data unavailable'} | "
            f"Insider: {insider if insider is not None else 'Ownership data unavailable'}"
            "</div>"
        )

    def _format_insider(self, insiders: list) -> str:
        if not insiders:
            return ''
        # Preview: show first 3 rows; expanded content shows up to 10
        preview_list = insiders[:3]
        remaining = insiders[3:10]

        def _rows(items):
            return ''.join(
                f"<tr><td>{i.get('insider_name','')}</td><td>{i.get('relationship','')}</td><td>{i.get('transaction_type','')}</td>"
                f"<td>{i.get('shares','')}</td><td>{i.get('date','')}</td><td>${float(i.get('price',0)):.2f}</td></tr>"
                for i in items
            )

        preview_rows = _rows(preview_list)
        more_rows = _rows(remaining) if remaining else ''

        toggle_id = f"insider_toggle_{int(time.time() * 1000)}"
        toggle_button = (
            f"<button type='button' class='section-toggle' id='btn_{toggle_id}' "
            f"onclick=\"var c=document.getElementById('{toggle_id}'); var b=document.getElementById('btn_{toggle_id}'); var show=c.style.display==='none'; c.style.display=show?'block':'none'; b.textContent=show?'Hide ▴':'Show more ▾';\">"
            f"Show more ▾"
            f"</button>"
        )

        header_html = (
            f"<div style='display:flex;align-items:center;justify-content:space-between;gap:12px;'>"
            f"<b>Recent Insider Transactions:</b>"
            f"{toggle_button}"
            f"</div>"
        )

        more_html = ''
        if more_rows:
            more_html = (
                f"<div id='{toggle_id}' style='display:none;margin-top:0.5rem;'>"
                f"<table class='insider-table'><tr><th>Name</th><th>Role</th><th>Type</th><th>Shares</th><th>Date</th><th>Price</th></tr>"
                f"{preview_rows}{more_rows}</table>"
                f"</div>"
            )

        # Always show the preview table; expanded content appends additional rows
        return (
            "<div class='insider-section'>"
            f"{header_html}"
            f"<table class='insider-table'><tr><th>Name</th><th>Role</th><th>Type</th><th>Shares</th><th>Date</th><th>Price</th></tr>"
            f"{preview_rows}</table>"
            f"{more_html}"
            "</div>"
        )

    def _format_dividends(self, dividends: list) -> str:
        if not dividends:
            return ''
        preview_list = dividends[:3]
        remaining = dividends[3:10]

        def _rows(items):
            return ''.join(f"<tr><td>{d.get('date','')}</td><td>{d.get('amount','')}</td></tr>" for d in items)

        preview_rows = _rows(preview_list)
        more_rows = _rows(remaining) if remaining else ''

        toggle_id = f"div_toggle_{int(time.time() * 1000)}"
        toggle_button = (
            f"<button type='button' class='section-toggle' id='btn_{toggle_id}' "
            f"onclick=\"var c=document.getElementById('{toggle_id}'); var b=document.getElementById('btn_{toggle_id}'); var show=c.style.display==='none'; c.style.display=show?'block':'none'; b.textContent=show?'Hide ▴':'Show more ▾';\">"
            f"Show more ▾"
            f"</button>"
        )

        header_html = (
            f"<div style='display:flex;align-items:center;justify-content:space-between;gap:12px;'>"
            f"<b>Dividend History:</b>"
            f"{toggle_button}"
            f"</div>"
        )

        more_html = ''
        if more_rows:
            more_html = (
                f"<div id='{toggle_id}' style='display:none;margin-top:0.5rem;'>"
                f"<table class='dividend-table'><tr><th>Date</th><th>Amount</th></tr>"
                f"{preview_rows}{more_rows}</table>"
                f"</div>"
            )

        return (
            "<div class='dividend-section'>"
            f"{header_html}"
            f"<table class='dividend-table'><tr><th>Date</th><th>Amount</th></tr>"
            f"{preview_rows}</table>"
            f"{more_html}"
            "</div>"
        )

    def _format_peers(self, peers: list) -> str:
        if not peers:
            return ''
        preview_list = peers[:3]
        remaining = peers[3:10]

        def _rows(items):
            return ''.join(
                f"<tr><td>{p.get('ticker','')}</td><td>{p.get('name','')}</td><td>{p.get('pe_ratio','')}</td><td>{p.get('market_cap','')}</td><td>{p.get('price','')}</td><td>{p.get('sector','')}</td></tr>"
                for p in items
            )

        preview_rows = _rows(preview_list)
        more_rows = _rows(remaining) if remaining else ''

        toggle_id = f"peers_toggle_{int(time.time() * 1000)}"
        toggle_button = (
            f"<button type='button' class='section-toggle' id='btn_{toggle_id}' "
            f"onclick=\"var c=document.getElementById('{toggle_id}'); var b=document.getElementById('btn_{toggle_id}'); var show=c.style.display==='none'; c.style.display=show?'block':'none'; b.textContent=show?'Hide ▴':'Show more ▾';\">"
            f"Show more ▾"
            f"</button>"
        )

        header_html = (
            f"<div style='display:flex;align-items:center;justify-content:space-between;gap:12px;'>"
            f"<b>Peer Comparison:</b>"
            f"{toggle_button}"
            f"</div>"
        )

        more_html = ''
        if more_rows:
            more_html = (
                f"<div id='{toggle_id}' style='display:none;margin-top:0.5rem;'>"
                f"<table class='peer-table'><tr><th>Ticker</th><th>Name</th><th>P/E</th><th>Market Cap</th><th>Price</th><th>Sector</th></tr>"
                f"{preview_rows}{more_rows}</table>"
                f"</div>"
            )

        return (
            "<div class='peer-section'>"
            f"{header_html}"
            f"<table class='peer-table'><tr><th>Ticker</th><th>Name</th><th>P/E</th><th>Market Cap</th><th>Price</th><th>Sector</th></tr>"
            f"{preview_rows}</table>"
            f"{more_html}"
            "</div>"
        )

    @staticmethod
    def _clean_reason_summary(summary: str, section: str) -> str:
        """Normalize generic fallback text so each section keeps its own meaning."""
        text = (summary or '').strip()
        if not text:
            return ''

        generic_technical = 'No strong technical signals detected.'
        generic_fundamental = 'No strong fundamental signals detected.'

        lowered = text.lower()
        if lowered == generic_technical.lower():
            if section == 'technical':
                return text
            return f'No strong {section} signals detected.'

        if lowered == generic_fundamental.lower():
            if section == 'fundamental':
                return text
            return f'No strong {section} signals detected.'

        return text

    @staticmethod
    def _parse_summary_sections(summary_text: str) -> Dict[str, str]:
        """Parse 'Fundamental(s): ... | Technical: ... | Sentiment: ...' summary text.
        Accepts both Fundamental and Fundamentals prefixes and is case-insensitive."""
        parsed = {"fundamental": "", "technical": "", "sentiment": ""}
        text = (summary_text or "").strip()
        if not text:
            return parsed

        for part in text.split('|'):
            chunk = part.strip()
            if not chunk:
                continue
            m = re.match(r'^(fundamental(?:s)?|technical|sentiment)\s*:\s*(.+)$', chunk, flags=re.IGNORECASE)
            if not m:
                continue
            key = m.group(1).lower()
            value = m.group(2).strip()
            if key.startswith('fundamental'):
                parsed['fundamental'] = value
            elif key == 'technical':
                parsed['technical'] = value
            elif key == 'sentiment':
                parsed['sentiment'] = value

        return parsed

    @staticmethod
    def add_tooltips(text: str) -> str:
        """Add tooltip spans to technical terms"""
        all_keys = list(FUNDAMENTAL_TOOLTIPS.keys()) + list(TECHNICAL_TOOLTIPS.keys())
        all_keys.sort(key=len, reverse=True)

        for key in all_keys:
            tooltip = FUNDAMENTAL_TOOLTIPS.get(key) or TECHNICAL_TOOLTIPS.get(key)
            text = re.sub(
                rf'\b{re.escape(key)}\b',
                f'<span title="{tooltip}">{key}</span>',
                text,
                flags=re.IGNORECASE
            )
        return text

    @staticmethod
    def to_bullets(text: str) -> str:
        """Convert comma-separated text to HTML bullet list"""
        items = [item.strip() for item in text.split(',') if item.strip()]
        if not items:
            return ''

        bullets = ''.join(f'<li>{item}</li>' for item in items)
        return f'<ul>{bullets}</ul>'

    @staticmethod
    def _split_reason_items(text: str) -> List[str]:
        """Split reason text into bullet-friendly items using common separators."""
        raw = (text or '').strip()
        if not raw:
            return []
        pieces = re.split(r'\s*(?:,|;|\|)\s*', raw)
        return [p.strip() for p in pieces if p.strip()]

    @staticmethod
    def _horizon_section_order(term: str) -> List[str]:
        """Order sections by horizon importance to keep quick reasons concise."""
        t = (term or '').lower()
        if 'short-term' in t:
            return ['technical', 'sentiment', 'fundamental']
        if 'medium-term' in t:
            return ['fundamental', 'technical', 'sentiment']
        if 'long-term' in t:
            return ['fundamental', 'technical', 'sentiment']
        return ['fundamental', 'technical', 'sentiment']

    @staticmethod
    def heatmap(label: str) -> str:
        """Generate colored recommendation badge"""
        label = (label or 'N/A').upper()
        class_map = {
            'STRONG BUY': 'badge-strong-buy',
            'BUY':        'badge-buy',
            'HOLD':       'badge-hold',
            'SELL':       'badge-sell',
        }
        icon_map = {
            'STRONG BUY': '▲▲',
            'BUY':        '▲',
            'HOLD':       '◆',
            'SELL':       '▼',
        }
        css_class = class_map.get(label, 'badge-na')
        icon = icon_map.get(label, '—')
        return f'<span class="badge {css_class}">{icon} {label}</span>'

    def expand_block(self, term: str, label: str, bar: str, bullets: str, idx: int,
                     fundamental_summary: str = None, technical_summary: str = None, sentiment_summary: str = None) -> str:
        """Create recommendation section with visible horizon reasons."""

        section_data = {
            'fundamental': (fundamental_summary or '').strip(),
            'technical': (technical_summary or '').strip(),
            'sentiment': (sentiment_summary or '').strip(),
        }

        section_item_limit = {
            'technical': 4,
            'fundamental': 3,
            'sentiment': 2,
        }

        preview_blocks: List[str] = []
        for key in self._horizon_section_order(term):
            text = section_data.get(key, '')
            if not text:
                continue
            title = key.capitalize()
            items = self._split_reason_items(text)
            if not items:
                continue
            trimmed_items = items[:section_item_limit.get(key, 3)]
            bullets_html = ''.join(f'<li>{self.add_tooltips(item)}</li>' for item in trimmed_items)
            preview_blocks.append(
                f'<div class="reason-preview reason-preview-{key}">'
                f'<span class="reason-preview-label">{title}</span>'
                f'<ul class="reason-preview-list">{bullets_html}</ul>'
                f'</div>'
            )

        if preview_blocks:
            quick_html = f'<div class="reasons-preview">{"".join(preview_blocks)}</div>'
        else:
            quick_html = f'<div class="reasons-body">{bullets}</div>'

        # Use a <details> element so the recommendation row is collapsed by default
        # Summary shows the term and the heatmap badge; expanding reveals the reason preview.
        summary_html = (
            f"<div style=\"display:flex;align-items:center;gap:10px;justify-content:space-between;width:100%\">"
            f"<div class=\"rec-label rec-label-collapsed\">{term}</div>"
            f"<div style=\"margin-left:8px;\">{bar}</div>"
            f"</div>"
        )

        return (
            f"<div class=\"rec-row\">"
            f"<details class=\"rec-row-details\">"
            f"<summary>{summary_html}</summary>"
            f"<div class=\"rec-details-body\">{quick_html}</div>"
            f"</details>"
            f"</div>"
        )

    def format_analysis_html(self, analysis) -> str:
        """
        Format complete analysis as HTML
        
        Args:
            analysis: StockAnalysis dataclass object
            
        Returns:
            HTML string for chat rendering
        """
        ticker = getattr(analysis, 'ticker', '') or 'N/A'
        company_name = getattr(analysis, 'company_name', '') or ticker
        quote = getattr(analysis, 'quote', {}) or {}
        recommendations = getattr(analysis, 'recommendations', {}) or {}
        news_result = getattr(analysis, 'news', {}) or {}
        price_history = getattr(analysis, 'price_history', {}) or {}
        ownership = getattr(analysis, 'ownership', {}) or {}
        insiders = getattr(analysis, 'insiders', []) or []
        dividends = getattr(analysis, 'dividends', []) or []
        peers = getattr(analysis, 'peers', []) or []

        display_name = self._safe_call(
            self._get_display_name,
            company_name,
            quote,
            fallback=company_name,
        )

        logo_html = ''
        if ticker != 'N/A':
            logo_html = self._safe_call(self._format_logo, ticker, fallback='')

        price_html = self._safe_call(self._format_price_line, quote, fallback='')
        price_chart_html = self._safe_call(
            self._format_price_chart,
            ticker,
            price_history,
            fallback='',
        )
        ownership_html = self._safe_call(self._format_ownership, ownership, fallback='')
        insider_html = self._safe_call(self._format_insider, insiders, fallback='')
        dividend_html = self._safe_call(self._format_dividends, dividends, fallback='')
        peer_html = self._safe_call(self._format_peers, peers, fallback='')
        recommendations_html = self._safe_call(
            self._format_recommendations,
            recommendations,
            fallback='',
        )
        news_html = self._safe_call(self._format_news, news_result, fallback='')

        # Single-column layout: header -> price/chart -> ownership/insider/dividend/peers -> recommendations -> news
        primary_label = (
            (recommendations.get('medium_term') or {}).get('label')
            or (recommendations.get('short_term') or {}).get('label')
            or (recommendations.get('long_term') or {}).get('label')
            or 'N/A'
        )

        return (
            f"<div class='analysis-block stock-card' data-ticker='{ticker}'>"
            f"<div class='stock-card-header'>"
            f"{logo_html}"
            f"<div>"
            f"<div class='stock-name'>{display_name}<span class='stock-ticker-badge'>{ticker}</span></div>"
            f"<div class='stock-price-line'>{price_html}</div>"
            f"</div>"
            f"<div style='margin-left:auto;display:flex;align-items:center;gap:8px;'>{self.heatmap(primary_label)}</div>"
            f"</div>"

            f"{price_chart_html}"
            f"{ownership_html}"
            f"{insider_html}"
            f"{dividend_html}"
            f"{peer_html}"

            # Recommendations remain a first-class section so they visually match other blocks
            f"<div class='rec-section-wrap' style='margin-top:0.9rem;'>{recommendations_html}</div>"

            f"{news_html}"
            f"</div>"
        )

    @staticmethod
    def _safe_call(fn, *args, fallback=''):
        """Run formatter step defensively so one bad field doesn't drop the whole card."""
        try:
            return fn(*args)
        except Exception:
            return fallback
    
    def _format_logo(self, ticker: str) -> str:
        """Format company logo via the server-side proxy endpoint."""
        logo_url = f"/api/logo/{ticker}"
        return (
            f'<img src="{logo_url}" alt="{ticker}" class="stock-logo" '
            f'onerror="this.style.display=\'none\'"/>'
        )
    
    def _get_display_name(self, company_name: str, quote: Dict[str, Any]) -> str:
        """Get best display name from quote data"""
        try:
            qdata = quote.get('data', {}) if isinstance(quote, dict) else {}
            longname = qdata.get('name') or qdata.get('shortName') or qdata.get('longName')
            if longname and longname.strip():
                return longname
        except Exception:
            pass
        return company_name
    
    def _format_price_line(self, quote: Dict[str, Any]) -> str:
        """Format current price line with data freshness timestamp"""
        try:
            qdata = quote.get('data', {}) if isinstance(quote, dict) else {}
            price = qdata.get('price')
            currency = qdata.get('currency', '')

            if price is not None and price != 'N/A':
                try:
                    price_val = float(price)
                    price_text = f"${price_val:,.2f}"
                except Exception:
                    price_text = str(price)

                fetched_at = datetime.now().strftime('%b %d, %H:%M')
                return (
                    f"<span style='font-size:0.95em;color:#6b7280;'>"
                    f"{price_text} {currency}"
                    f"<span title='Data fetched at {fetched_at}' "
                    f"style='margin-left:6px;font-size:0.85em;color:#9ca3af;cursor:help;'>"
                    f"&#128337; {fetched_at}</span>"
                    f"</span>"
                )
        except Exception:
            pass

        return ''
    
    def _format_price_chart(self, ticker: str, price_history: Dict[str, Any]) -> str:
        """Format price chart section"""
        if not isinstance(price_history, dict):
            return ''

        dates = price_history.get('dates') or []
        prices_raw = price_history.get('prices') or []
        if not dates or not prices_raw:
            return ''

        valid_prices = []
        for p in prices_raw:
            try:
                if p is not None:
                    valid_prices.append(float(p))
            except Exception:
                continue

        if not valid_prices:
            return ''
        first_price = valid_prices[0]
        last_price = valid_prices[-1]
        overall_change = last_price - first_price
        overall_change_pct = (overall_change / first_price) * 100 if first_price else 0.0
        change_color = '#10b981' if overall_change >= 0 else '#ef4444'
        change_symbol = '+' if overall_change >= 0 else ''
        perf_class = 'positive' if overall_change >= 0 else 'negative'
        
        chart_id = f"chart_{ticker.replace('.', '_')}_{int(time.time() * 1000)}"
        
        # Build an inline onclick JS string without using f-string braces so Python doesn't interpret JS object braces.
        onclick_js = (
            "(function(cid,t){"
            "var d=document.getElementById(cid);var b=document.getElementById('btn_'+cid);if(!d)return;"
            "var hidden=d.style.display==='none'||d.style.display=='';"
            "if(hidden){d.style.display='block';if(b)b.textContent='Hide Chart ▲';"
            "var L=document.getElementById('loading_'+cid);var C=document.getElementById('canvas_'+cid);"
            "if(L)L.style.display='block';if(C)C.style.display='none';"
            "fetch('/api/price-history?ticker='+encodeURIComponent(t)+'&period=1mo').then(r=>r.json()).then(function(data){"
            "try{var ctx=document.getElementById('canvas_'+cid).getContext('2d');document.getElementById('canvas_'+cid).height=250;"
            "try{if(window._inlineCharts&&window._inlineCharts[cid]){window._inlineCharts[cid].destroy()}}catch(e){};"
            "var canvas=document.getElementById('canvas_'+cid);try{canvas.style.display='block';canvas.width=(canvas.clientWidth||Math.floor((canvas.parentElement&&canvas.parentElement.getBoundingClientRect&&canvas.parentElement.getBoundingClientRect().width)||600));}catch(e){};canvas.height=250;"
            "// sanitize response;"
            "var safeDates = (data.dates||[]).map(function(d){return d==null? '' : String(d);});"
            "var safePrices = (data.prices||[]).map(function(p){return p==null? null : Number(p);});"
            "var ch=new Chart(ctx,{type:'line',data:{labels:safeDates,datasets:[{data:safePrices,borderColor:'#10b981',backgroundColor:'#10b98118',fill:true,pointRadius:0}]},options:{responsive:false,maintainAspectRatio:false,plugins:{tooltip:{mode:'index',intersect:false,callbacks:{title:function(items){try{return items&&items.length? (items[0].label||'') : ''; }catch(e){return '';}},label:function(ctx){try{var y=ctx.parsed&&ctx.parsed.y;return (y==null)?'' : '$' + Number(y).toFixed(2);}catch(e){return '';}}}}}});"
            "window._inlineCharts=window._inlineCharts||{};window._inlineCharts[cid]=ch;}catch(e){console.error(e)}}).finally(function(){if(L)L.style.display='none';if(C)C.style.display='block'});"
            "}else{d.style.display='none';if(b)b.textContent='Chart';}})('" + chart_id + "','" + ticker + "')"
        )

        return (
            f"<div class=\"perf-bar {perf_class}\">"
            f"<span>"
            f"<b>30-Day:</b>"
            f"<span style=\"color:{change_color};font-weight:600;\">{change_symbol}{overall_change_pct:.2f}% ({change_symbol}${overall_change:.2f})</span>"
            f"</span>"
            f"<button class=\"toggle-chart-btn\" data-chart-id=\"{chart_id}\" data-ticker=\"{ticker}\" onclick=\"{onclick_js}\">"
            f"<span id=\"btn_{chart_id}\">Chart</span>"
            f"</button>"
            f"</div>"
            f"<div id=\"{chart_id}\" class=\"chart-container\" style=\"display:none;\">"
            f"<div style=\"display:flex;justify-content:center;margin-bottom:0.75rem;\">"
            f"<div class=\"period-control\">"
            f"<button class=\"period-btn\" data-period=\"1d\" data-ticker=\"{ticker}\" data-chart-id=\"{chart_id}\">1D</button>"
            f"<button class=\"period-btn\" data-period=\"5d\" data-ticker=\"{ticker}\" data-chart-id=\"{chart_id}\">5D</button>"
            f"<button class=\"period-btn active\" data-period=\"1mo\" data-ticker=\"{ticker}\" data-chart-id=\"{chart_id}\">1M</button>"
            f"</div>"
            f"</div>"
            f"<canvas id=\"canvas_{chart_id}\" style=\"width:100%;height:250px;\"></canvas>"
            f"<div id=\"loading_{chart_id}\" style=\"text-align:center;padding:20px;color:var(--text-3,#64748b);display:none;\">Loading chart...</div>"
            f"</div>"
        )

    def _format_news(self, news_result: Dict[str, Any]) -> str:
        """Format news section"""
        articles = []
        if isinstance(news_result, dict):
            articles = news_result.get('news') or []
        elif isinstance(news_result, list):
            articles = news_result

        if not articles:
            return ''

        valid_articles = [
            item for item in articles
            if isinstance(item, dict) and item.get('headline') and item.get('url')
        ]
        if not valid_articles:
            return ''

        def _render_cards(items):
            return ''.join(
                f'<a href="{normalize_result_url(item["url"])}" target="_blank" rel="noopener" class="news-card">'
                f'<div class="news-card-headline">{item["headline"]}</div>'
                f'<div class="news-card-meta">View article \u2192</div>'
                f'</a>'
                for item in items
            )

        # Render news inside a collapsible section that matches other card blocks
        # Show up to 10 articles when expanded
        top_articles = valid_articles[:10]
        top_items_html = _render_cards(top_articles)

        toggle_id = f"news_toggle_{int(time.time() * 1000)}"

        # Button shows/hides the whole news content (keeps inline-js simple to avoid f-string braces)
        toggle_button = (
            f"<button type='button' class='section-toggle' id='btn_{toggle_id}' "
            f"onclick=\"var c=document.getElementById('{toggle_id}'); var b=document.getElementById('btn_{toggle_id}'); var show=c.style.display==='none'; c.style.display=show?'block':'none'; b.textContent=show?'Hide ▴':'Show more ▾';\">"
            f"Show more ▾"
            f"</button>"
        )

        header_html = (
            f"<div style='display:flex;align-items:center;justify-content:space-between;gap:12px;'>"
            f"<b>Recent News</b>"
            f"{toggle_button}"
            f"</div>"
        )

        return (
            f"<div class='news-section'>"
            f"{header_html}"
            f"<div id='{toggle_id}' style='display:none;margin-top:0.6rem;' class='news-full-content'>"
            f"{top_items_html}"
            f"</div>"
            f"</div>"
        )

    def _format_recommendations(self, recommendations: Dict[str, Any]) -> str:
        """Format recommendations section"""
        if not isinstance(recommendations, dict):
            return ''

        short = recommendations.get('short_term') or {}
        medium = recommendations.get('medium_term') or {}
        long = recommendations.get('long_term') or {}
        fundamental = recommendations.get('fundamental') or {}
        technical = recommendations.get('technical') or {}
        sentiment = recommendations.get('sentiment') or {}
        
        # Extract fundamental, technical, and sentiment summaries
        fund_summary = str(fundamental.get('summary', '') or '')
        tech_summary = str(technical.get('summary', '') or '')
        sentiment_summary = str(sentiment.get('summary', '') or '')
        
        # Parse short-term summary (technical + sentiment)
        short_summary = str(short.get('summary', '') or '')
        short_tech = ''
        short_sentiment = ''
        
        if '|' in short_summary:
            short_parts = self._parse_summary_sections(short_summary)
            short_tech = short_parts.get('technical', '')
            short_sentiment = short_parts.get('sentiment', '')

        short_tech = self._clean_reason_summary(short_tech or short_summary, 'technical')
        short_sentiment = self._clean_reason_summary(short_sentiment, 'sentiment')
        
        # Parse medium-term summary (fundamental + technical + sentiment)
        medium_summary = str(medium.get('summary', '') or '')
        medium_fund = ''
        medium_tech = ''
        medium_sentiment = ''
        
        if '|' in medium_summary:
            medium_parts = self._parse_summary_sections(medium_summary)
            medium_fund = medium_parts.get('fundamental', '')
            medium_tech = medium_parts.get('technical', '')
            medium_sentiment = medium_parts.get('sentiment', '')

        if not (medium_fund or medium_tech or medium_sentiment) and medium_summary:
            medium_tech = medium_summary

        medium_fund = self._clean_reason_summary(medium_fund, 'fundamental')
        medium_tech = self._clean_reason_summary(medium_tech, 'technical')
        medium_sentiment = self._clean_reason_summary(medium_sentiment, 'sentiment')
        
        # Parse long-term summary (fundamental + technical + sentiment)
        long_summary = str(long.get('summary', '') or '')
        long_fund = ''
        long_tech = ''
        long_sentiment = ''
        
        if '|' in long_summary:
            long_parts = self._parse_summary_sections(long_summary)
            long_fund = long_parts.get('fundamental', '')
            long_tech = long_parts.get('technical', '')
            long_sentiment = long_parts.get('sentiment', '')

        if not (long_fund or long_tech or long_sentiment) and long_summary:
            long_tech = long_summary

        long_fund = self._clean_reason_summary(long_fund, 'fundamental')
        long_tech = self._clean_reason_summary(long_tech, 'technical')
        long_sentiment = self._clean_reason_summary(long_sentiment, 'sentiment')
        
        blocks = [
            self.expand_block(
                'Short-term (1 week)',
                short.get('label', 'N/A'),
                self.heatmap(short.get('label', 'N/A')),
                '',  # bullets placeholder
                1,
                fundamental_summary='',
                technical_summary=short_tech,
                sentiment_summary=short_sentiment
            ),
            self.expand_block(
                'Medium-term (3 months)',
                medium.get('label', 'N/A'),
                self.heatmap(medium.get('label', 'N/A')),
                '',  # bullets placeholder
                2,
                fundamental_summary=medium_fund,
                technical_summary=medium_tech,
                sentiment_summary=medium_sentiment
            ),
            self.expand_block(
                'Long-term (6-12 months)',
                long.get('label', 'N/A'),
                self.heatmap(long.get('label', 'N/A')),
                '',  # bullets placeholder
                3,
                fundamental_summary=long_fund,
                technical_summary=long_tech,
                sentiment_summary=long_sentiment  # Only show if explicitly in long-term summary (not fallback)
            )
        ]

        risk_note = (
            "<div class='horizon-risk-note'>"
            "Signals can change quickly after earnings releases, guidance updates, and macro shocks."
            "</div>"
        )

        # No preview text when collapsed — only the section title and the Show more toggle
        preview_html = ''

        full_html = ''.join(blocks)

        toggle_id = f"rec_toggle_{int(time.time() * 1000)}"

        # Use a simple inline JS toggle without braces to avoid f-string escaping pitfalls
        # Use the same small 'Show more' style as other sections and a down-arrow
        toggle_button = (
            f"<button type='button' class='section-toggle' id='btn_{toggle_id}' "
            f"onclick=\"var c=document.getElementById('{toggle_id}'); var b=document.getElementById('btn_{toggle_id}'); var show=c.style.display==='none'; c.style.display=show?'block':'none'; b.textContent=show?'Hide ▴':'Show more ▾';\">"
            f"Show more ▾"
            f"</button>"
        )

        header_html = (
            f"<div style='display:flex;align-items:center;justify-content:space-between;gap:12px;'>"
            f"<div class='rec-section-title'>Time Horizon Recommendations</div>"
            f"{toggle_button}"
            f"</div>"
        )

        return (
            "<div class='rec-section'>"
            f"{header_html}"
            f"<div id='{toggle_id}' style='display:none;margin-top:0.6rem;' class='rec-full-content'>"
            f"{full_html}"
            f"{risk_note}"
            f"</div>"
            "</div>"
        )

    @staticmethod
    def format_earnings_html(ticker: str, data: Dict) -> str:
        """Format earnings data as HTML table"""
        html = f"<b>Earnings for {ticker}:</b><br>"
        
        # Next earnings
        next_earnings = data.get('next_earnings')
        if next_earnings:
            html += "<b>Next Earnings Event:</b><ul>"
            for k, v in next_earnings.items():
                html += f"<li><b>{k}:</b> {v}</li>"
            html += "</ul>"
        
        # Earnings history
        earnings_history = data.get('earnings_history', [])
        if earnings_history:
            columns = list(earnings_history[0].keys())
            date_col = 'date' if 'date' in columns else columns[0]
            
            html += "<b>Recent Earnings History:</b>"
            html += '<table border="1" style="border-collapse:collapse;margin-top:10px;"><thead><tr>'
            for col in columns:
                html += f"<th style='padding:8px;background:#f3f4f6;'>{col}</th>"
            html += "</tr></thead><tbody>"
            
            for record in earnings_history[:5]:
                html += "<tr>"
                for col in columns:
                    html += f"<td style='padding:8px;'>{record.get(col, '')}</td>"
                html += "</tr>"
            
            html += "</tbody></table>"
        
        return html

    @staticmethod
    def format_comparison_price(quote: Any) -> str:
        """Format price text for comparison table, handling multiple quote shapes."""
        if not isinstance(quote, dict):
            return 'N/A'

        qdata = quote.get('data') if isinstance(quote.get('data'), dict) else quote
        if not isinstance(qdata, dict):
            return 'N/A'

        raw_price = qdata.get('price')
        if raw_price is None:
            raw_price = qdata.get('currentPrice')

        currency = qdata.get('currency', '')
        try:
            price_val = float(raw_price)
            if currency:
                return f"${price_val:,.2f} {currency}"
            return f"${price_val:,.2f}"
        except Exception:
            return str(raw_price) if raw_price not in (None, '') else 'N/A'

    def format_stock_comparison(self, analyses: List[Any]) -> str:
        """Build a side-by-side stock comparison HTML block."""
        cards = []
        rows = []

        for analysis in analyses[:2]:
            card_html = self.format_analysis_html(analysis)
            cards.append(f"<div class='comparison-card'>{card_html}</div>")

            recs = getattr(analysis, 'recommendations', {}) or {}
            short = recs.get('short_term', {}) or {}
            medium = recs.get('medium_term', {}) or {}
            long_ = recs.get('long_term', {}) or {}
            price_text = self.format_comparison_price(getattr(analysis, 'quote', None))
            rows.append(
                "<tr>"
                f"<td><b>{getattr(analysis, 'ticker', 'N/A')}</b></td>"
                f"<td>{getattr(analysis, 'company_name', 'N/A')}</td>"
                f"<td>{price_text}</td>"
                f"<td>{short.get('label', 'N/A')}</td>"
                f"<td>{medium.get('label', 'N/A')}</td>"
                f"<td>{long_.get('label', 'N/A')}</td>"
                "</tr>"
            )

        return (
            "<div class='comparison-section stock-card'>"
            "<div class='stock-card-header'>"
            "<div>"
            "<div class='stock-name'>Stock Comparison</div>"
            "<div class='stock-price-line'>Side-by-side analysis of the requested stocks.</div>"
            "</div>"
            "</div>"
            "<div class='comparison-summary'>"
            "<table class='comparison-table'>"
            "<thead><tr><th>Ticker</th><th>Company</th><th>Price</th><th>Short</th><th>Medium</th><th>Long</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody>"
            "</table>"
            "</div>"
            f"<div class='comparison-grid'>{''.join(cards)}</div>"
            "</div>"
        )

    def build_analysis_fallback_html(self, result_data: Dict, ticker: str) -> str:
        """Build minimal analysis card when richer rendering is unavailable."""
        recs = result_data.get("recommendations", {}) or {}
        price = result_data.get("price")
        currency = result_data.get("currency", "USD")
        company = result_data.get("company_name", ticker)

        def _badge(label: str) -> str:
            label_u = (label or "N/A").upper()
            class_map = {
                "STRONG BUY": "badge-strong-buy",
                "BUY": "badge-buy",
                "HOLD": "badge-hold",
                "SELL": "badge-sell",
            }
            icon_map = {
                "STRONG BUY": "▲▲",
                "BUY": "▲",
                "HOLD": "◆",
                "SELL": "▼",
            }
            css_class = class_map.get(label_u, "badge-na")
            icon = icon_map.get(label_u, "—")
            return f"<span class='badge {css_class}'>{icon} {label_u}</span>"

        def _row(title: str, data: Dict) -> str:
            label = data.get("label") or "N/A"
            summary = data.get("summary") or "No summary available"
            return (
                f"<div class='rec-row'>"
                f"<div>"
                f"<div class='rec-label'>{title}</div>"
                f"<div class='stock-price-line'>{summary}</div>"
                f"</div>"
                f"{_badge(label)}"
                f"</div>"
            )

        price_text = "N/A"
        if isinstance(price, (int, float)):
            price_text = f"${price:,.2f} {currency}"

        ownership = result_data.get("ownership", {})
        ownership_html = ""
        if ownership and 'institutional' in ownership:
            inst = ownership.get('institutional', 'N/A')
            retail = ownership.get('retail', 'N/A')
            insider = ownership.get('insider', 'N/A')
            ownership_html = f"<div class='ownership-section' style='margin-bottom:10px;'><b>Ownership Breakdown:</b> Institutional: {inst} | Retail: {retail} | Insider: {insider}</div>"

        return (
            f"<div class='analysis-block stock-card' data-ticker='{ticker}'>"
            f"<div class='stock-card-header'>"
            f"<div>"
            f"<div class='stock-name'>{company}<span class='stock-ticker-badge'>{ticker}</span></div>"
            f"<div class='stock-price-line'>{price_text}</div>"
            f"</div>"
            f"</div>"
            f"{ownership_html}"
            f"<div class='rec-section'>"
            f"<div class='rec-section-title'>Time Horizon Recommendations</div>"
            f"{_row('Short-term (1 week)', recs.get('short_term', {}) or {})}"
            f"{_row('Medium-term (3 months)', recs.get('medium_term', {}) or {})}"
            f"{_row('Long-term (6-12 months)', recs.get('long_term', {}) or {})}"
            f"</div>"
            f"</div>"
        )

    def ensure_analysis_markup(self, result_data: Dict, ticker: str, analysis_html: str) -> str:
        """Regenerate analysis HTML if a partial renderer dropped required card markup."""
        if analysis_html and "badge-" in analysis_html and "rec-section-title" in analysis_html:
            return analysis_html

        try:
            class _AnalysisFallback:
                pass

            analysis = _AnalysisFallback()
            analysis.ticker = ticker
            analysis.company_name = result_data.get("company_name", ticker)
            analysis.quote = {
                "data": {
                    "price": result_data.get("price"),
                    "currency": result_data.get("currency", "USD"),
                    "name": result_data.get("company_name", ticker),
                }
            }
            analysis.recommendations = result_data.get("recommendations", {}) or {}
            analysis.news = result_data.get("news", {"news": []})
            analysis.price_history = result_data.get("price_history", {"dates": [], "prices": []})
            analysis.ownership = result_data.get("ownership", {}) or {}
            analysis.insiders = result_data.get("insiders", []) or []
            analysis.dividends = result_data.get("dividends", []) or []
            analysis.peers = result_data.get("peers", []) or []

            rendered = self.format_analysis_html(analysis)
            if rendered and "badge-" in rendered and "rec-section-title" in rendered:
                return rendered
        except Exception:
            pass

        fallback = self.build_analysis_fallback_html(result_data, ticker)
        if fallback and "stock-card" in fallback:
            return fallback
        return analysis_html

    @staticmethod
    def append_citations_html(reply: str, citations: List[Dict[str, str]]) -> str:
        """Append unique clickable citations to the reply if available."""
        if not citations:
            return reply

        seen = set()
        unique: List[Dict[str, str]] = []
        for item in citations:
            url = normalize_result_url((item.get("url") or "").strip())
            if not url or url in seen:
                continue
            seen.add(url)
            title = (item.get('title') or item.get('headline') or url)
            unique.append({"url": url, "title": title})

        if not unique:
            return reply

        parts = ['<div class="citations"><b>Sources:</b><ul>']
        for u in unique:
            parts.append(f'<li><a href="{u["url"]}" target="_blank" rel="noopener">{u["title"]}</a></li>')
        parts.append('</ul></div>')

        return reply + ''.join(parts)
