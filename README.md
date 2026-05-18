# tickerTalk

Last updated: 2026-05-17 — Commit-ready

## Overview
tickerTalk is a Flask chat app for stock analysis. A local LLM decides which tools to call, the tools fetch live market/news data, and the backend returns a rich analysis card with the chart, heatmap badges, news, and horizon recommendations.

## What the current UI shows
The chat response can include three pieces at once:
1. Tool chips that show which tools ran.
2. `analysis_html`, which renders the card with the chart toggle and heatmap badges.
3. A plain-text reply from the assistant.

The UI also includes:
- A Stop button that cancels an in-flight request.
- Inline source citations when news/web search tools are used.
- Time Horizon Recommendations shown before news in the analysis card.
- 5 news items shown by default, with a "View all news (N)" toggle for the rest.

## Architecture
| Layer | Role |
|-------|------|
| `core/` | Pure recommendation logic and domain models |
| `adapters/` | Yahoo Finance, Finnhub, FinBERT, and company lookup wrappers |
| `application/` | `StockAnalysisUseCase` orchestration |
| `web/` | Flask routes, agent loop, HTML formatting, and browser UI |

## Current recommendation flow
1. User asks for analysis or a follow-up in the browser.
2. `AgentService` builds the prompt and calls `LLMService.generate_raw()`.
3. The LLM emits `<tool_call>` blocks.
4. `ToolExecutor` resolves the ticker and runs full analysis.
5. `FormattingService` renders the analysis card.
6. The browser displays the card plus the assistant reply.

If the model skips tools on an analysis-style request, the backend now forces the full analysis path so the chart and heatmap still appear.

General company questions are guarded to avoid unnecessary full-analysis cards.

## Multi-horizon weights
| Horizon | Fundamental | Technical | Sentiment |
|---------|-------------|-----------|-----------|
| Short | 0.00 | 0.80 | 0.20 |
| Medium | 0.55 | 0.35 | 0.10 |
| Long | 0.80 | 0.20 | 0.00 |

## Run locally
```bash
source .venv/bin/activate
export FINNHUB_API_KEY=your_key_here
python web/app.py
```

## Test and format
```bash
pytest tests/unit
black . && isort . && ruff check .
```

## Environment variables
- `FINNHUB_API_KEY` is required for news.
- `SECRET_KEY` signs Flask sessions.
- `LLM_PROVIDER` defaults to `ollama`.
- `OLLAMA_URL` points at the local Ollama chat endpoint.

## Notes
- Session history is plain text only.
- `data-ticker` on the analysis card is the authoritative ticker for follow-ups.
- Repetitive follow-up prompts are rewritten into context-aware suggestions.
- `src/agent.py` and `src/mcp_orchestrator.py` are legacy references only.
