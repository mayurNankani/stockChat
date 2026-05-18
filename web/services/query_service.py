"""Query Service
Business logic for handling different types of user queries.

Modification: Web search now anchors to the primary company (first
analysis in session) to maintain consistent linkage, even when other
companies are mentioned in follow-ups.
"""

import re
from flask import session
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, List, Optional
from repositories.stock_repository import IStockRepository
from services.llm_service import LLMService
from services.formatting_service import FormattingService
from src.tools.article_scraper import fetch_article_text
from src.tools.web_search import ddg_search, normalize_result_url


_COMPARISON_SKIP_WORDS = {
    'a', 'an', 'and', 'or', 'the', 'to', 'vs', 'vs.', 'versus', 'compare', 'comparison',
    'better', 'worse', 'than', 'with', 'between', 'against', 'for', 'of', 'in', 'on',
    'is', 'are', 'was', 'were', 'do', 'does', 'did', 'should', 'would', 'could', 'may',
    'i', 'me', 'my', 'you', 'your', 'we', 'our', 'they', 'their', 'it', 'this', 'that',
    'please', 'show', 'tell', 'ask', 'full', 'analysis', 'report', 'stock', 'stocks',
}


class QueryService:
    """
    Handles various query types: followups, earnings, news, comparisons
    Implements query parsing and LLM interaction logic
    """
    
    def __init__(
        self,
        repository: IStockRepository,
        llm_service: LLMService,
        formatting_service: FormattingService
    ):
        self.repository = repository
        self.llm = llm_service
        self.formatter = formatting_service
    
    def handle_followup(
        self,
        user_message: str,
        context: str,
        model_key: str,
        current_ticker: str = ''
    ) -> str:
        """
        Handle follow-up questions about previous analysis
        Uses parallel LLM + web search with confidence-based selection
        
        Args:
            user_message: User's question
            context: Previous analysis HTML
            model_key: LLM model to use
            
        Returns:
            Response text (may include HTML)
        """
        # Check for contradictions in buy/sell questions
        contradiction_response = self._check_contradictions(user_message, context)
        if contradiction_response:
            return contradiction_response
        
        # Check for additional stock comparisons
        additional_data = self._detect_and_fetch_additional_stocks(user_message, context, model_key, current_ticker)
        
        # Build enhanced context
        enhanced_context = context
        instruction_suffix = ""
        
        if additional_data:
            enhanced_context += "\n\n<b>Additional Stock Data (for comparison):</b><br>" + additional_data
            instruction_suffix = (
                "\n\nIMPORTANT: I have fetched REAL DATA for the additional stock mentioned in the question. "
                "This data is shown in the 'Additional Stock Data' section above. "
                "USE THIS DATA DIRECTLY in your answer - do NOT suggest the user look it up elsewhere. "
                "Extract the specific metrics requested (PE ratio, price, market cap, etc.) from the data provided "
                "and present them clearly in your response."
            )
        
        # Run LLM and web search in parallel
        # Capture primary identifier from session BEFORE threads (avoid request context use inside worker)
        primary_ticker = session.get('primary_ticker')
        primary_company_name = session.get('primary_company_name')

        with ThreadPoolExecutor(max_workers=2) as executor:
            llm_future = executor.submit(
                self._get_llm_response,
                user_message,
                enhanced_context,
                instruction_suffix,
                model_key,
                primary_ticker or '',
                primary_company_name or ''
            )
            web_future = executor.submit(
                self._get_web_search_response,
                user_message,
                context,
                primary_ticker,
                primary_company_name,
            )

            try:
                llm_response = llm_future.result(timeout=45)
            except Exception as exc:
                print(f"[WARN] LLM future failed: {exc}")
                llm_response = {'response': 'The analysis model timed out or encountered an error. Please try again.', 'confidence': 'LOW'}

            try:
                web_results = web_future.result(timeout=15)
            except Exception as exc:
                print(f"[WARN] Web search future failed: {exc}")
                web_results = {'results': [], 'query': user_message}
        
        # Determine confidence and choose response
        return self._select_best_response(llm_response, web_results, model_key)
    
    def _get_llm_response(
        self,
        user_message: str,
        context: str,
        instruction_suffix: str,
        model_key: str,
        primary_ticker: str = '',
        primary_company_name: str = ''
    ) -> Dict[str, Any]:
        """Get LLM response with confidence assessment"""
        stock_identity = ''
        if primary_ticker or primary_company_name:
            name = primary_company_name or primary_ticker
            ticker = primary_ticker or ''
            stock_identity = f"The primary stock being discussed is {name} (ticker: {ticker}). Always refer to it by name, never as 'the discussed stock' or 'the company'.\n\n"
        prompt = (
            f"{stock_identity}"
            f"Here is the stock analysis context for reference (from yfinance and internal agents):\n{context}\n\n"
            f"Now answer the user's question: {user_message}\n\n"
            f"FORMATTING INSTRUCTIONS - Use HTML for proper display:\n"
            f"- Use <b>text</b> for bold important terms\n"
            f"- Use <br> for line breaks between paragraphs\n"
            f"- When listing multiple points, use proper HTML lists:\n"
            f"  * For bullet points: <ul><li>First point</li><li>Second point</li></ul>\n"
            f"  * For numbered lists: <ol><li>First</li><li>Second</li></ol>\n"
            f"- DO NOT use plain text bullets like '•', '-', or '*' - always use HTML <ul><li> tags\n"
            f"- For paragraphs, just use regular text with <br> between them\n"
            f"- Keep your response natural - use lists when appropriate, paragraphs when better\n"
            f"\nIMPORTANT: At the end of your response, add a confidence score on a new line:\n"
            f"CONFIDENCE: [HIGH/MEDIUM/LOW]\n"
            f"- HIGH: You have specific data from the context to answer completely\n"
            f"- MEDIUM: You can partially answer but some info might be missing\n"
            f"- LOW: The context doesn't contain enough information to answer well\n"
            f"{instruction_suffix}"
        )
        
        response = self.llm.generate(prompt, model_key)
        
        # Extract confidence level
        confidence_match = re.search(r'CONFIDENCE:\s*(HIGH|MEDIUM|LOW)', response, re.IGNORECASE)
        confidence = confidence_match.group(1).upper() if confidence_match else 'MEDIUM'
        
        # Remove confidence marker from response
        clean_response = re.sub(r'\n?CONFIDENCE:\s*(HIGH|MEDIUM|LOW)\n?', '', response, flags=re.IGNORECASE)
        
        return {
            'response': clean_response.strip(),
            'confidence': confidence
        }
    
    def _get_web_search_response(self, user_message: str, context: str, primary_ticker: str | None, primary_company_name: str | None) -> Dict[str, Any]:
        """Get web search results for the question.

        Args:
            user_message: The follow-up question text.
            context: Stored HTML analysis context.
            primary_ticker: Captured outside thread (may be None).
            primary_company_name: Captured outside thread (may be None).
        """
        # Fallback to first analysis block if primary missing
        if not primary_ticker:
            tickers = re.findall(r'data-ticker="([^\"]+)"', context)
            primary_ticker = tickers[0] if tickers else ''
        base_term = (primary_company_name or '').strip() or primary_ticker or ''

        # Build search anchored to primary company only (do NOT override with other mentioned tickers)
        search_query = f"{base_term} {user_message}".strip() if base_term else user_message
        
        try:
            results = ddg_search(search_query, max_results=3)
            return {
                'results': results,
                'query': search_query
            }
        except Exception as e:
            print(f"Web search failed: {e}")
            return {'results': [], 'query': search_query}
    
    def _select_best_response(
        self,
        llm_result: Dict[str, Any],
        web_result: Dict[str, Any],
        model_key: str
    ) -> str:
        """
        Select best response based on LLM confidence
        
        Args:
            llm_result: LLM response with confidence
            web_result: Web search results
            model_key: Model key for summarization
            
        Returns:
            Final response to user
        """
        confidence = llm_result.get('confidence', 'MEDIUM')
        llm_response = llm_result.get('response', '')
        web_results = web_result.get('results', [])
        
        # If high confidence, use LLM response
        if confidence == 'HIGH':
            return llm_response
        
        # If medium confidence and no web results, use LLM
        if confidence == 'MEDIUM' and not web_results:
            return llm_response
        
        # If low confidence, provide web links without summarizing
        if confidence == 'LOW' and web_results:
            links_html = self._format_web_links(web_results)
            return (
                f"I don't have enough information in the current analysis to answer this confidently. "
                f"Here are some relevant sources you can check:<br><br>{links_html}"
            )
        
        # If medium confidence with web results, show both
        if confidence == 'MEDIUM' and web_results:
            links_html = self._format_web_links(web_results)
            return (
                f"{llm_response}<br><br>"
                f"<b>Related sources for more information:</b><br>{links_html}"
            )
        
        # Fallback to LLM response
        return llm_response
    
    def _format_web_links(self, results: List[Dict]) -> str:
        """Format web search results as clickable links without summarization"""
        if not results:
            return "No additional sources found."
        
        links = []
        for i, result in enumerate(results[:5], 1):
            title = result.get('title', 'Source')
            url = normalize_result_url(result.get('url', '#'))
            snippet = result.get('snippet', '')
            
            # Show snippet as preview without LLM summarization
            link_html = (
                f'{i}. <a href="{url}" target="_blank" style="color:#3b82f6;text-decoration:underline;">'
                f'<b>{title}</b></a><br>'
                f'<span style="color:#5a6c7d;font-size:0.9em;">{snippet[:150]}...</span>'
            )
            links.append(link_html)
        
        return '<br><br>'.join(links)
    
    def _check_contradictions(self, user_message: str, context: str) -> Optional[str]:
        """Check if user is asking about a contradictory recommendation"""
        try:
            requested_horizon = self._detect_horizon_from_message(user_message)
            stored_label = self._extract_label_for_horizon(context, requested_horizon)
            
            if stored_label:
                wants_sell = bool(re.search(
                    r"\bwhy\b.*\bsell\b|\bwhy is it a sell\b|\bwhy\s+sell\b|\bwhy.*\b(so )?sell\b",
                    user_message,
                    re.IGNORECASE
                ))
                wants_buy = bool(re.search(
                    r"\bwhy\b.*\bbuy\b|\bwhy is it a buy\b|\bwhy\s+buy\b|\bwhy.*\b(so )?buy\b",
                    user_message,
                    re.IGNORECASE
                ))
                
                if wants_sell and 'SELL' not in stored_label:
                    return (
                        f"The previous analysis rated the {requested_horizon} horizon as '<b>{stored_label}</b>'. "
                        f"I can't explain it as a 'sell' because the stored recommendation is {stored_label}. "
                        f"Would you like me to re-evaluate the stock for the {requested_horizon} horizon?"
                    )
                
                if wants_buy and ('BUY' not in stored_label and 'STRONG BUY' not in stored_label):
                    return (
                        f"The previous analysis rated the {requested_horizon} horizon as '<b>{stored_label}</b>'. "
                        f"I can't explain it as a 'buy' because the stored recommendation is {stored_label}. "
                        f"Would you like me to re-evaluate the stock for the {requested_horizon} horizon?"
                    )
        except Exception:
            pass
        
        return None
    
    def _extract_label_for_horizon(self, ctx: str, horizon: str) -> Optional[str]:
        """Extract recommendation label for given time horizon"""
        patterns = {
            'short': r"<b>Short-term.*?:\s*([^<]+)</b>",
            'medium': r"<b>Medium-term.*?:\s*([^<]+)</b>",
            'long': r"<b>Long-term.*?:\s*([^<]+)</b>"
        }
        pat = patterns.get(horizon)
        if not pat:
            return None
        
        m = re.search(pat, ctx, re.IGNORECASE)
        return m.group(1).strip().upper() if m else None
    
    def _detect_horizon_from_message(self, msg: str) -> str:
        """Detect time horizon from message"""
        msg = msg.lower()
        if 'short' in msg or '1 week' in msg or 'week' in msg:
            return 'short'
        if 'medium' in msg or '3 month' in msg or '3 months' in msg:
            return 'medium'
        if 'long' in msg or '6 month' in msg or '12 month' in msg:
            return 'long'
        return 'short'
    
    # Keywords that signal a comparison intent — only run Gemma if one of these is present
    _COMPARISON_SIGNALS = re.compile(
        r'\b(compare|vs\.?|versus|against|better than|worse than|compared to|'
        r'like|similar to|over|instead of|or)\b',
        re.IGNORECASE
    )

    def _detect_and_fetch_additional_stocks(
        self,
        user_message: str,
        context: str,
        model_key: str = 'gemma3',
        current_ticker: str = ''
    ) -> str:
        """Detect and fetch data for additional stocks mentioned in comparison queries.

        Uses Gemma locally to decide whether the question requests a comparison
        and which tickers to fetch, avoiding false positives from common words.
        Fetches each ticker's quote + info in parallel to minimise latency.
        """
        # Fast pre-filter: skip Gemma entirely if no comparison keywords are present
        if not self._COMPARISON_SIGNALS.search(user_message):
            return ''

        # Prefer the authoritative session ticker; fall back to parsing HTML
        if not current_ticker:
            all_matches = re.findall(r'data-ticker="([^\"]+)"', context)
            current_ticker = all_matches[0] if all_matches else ''
        print(f"[DEBUG] _detect_and_fetch_additional_stocks: current_ticker={current_ticker!r}")
        additional_tickers = self._extract_comparison_tickers(user_message, current_ticker, context)
        if not additional_tickers:
            additional_tickers = self._llm_extract_comparison_tickers(user_message, current_ticker, model_key)
        if not additional_tickers:
            return ''

        def _fetch_one(ticker: str) -> str:
            try:
                quote_result = self.repository.get_quote(ticker)
                if quote_result.get('status') != 'ok':
                    return ''
                quote_data = quote_result.get('data', {})
                info = self.repository.get_stock_info(ticker)

                pe_ratio = info.get('trailingPE', info.get('forwardPE', 'N/A'))
                market_cap = info.get('marketCap', 'N/A')
                if market_cap != 'N/A':
                    market_cap = f"${market_cap / 1e9:.2f}B" if market_cap >= 1e9 else f"${market_cap / 1e6:.2f}M"

                dividend_yield = info.get('dividendYield', 'N/A')
                if dividend_yield != 'N/A':
                    dividend_yield = f"{dividend_yield * 100:.2f}%"

                eps = info.get('trailingEps', 'N/A')
                revenue = info.get('totalRevenue', 'N/A')
                if revenue != 'N/A':
                    revenue = f"${revenue / 1e9:.2f}B" if revenue >= 1e9 else f"${revenue / 1e6:.2f}M"

                profit_margin = info.get('profitMargins', 'N/A')
                if profit_margin != 'N/A':
                    profit_margin = f"{profit_margin * 100:.2f}%"

                pe_display = (
                    f"<b style='font-size:1.1em;color:#2563eb;'>{pe_ratio:.2f}</b>"
                    if isinstance(pe_ratio, (int, float)) else pe_ratio
                )

                try:
                    ownership = self.repository.get_ownership_breakdown(ticker)
                    if ownership and 'institutional' in ownership:
                        inst = ownership.get('institutional', 'N/A')
                        retail = ownership.get('retail', 'N/A')
                        insider = ownership.get('insider', 'N/A')
                        ownership_str = f"Institutional: {inst} | Retail: {retail} | Insider: {insider}"
                    else:
                        ownership_str = "N/A"
                except Exception:
                    ownership_str = "N/A"
                return f"""
<div style="margin:15px 0;padding:15px;background:#f0f9ff;border-left:4px solid #3b82f6;border-radius:6px;box-shadow:0 2px 4px rgba(0,0,0,0.1);">
    <div style="font-size:1.1em;margin-bottom:10px;"><b>{info.get('longName', ticker)} ({ticker})</b></div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
        <div><b>Current Price:</b> ${quote_data.get('price', 'N/A')} {quote_data.get('currency', '')}</div>
        <div><b>P/E Ratio:</b> {pe_display}</div>
        <div><b>Market Cap:</b> {market_cap}</div>
        <div><b>EPS:</b> {eps if eps != 'N/A' else 'N/A'}</div>
        <div><b>Revenue:</b> {revenue}</div>
        <div><b>Profit Margin:</b> {profit_margin}</div>
        <div><b>Dividend Yield:</b> {dividend_yield}</div>
        <div style="grid-column: span 2;"><b>Ownership Breakdown:</b> {ownership_str}</div>
    </div>
</div>
"""
            except Exception as exc:
                print(f"Error fetching comparison data for {ticker}: {exc}")
                return ''

        with ThreadPoolExecutor(max_workers=min(len(additional_tickers), 4)) as pool:
            futures = {pool.submit(_fetch_one, t): t for t in additional_tickers}
            parts = []
            for future in futures:
                try:
                    html = future.result(timeout=15)
                    if html:
                        parts.append(html)
                except Exception as exc:
                    print(f"Comparison fetch timed out for {futures[future]}: {exc}")

        return ''.join(parts)

    def _extract_comparison_tickers(self, user_message: str, current_ticker: str, context: str) -> List[str]:
        """Deterministically extract comparison tickers from the query and context.

        This prefers explicit ticker-like tokens, then company-name lookups, and
        excludes the current ticker so follow-up comparisons only fetch the other
        stock(s) being compared.
        """
        candidates: List[str] = []
        seen = set()

        def _add_candidate(value: str):
            ticker = (value or '').upper().strip()
            if not ticker or ticker in seen or ticker in {'N/A', current_ticker}:
                return
            if re.fullmatch(r'[A-Z0-9\.^]{1,10}', ticker):
                candidates.append(ticker)
                seen.add(ticker)

        # 1) Explicit ticker-like tokens from the user message
        for token in re.findall(r'\b[A-Z0-9\.\^]{1,10}\b', user_message):
            token_u = token.upper().strip()
            if token_u.lower() in _COMPARISON_SKIP_WORDS:
                continue
            if re.fullmatch(r'[A-Z0-9]{1,6}(?:\.[A-Z]{1,2})?|\^[A-Z0-9]+', token_u):
                _add_candidate(token_u)

        # 2) Title-case company names / multi-word names from the message
        title_tokens = re.findall(r'\b(?:[A-Z][a-z0-9&]+(?:\s+[A-Z][a-z0-9&]+){0,2})\b', user_message)
        for phrase in title_tokens:
            phrase_l = phrase.lower().strip()
            if phrase_l in _COMPARISON_SKIP_WORDS:
                continue
            match = self.repository.search_company(phrase)
            if match and match.get('symbol'):
                _add_candidate(match['symbol'])

        # 3) If the message is a follow-up, allow context to contribute a second ticker
        context_tickers = re.findall(r'data-ticker="([^"]+)"', context)
        for ticker in context_tickers:
            _add_candidate(ticker)

        return candidates[:5]
    
    def _llm_extract_comparison_tickers(self, user_message: str, current_ticker: str, model_key: str) -> List[str]:
        """Ask Gemma (locally via Ollama) whether the follow-up question requests a
        stock comparison and, if so, which tickers to fetch.

        Returns a list of uppercase ticker symbols (excluding current_ticker),
        or an empty list if no comparison is intended.
        """
        prompt = (
            f"The user is currently viewing a stock analysis for ticker: {current_ticker}\n\n"
            f"User follow-up question: \"{user_message}\"\n\n"
            f"Task: Does the user explicitly ask to compare {current_ticker} with one or more OTHER specific companies or stocks?\n\n"
            f"Rules:\n"
            f"- Only return tickers for companies the user is clearly asking to compare against.\n"
            f"- Do NOT treat common English words or abbreviations (IT, AI, VS, US, PE, EPS, CEO, etc.) as ticker symbols.\n"
            f"- Do NOT return {current_ticker} itself.\n"
            f"- If the user is NOT asking for a comparison, respond with exactly: NONE\n"
            f"- If the user mentions a company by name (e.g. Apple, Google), convert it to its ticker symbol.\n\n"
            f"Respond with ONLY a comma-separated list of ticker symbols (e.g. AAPL,GOOGL) or the single word NONE. "
            f"No explanation, no punctuation, no markdown."
        )

        print(f"[LLM ticker extract] PROMPT:\n{prompt}")
        try:
            raw = self.llm.generate_raw(prompt, model_key).strip()
            print(f"[LLM ticker extract] RAW RESPONSE from {model_key}: '{raw}'")
            # Strip any markdown/extra whitespace the model may emit
            cleaned = re.sub(r'[`\n\r]', '', raw).strip()
            print(f"[LLM ticker extract] AFTER CLEAN: '{cleaned}'")
            if not cleaned or cleaned.upper() == 'NONE':
                print(f"[LLM ticker extract] → No comparison detected, returning []")
                return []
            tokens = [t.strip().upper() for t in cleaned.split(',')]
            valid = [
                t for t in tokens
                if re.match(r'^[A-Z]{1,5}$|^\^[A-Z0-9]+$', t) and t != current_ticker
            ]
            print(f"[LLM ticker extract] → Tokens={tokens} Valid={valid}")
            return valid[:5]
        except Exception as exc:
            print(f"[WARN] LLM ticker extraction failed: {exc}")
            return []
    
    def handle_earnings_query(self, ticker: str) -> str:
        """Handle earnings-specific queries"""
        earnings_result = self.repository.get_earnings(ticker)
        
        if earnings_result.get('status') != 'ok':
            return f"Could not fetch earnings for {ticker}."
        
        return self.formatter.format_earnings_html(ticker, earnings_result['data'])
    
    def handle_news_article(self, article: Dict[str, Any], model_key: str) -> str:
        """Handle news article summarization"""
        article_url = article.get('url', '')
        article_content = fetch_article_text(article_url) if article_url else ''
        
        article_text = (
            f"Headline: {article.get('headline', '')}\n"
            f"URL: {article_url}\n"
            f"Summary: {article.get('summary', '')}\n"
            f"Content: {article_content}"
        )
        
        prompt = (
            f"Here is a news article about a stock. Please summarize it in 2-3 sentences "
            f"for a general audience.\n{article_text}\n\n"
            f"IMPORTANT: Format your response using HTML:\n"
            f"- Use <b>text</b> for important terms\n"
            f"- Use <br> for line breaks\n"
            f"- Do NOT use markdown or plain text formatting\n"
            f"If you don't have enough information, say so."
        )
        
        return self.llm.generate(prompt, model_key)
    
    @staticmethod
    def extract_ticker_from_context(context: str, history: List) -> Optional[str]:
        """Extract ticker symbol from analysis context or history"""
        # Try to extract from data-ticker attribute in HTML
        match = re.search(r'data-ticker="([^"]+)"', context)
        if match:
            return match.group(1)
        
        # Try to find ticker pattern in history
        for msg in reversed(history):
            content = msg.get('content', '')
            ticker_match = re.search(r'\b([A-Z]{1,5})\b', content)
            if ticker_match:
                return ticker_match.group(1)
        
        return None
    
    @staticmethod
    def find_matching_article(user_message: str, news_articles: List[Dict]) -> Optional[Dict]:
        """Find a matching news article for user's query.

        Matching strategy:
        1. Index-based ("first article", "2nd news", etc.)
        2. Direct keyword overlap between query tokens and (headline+summary)
           if the user references news/article/headline or includes deal/merger
        3. Require minimum overlap to avoid false positives on generic questions.
        """
        if not news_articles:
            return None

        msg_lower = user_message.lower()

        # Exclude broad business model questions
        business_question_patterns = [
            r'\bwhat (does|do|is)\b.*\b(company|business|they|it)\b.*\bdo\b',
            r'\b(describe|explain|tell me about)\b.*\b(business|company|products|services)\b',
            r'\bwhat (are|is) (their|its)\b.*\b(product|service|business)\b',
            r'\bhow (does|do)\b.*\b(make money|earn|revenue|operate)\b',
        ]
        if any(re.search(p, msg_lower) for p in business_question_patterns):
            return None

        # Index-based matching
        idx_match = re.search(r'(first|second|third|fourth|fifth|[0-9]+)[^\w]*(news|article|headline|story)', msg_lower)
        if idx_match:
            idx_map = {'first': 0, 'second': 1, 'third': 2, 'fourth': 3, 'fifth': 4}
            raw = idx_match.group(1).lower()
            idx = idx_map.get(raw)
            if idx is None:
                try:
                    idx = int(raw) - 1
                except ValueError:
                    idx = None
            if idx is not None and 0 <= idx < len(news_articles):
                return news_articles[idx]

        # Determine if user is referencing news generally
        news_intent_terms = {'news', 'article', 'headline', 'story', 'press', 'report', 'deal', 'acquisition', 'merger', 'agreement'}
        has_news_intent = any(t in msg_lower for t in news_intent_terms)
        if not has_news_intent:
            return None

        # Tokenize user query (simple split, remove stopwords)
        stopwords = {
            'the','a','an','and','or','of','in','on','for','with','about','is','to','this','that','what','does','do','tell','me','show','latest','recent','deal','headline','news','article','story'
        }
        query_tokens = [t for t in re.findall(r'[a-z0-9]+', msg_lower) if t not in stopwords]
        if not query_tokens:
            return None

        best_article = None
        best_overlap = 0.0

        for art in news_articles:
            text = ' '.join([
                (art.get('headline') or '').lower(),
                (art.get('summary') or '').lower()
            ])
            article_tokens = set(re.findall(r'[a-z0-9]+', text))
            overlap = len([t for t in query_tokens if t in article_tokens])
            if overlap == 0:
                continue
            overlap_ratio = overlap / max(len(query_tokens), 1)
            # Require at least 2 tokens or >=30% of query tokens
            if overlap >= 2 or overlap_ratio >= 0.3:
                if overlap_ratio > best_overlap:
                    best_overlap = overlap_ratio
                    best_article = art

        return best_article
