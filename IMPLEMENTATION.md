# tickerTalk — Implementation Guide

Last updated: 2026-05-17 — Commit-ready

## Request flow
1. The browser posts `history` and `model` to `/chat`.
2. `AgentService` builds the system prompt and adds a ticker hint.
3. The LLM emits one or more `<tool_call>` blocks.
4. `ToolExecutor` resolves the ticker and runs `run_full_analysis`.
5. `StockAnalysisService` produces the stock analysis object.
6. `FormattingService` renders the HTML card with the logo, price, chart toggle, heatmap badges, expandable reasons, and news.
7. The browser shows tool chips, the card, and the assistant reply.

If the model answers without calling tools on an analysis-style request, the backend now forces the full analysis path so the rich card still appears.

If the model returns the repetitive "run full analysis or compare" follow-up, `AgentService` rewrites it into a context-aware prompt based on the user question type.

When `get_news` or `web_search` tools run, `AgentService` appends deduplicated clickable source citations to the final assistant reply.

General company questions are guarded so `run_full_analysis` is skipped unless recommendation intent is explicit.

## Tools
| Tool | Use |
|------|-----|
| `resolve_ticker` | Validate company name or ticker |
| `run_full_analysis` | Full recommendation and rich HTML card |
| `get_stock_snapshot` | Fast quote and valuation lookup |
| `get_news` | Latest news |
| `get_price_history` | Chart data for the browser |
| `get_earnings` | Earnings data |
| `web_search` | External context for follow-ups |

## Recommendation scoring
The current horizon weights are:
| Horizon | Fundamental | Technical | Sentiment |
|---------|-------------|-----------|-----------|
| Short | 0.00 | 0.80 | 0.20 |
| Medium | 0.55 | 0.35 | 0.10 |
| Long | 0.80 | 0.20 | 0.00 |

Ratings are mapped from the weighted score:
| Score | Label |
|-------|-------|
| 70+ | STRONG BUY |
| 55-69 | BUY |
| 40-54 | HOLD |
| 25-39 | SELL |
| < 25 | STRONG SELL |

## Chat state
The session stores only plain text conversation history. The analysis card, chart data, and news are always regenerated.

The browser uses an abortable fetch flow with a Stop button to cancel long-running requests.

In the analysis card, Time Horizon Recommendations are rendered before news. News shows 5 items by default with a "View all news (N)" expander.

## Run locally
```bash
source .venv/bin/activate
cp config/.env.example .env
export FINNHUB_API_KEY=your_key_here
python web/app.py
```

## Add a new tool
1. Add a schema entry in `web/services/agent_tools.py`.
2. Add a handler method on `ToolExecutor`.
3. Register the handler in `execute()`.
4. Let the system prompt pick it up automatically.
