# tickerTalk — Architecture

Last updated: 2026-05-17 — Commit-ready

## Current system overview
tickerTalk is a Flask web app that runs a prompt-based agent loop. The LLM decides which tools to call, the tools fetch live stock data, and the backend returns a rich HTML analysis card plus a conversational reply.

## Layers
| Layer | Responsibility |
|-------|----------------|
| Browser | Sends chat requests and renders `analysis_html` |
| Flask routes | `/chat` and `/api/price-history` |
| AgentService | Builds prompts, parses `<tool_call>`, and orchestrates the loop |
| ToolExecutor | Resolves tickers and executes analysis/news/chart tools |
| StockAnalysisService | Runs the unified stock analysis use case |
| FormattingService | Builds the analysis card with chart, heatmap, and news |

## Data flow
1. User sends a chat message.
2. `AgentService` appends history and a ticker hint.
3. The LLM emits tool calls.
4. `resolve_ticker` validates the symbol by checking that price data exists.
5. `run_full_analysis` fetches quote, news, price history, and recommendation data.
6. `FormattingService` renders the card HTML.
7. The browser receives `reply`, `tool_updates`, and `analysis_html`.

## Important behavior
- Analysis-style requests are guarded so the full card still appears even if the model skips tool calls.
- General company-info requests are guarded so full analysis is not run unless recommendation intent is explicit.
- Session history stays plain text only.
- `data-ticker` on the analysis card is the source of truth for follow-up context.
- The chart is loaded and drawn in the browser from `analysis_html` plus `/api/price-history`.
- Assistant replies include source citations when news/web-search tools provide URLs.
- The browser supports request cancellation through a Stop button.
- In full analysis cards, Time Horizon Recommendations appear before news; news shows 5 items by default with an expand toggle.

## Current tool set
| Tool | Purpose |
|------|---------|
| `resolve_ticker` | Company name or ticker to validated symbol |
| `run_full_analysis` | Full technical, fundamental, and sentiment analysis |
| `get_stock_snapshot` | Fast quote and valuation snapshot |
| `get_news` | Latest Finnhub news |
| `get_price_history` | Chart data |
| `get_earnings` | Earnings data |
| `web_search` | DuckDuckGo fallback search |

## Recommendation weights
| Horizon | Fundamental | Technical | Sentiment |
|---------|-------------|-----------|-----------|
| Short | 0.00 | 0.80 | 0.20 |
| Medium | 0.55 | 0.35 | 0.10 |
| Long | 0.80 | 0.20 | 0.00 |

## External services
| Service | Role |
|---------|------|
| Ollama | Local LLM inference |
| yfinance | Quotes and history |
| Finnhub | News and logos |
| FinBERT | News sentiment |
| DuckDuckGo | Web search fallback |
