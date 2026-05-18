# Finnhub News Setup

Last updated: 2026-05-17 — Commit-ready

## Current status
Finnhub is the live news source used by `FinnhubNewsAdapter` and surfaced in the analysis card through `FormattingService`.

## Setup
1. Create a Finnhub account at https://finnhub.io/register.
2. Add `FINNHUB_API_KEY` to `.env` or your shell.
3. Start the app with `python web/app.py`.

Example:
```bash
FINNHUB_API_KEY=your_actual_api_key_here
```

## What the app uses it for
- Recent company news in the analysis card.
- News sentiment input for the recommendation pipeline.
- Follow-up questions that need article context.

## Notes
- The adapter returns normalized article objects to the web layer.
- The old RSS-based workflow is historical only.
- If news is missing, verify the ticker and the API key first.
