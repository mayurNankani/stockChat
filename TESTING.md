# Testing

Last updated: 2026-05-17 — Commit-ready

## Current smoke tests
```bash
source .venv/bin/activate
pytest tests/unit
```

## Live app checks
Use these to verify the current browser flow:
```bash
python web/app.py
```

Then in the browser, try:
- `analyze AAPL`
- `should I buy NVDA?`
- `analyze ^GSPC`

Expected result:
- Tool chips appear.
- The analysis card includes the chart toggle and heatmap badges.
- Time Horizon Recommendations appear before the news section.
- The news section shows 5 items by default and expands with "View all news (N)".
- The assistant reply appears below the card.

## Recommendation engine tests
The repository still includes the older comparison scripts for historical context:
```bash
./scripts/testing/test_comparison.sh AAPL
.venv/bin/python scripts/testing/compare_systems.py AAPL
```

Those scripts print recommendation output from the current scoring engine; they are not part of the chat UI path.

## Useful checks
- `tests/unit/test_recommendation_engine.py` verifies the weighting rules.
- `tests/unit/test_stock_service.py` checks ticker resolution.
- `tests/unit/test_cache.py` covers the in-memory TTL cache.

## What to verify manually
1. The backend returns `analysis_html` for analysis-style requests.
2. The chart toggle appears in the response card.
3. The heatmap badges render as STRONG BUY, BUY, HOLD, or SELL.
4. Clicking Stop during a request cancels the in-flight response cleanly.
5. Replies that use news/web search include a Sources section with clickable links.
