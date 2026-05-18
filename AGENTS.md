# AGENTS.md — Contributor & AI Agent Guide

Last updated: 2026-05-17 — Commit-ready

This file describes the project structure, agent roles, key conventions, and important rules for human contributors and AI coding agents working on this codebase.

---

## Project Purpose

**tickerTalk** is a conversational stock-market analysis assistant. Users type a company name or ticker; the system resolves the ticker, fetches market data and news, runs multi-horizon (short/medium/long) recommendations, and maintains a follow-up chat context within the browser session.

---

## Repository Layout

```
stockMarketAgent/
├── core/                        # Pure domain — no I/O, no HTTP
│   ├── models/                  # Dataclasses (StockQuote, PriceHistory, NewsArticle, …)
│   └── analysis/
│       └── recommendation_engine.py  # Weighted scoring & rating thresholds
│
├── adapters/                    # One concrete adapter per integration
│   ├── market_data/             # YahooFinanceAdapter  (quotes, price history)
│   ├── news/                    # FinnhubNewsAdapter   (company news)
│   ├── sentiment/               # FinbertSentimentAdapter (FinBERT NLP)
│   └── company_lookup/          # YahooCompanyLookupAdapter (ticker resolution)
│
├── application/
│   └── use_cases/
│       └── run_stock_analysis.py  # StockAnalysisUseCase — orchestrates everything
│
├── src/                         # Legacy tooling (partially migrated)
│   ├── agent_improved.py        # StockAnalysisAgentImproved — fundamental/technical/sentiment scoring
│   └── tools/                   # Atomic tools (kept for backwards-compat)
│       ├── company_search.py
│       ├── fundamental_analysis.py
│       ├── technical_analysis.py
│       ├── finnhub_news.py
│       ├── sentiment_analysis.py  # FinBERT wrapper (MPS/CUDA/CPU auto-select)
│       ├── web_search.py          # DuckDuckGo search helper
│       └── article_scraper.py     # Full article text fetcher
│
├── web/                         # Flask presentation layer
│   ├── app.py                   # Application factory (create_app)
│   ├── index.html               # Single-page UI (vanilla JS + Chart.js)
│   ├── config/                  # Config object (API keys, LLM provider)
│   ├── models/                  # Web-layer dataclasses (StockAnalysis, CompanyMatch)
│   ├── prompts/
│   │   └── agent_system.txt     # Agent system prompt template ({tool_descriptions} placeholder)
│   ├── repositories/
│   │   └── stock_repository.py  # IStockRepository + StockRepository (adapter-backed)
│   ├── routes/
│   │   ├── stock_routes.py      # / and /chat endpoints
│   │   └── api_routes.py        # /api/price-history endpoint
│   └── services/
│       ├── agent_service.py     # AgentService — prompt-based agentic loop (tool call parser)
│       ├── agent_tools.py       # TOOL_SCHEMAS + ToolExecutor (7 tools)
│       ├── stock_service.py     # StockAnalysisService — ticker resolution + analysis
│       ├── formatting_service.py # HTML builder for analysis output
│       └── llm_service.py       # Ollama / Gemini LLM abstraction
│
├── config/
│   └── .env.example             # Template for required environment variables
├── wsgi.py                      # Production WSGI entry point (gunicorn)
├── gunicorn.conf.py             # Gunicorn settings (workers, timeout, bind)
├── pyproject.toml               # black, isort, ruff, mypy config
└── requirements.txt             # Python dependencies (includes gunicorn)
```

---

## Agents & Their Roles

### 1 `AgentService` (`web/services/agent_service.py`)
The agentic loop orchestrator — the primary entry point for all chat turns.
- Loads system prompt from `web/prompts/agent_system.txt` at startup.
- Builds a `[SYSTEM]/[User]/[Assistant]` prompt and calls `LLMService.generate_raw()`.
- Parses `<tool_call>` blocks (also handles ` ```tool_call``` ` code-fence variant) via regex.
- Runs up to `MAX_TOOL_ITERATIONS = 5` tool calls per turn before forcing a final answer.
- Injects ticker hints (`_build_ticker_hint`) and corrects mangled tickers (`_correct_ticker_arg`) before tool execution.
- Delegates HTML rendering to `FormattingService` via the pre-rendered `analysis_html` field from `run_full_analysis`.
- If an analysis-style request returns plain text without tool calls, the service now forces `resolve_ticker` + `run_full_analysis` so the chart and heatmap still appear.
- Guards general company-info questions so `run_full_analysis` is skipped unless recommendation intent is explicit.
- Rewrites repetitive generic follow-up prompts into context-aware prompts based on user question type.
- Collects citations from `get_news` and `web_search` tool outputs and appends clickable source links to replies.

### 2 `ToolExecutor` (`web/services/agent_tools.py`)
Executes the 7 named tools the LLM can call:

| Tool | Purpose |
|------|---------|
| `resolve_ticker` | Converts company name/ticker to a validated ticker symbol |
| `run_full_analysis` | Runs complete multi-horizon analysis; renders full HTML card |
| `get_stock_snapshot` | Quick live price/metrics (P/E, market cap, 52-week range) |
| `get_news` | Fetches latest Finnhub news for a ticker |
| `get_price_history` | Fetches price history for charting |
| `get_earnings` | Fetches next/recent earnings dates and EPS |
| `web_search` | DuckDuckGo web search anchored to the session company |

`resolve_ticker` validates ticker-like inputs (`[A-Z0-9]{1,6}`) directly via `get_quote()` before falling back to fuzzy `search_company()`.

### 3 `StockAnalysisAgentImproved` (`src/agent_improved.py`)
The scoring brain called by `StockAnalysisUseCase`. Computes:
- **`get_fundamental_recommendation(analysis)`** — valuation, growth, profitability, health; sector-adjusted weights.
- **`get_technical_recommendation(analysis)`** — RSI, MACD, ADX, Bollinger Bands, SMAs, MFI, ATR.
- `_get_sentiment_recommendation(ticker)` — delegates to FinBERT.
- **`get_recommendation(ticker)`** — assembles `short_term`, `medium_term`, `long_term` dicts.

### 4 `StockAnalysisUseCase` (`application/use_cases/run_stock_analysis.py`)
Orchestrator for the scoring pipeline. Calls the legacy agent and all adapters, then delegates final scoring to `recommendation_engine.py`. Returns a `presentation` dict with `quote`, `recommendation_report`, and `legacy_components`.

### 5 `StockAnalysisService` (`web/services/stock_service.py`)
Web-layer bridge:
- Ticker resolution (`find_ticker` / `_try_ticker_tokens` / `_search_company`)
- Calling `StockAnalysisUseCase.run(ticker)`
- Re-hydrating legacy `short_term` / `medium_term` / `long_term` keys from the unified report

### 6 `FormattingService` (`web/services/formatting_service.py`)
Stateless HTML builder. `format_analysis_html(analysis)` produces the full card with:
- Company logo (Finnhub logo API)
- Current price + timestamp
- 30-day Chart.js chart (toggle, period buttons)
- Color-coded heatmap badges (STRONG BUY / BUY / HOLD / SELL)
- Expandable fundamental / technical / sentiment sections
- Recent news links (5 shown by default, with a "View all news (N)" toggle for additional items)

Card section order is: header -> chart/performance -> time-horizon recommendations -> news.

Every top-level analysis block emits a `<div class='analysis-block' data-ticker='TICKER'>` wrapper — this is the reliable source of truth for the current ticker in follow-up sessions.
- The formatter now fails open on partial data, which prevents one malformed field from stripping the whole card.

### 7 `LLMService` (`web/services/llm_service.py`)
Abstracts Ollama and Gemini:
- `generate_raw(prompt, model_key)` — used by `AgentService`; returns plain text (no tool plumbing).
- `generate(prompt, model_key)` — returns cleaned HTML for direct rendering.
- Models configured in `web/config.py` `MODEL_MAP`.

---

## Key Conventions

### Ticker Resolution Order
1. Direct uppercase / ticker-like token → `get_quote()` validation (price must be non-null).
2. Token extraction from query string → per-token `get_quote()` validation.
3. `repository.search_company(query)` → `YahooCompanyLookupAdapter`.

Always validate a ticker by confirming `price is not None`; never trust a symbol alone.

### LLM Tool Call Format
Models that don't support native Ollama function-calling (gemma3, llama3) are instructed via the system prompt to output:

```
<tool_call>{"name": "tool_name", "args": {"param": "value"}}</tool_call>
```

`AgentService` also normalises the ` ```tool_call ... ``` ` code-fence variant some models emit.

### Ticker Hallucination Guard
Two layers prevent the LLM from mangling ticker symbols:
1. **Prompt hint** — `_build_ticker_hint(user_message)` injects a `[SYSTEM NOTE: exact strings: "CMCSA"]` line into the user turn before the LLM runs.
2. **Code correction** — `_correct_ticker_arg(args, user_message)` post-processes the parsed tool call: if the LLM's `company_name` is a substring of a token in the original message (e.g. `CMSA` ⊂ `CMCSA`), it is replaced with the longer token.

### Recommendation Weighting
Defined in `core/analysis/recommendation_engine.py` — edit `WEIGHTS` there only.

| Horizon | Fundamental | Technical | Sentiment |
|---------|------------|-----------|-----------|
| Short   | 0.00       | 0.80      | 0.20      |
| Medium  | 0.55       | 0.35      | 0.10      |
| Long    | 0.80       | 0.20      | 0.00      |

### Session Keys (Flask)
| Key | Set in | Used in |
|-----|--------|---------|
| `conversation_history` | `stock_routes.chat` | `AgentService.run()` |

⚠️ Session stores **plain text only** — no HTML blobs. `analysis_html` is generated fresh each request and never persisted in the session.

### Price History Intervals
| Period | yfinance interval | Date format |
|--------|------------------|-------------|
| `1d`   | `5m`             | `%Y-%m-%d %H:%M` |
| `5d`   | `15m`            | `%Y-%m-%d %H:%M` |
| `1mo`+ | `1d`             | `%Y-%m-%d` |

### Sentiment Model
FinBERT (`ProsusAI/finbert`) runs locally. Device selected at import: MPS → CUDA → CPU.

---

## Running Locally

```bash
# 1 — activate env
source .venv/bin/activate

# 2 — set secrets (copy .env.example → .env and fill in values)
cp config/.env.example .env
export FINNHUB_API_KEY=your_key_here

# 3 — start development server
python web/app.py
# → http://127.0.0.1:5001
```

## Running in Production

```bash
# Install gunicorn (already in requirements.txt)
pip install gunicorn

# Start with config file
gunicorn -c gunicorn.conf.py wsgi:app

# Or inline
gunicorn --workers 2 --timeout 120 --bind 0.0.0.0:5001 wsgi:app
```

---

## Adding a New Tool

1. Add a schema entry to `TOOL_SCHEMAS` in `web/services/tool_schemas.py`.
2. Add a handler method `_my_tool(self, args)` to `ToolExecutor`.
3. Register it in the `handlers` dict inside `execute()`.
4. The tool description is automatically injected into the system prompt at startup — no prompt edits needed.

## Adding a New Adapter

1. Create `adapters/<category>/my_adapter.py` implementing the relevant Protocol from `adapters/<category>/interface.py`.
2. Instantiate it in `StockRepository.__init__` and/or `StockAnalysisService.__init__`.
3. Update `StockAnalysisUseCase.__init__` if the use-case orchestration needs it.
4. Keep domain models pure — no library imports inside `core/`.

---

## What NOT to Change Without Review

- `core/models/` dataclass field names — downstream code unpacks them by name.
- `WEIGHTS` dict in `recommendation_engine.py` — changes affect all three horizons and both the legacy agent and unified use-case.
- `data-ticker` attribute emitted by `FormattingService` — JavaScript chart handlers depend on it.
- `find_matching_article` matching thresholds — too-low overlap triggers false article matches on generic financial questions.
- `_build_ticker_hint` / `_correct_ticker_arg` correction logic — changing thresholds can re-introduce LLM ticker hallucination.

---

## Deprecated

- Direct `src/mcp_orchestrator.py` usage — file deleted; use `StockAnalysisUseCase` instead.
- Direct `src/agent.py` usage — file deleted; use `StockAnalysisAgentImproved`.
