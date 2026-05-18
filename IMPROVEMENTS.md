# Improvements

Last updated: 2026-05-17 — Commit-ready

## Current status
The project now uses the agentic Flask flow in `web/`. The rich analysis card is built from `analysis_html`, and the backend has a fallback path so analysis-style queries still show the chart and heatmap even if the LLM skips tool calls.

## Recommendation system improvements

The repository still keeps the improved scoring docs for reference, but the current live flow is the agentic chat path in `web/services/agent_service.py`.

## Key improvements

### 1. **Continuous Weighted Scoring (vs Binary Thresholds)**

**Old System:**
```python
if pe_ratio < 15:
    score += 2
elif pe_ratio < 25:
    score += 1
elif pe_ratio > 40:
    score -= 1
```
- **Problem**: PE of 14.9 and 10 both get +2, but 10 might indicate problems
- **Problem**: PE of 15.1 gets only +1, huge drop from 14.9

**New System:**
```python
if pe < 10:
    pe_score = 0.6  # Too cheap might signal problems
elif pe < 15:
    pe_score = 1.0  # Sweet spot
elif pe < 25:
    pe_score = 0.7 - (pe - 15) * 0.02  # Gradually decrease
elif pe < 40:
    pe_score = 0.4 - (pe - 25) * 0.015
else:
    pe_score = max(0, 0.2 - (pe - 40) * 0.01)

valuation_score += pe_score * 3.0  # Weight of 3
```
- **Benefit**: Smooth transitions, no arbitrary jumps
- **Benefit**: Different metrics have different importance (weights)
- **Benefit**: More nuanced - recognizes PE of 10 vs 14 vs 20

### 2. **Metric Weighting (vs Equal Treatment)**

**Old System:**
- All positive signals = +1 or +2
- PE ratio gets same weight as current ratio
- Growth gets same weight as valuation

**New System:**
```python
# Valuation category weights:
PE Ratio:     3.0
PEG Ratio:    4.0  # Most important valuation metric
Price-to-Book: 2.0

# Growth category weights:
Revenue Growth:  4.0
Earnings Growth: 5.0  # Most important growth metric

# Health category weights:
Debt-to-Equity: 3.5
Current Ratio:  2.5
Quick Ratio:    2.0

# Profitability category weights:
Profit Margins: 4.0
ROE:            4.5
Operating Margins: 2.5
```
- **Benefit**: PEG ratio matters more than price-to-book (rightly so)
- **Benefit**: Earnings growth weighted higher than revenue growth
- **Benefit**: Reflects real-world investing priorities

### 3. **Sector-Aware Adjustments**

**Old System:**
- Same scoring for tech stock vs utility stock
- Growth-focused tech companies penalized for low PE

**New System:**
```python
SECTOR_WEIGHTS = {
    "Technology": {"growth": 1.5, "valuation": 0.7, "profitability": 1.3, "health": 0.8},
    "Financial": {"growth": 0.8, "valuation": 1.2, "profitability": 1.1, "health": 1.5},
    "Utilities": {"growth": 0.6, "valuation": 1.1, "profitability": 1.0, "health": 1.3},
}

# Applied as:
weighted_growth = (growth_score / growth_max) * 10 * weights["growth"]
```
- **Benefit**: Tech stocks (high growth, high PE) scored appropriately
- **Benefit**: Financial stocks emphasize balance sheet health
- **Benefit**: Utilities get less penalty for low growth

### 4. **Confidence Scoring (New Feature)**

**Old System:**
- No indication of recommendation reliability
- Missing data handled same as present data

**New System:**
```python
# Track which metrics are available
metrics_available = sum([
    1 if fundamental_data.get('pe_ratio') else 0,
    1 if fundamental_data.get('peg_ratio') else 0,
    # ... 8 key metrics total
])
confidence = (metrics_available / 8) * 100

# Returns:
{
    "label": "BUY",
    "score": 68.5,
    "confidence": 87.5  # High confidence = 7-8 metrics available
}
```
- **Benefit**: User knows if recommendation is based on full data or partial
- **Benefit**: Can filter low-confidence recommendations
- **Benefit**: Transparency about data quality

### 5. **Normalized 0-100 Scoring (vs Unbounded Integers)**

**Old System:**
```python
score = 0
# After many additions/subtractions
if score >= 3:
    label = "STRONG BUY"
elif score > 0:
    label = "BUY"
# ...
```
- **Problem**: Score of 5 vs 15 both = STRONG BUY (no differentiation)
- **Problem**: Can't tell "how strong" the buy is

**New System:**
```python
normalized_score = (total_score / max_possible_score) * 100

# Returns score 0-100:
- 90: Very strong buy (clear winner)
- 75: Strong buy (threshold)
- 65: Moderate buy
- 50: Neutral
- 30: Moderate sell
```
- **Benefit**: Clear percentage scale everyone understands
- **Benefit**: Can rank stocks (78 vs 65 vs 52)
- **Benefit**: More granular than 4 categories

### 6. **Non-Linear Scoring for Realistic Relationships**

**Old System:**
```python
if revenue_growth > 0.2:
    score += 2
elif revenue_growth > 0.1:
    score += 1
```
- **Problem**: 21% growth = 10% growth in terms of incremental value
- **Problem**: Doesn't capture diminishing returns

**New System:**
```python
if rev_pct > 30:
    rev_score = 1.0
elif rev_pct > 20:
    rev_score = 0.85 + (rev_pct - 20) * 0.015  # Diminishing returns
elif rev_pct > 10:
    rev_score = 0.65 + (rev_pct - 10) * 0.02
elif rev_pct > 5:
    rev_score = 0.5 + (rev_pct - 5) * 0.03
elif rev_pct > 0:
    rev_score = 0.4 + rev_pct * 0.02
else:
    rev_score = max(0, 0.4 + rev_pct * 0.05)  # Steeper penalty for decline
```
- **Benefit**: 30% growth gets full credit, more doesn't help much (realistic)
- **Benefit**: Difference between 5% and 10% growth properly valued
- **Benefit**: Negative growth penalized more severely

### 7. **Technical Analysis: Signal Strength Matters**

**Old System:**
```python
if rsi < 30:
    signals += 2  # RSI of 29 = RSI of 5
elif rsi < 40:
    signals += 1
```

**New System:**
```python
if rsi < 30:
    # RSI of 10 gets higher score than RSI of 29
    rsi_score = 1.0 - (rsi / 30) * 0.3
    total_score += rsi_score * 5.0  # Weighted by importance
```
- **Benefit**: RSI of 10 (extremely oversold) scores higher than 29
- **Benefit**: Captures intensity of signal, not just direction

### 8. **Volatility Adjustments for Technical Signals**

**Old System:**
- Bollinger Band signals treated equally regardless of volatility

**New System:**
```python
# Calculate Bollinger position score...
if bb_width > 0.2:  # High volatility
    volatility_factor = 0.7  # Reduce signal reliability
elif bb_width > 0.1:
    volatility_factor = 0.85
else:
    volatility_factor = 1.0

total_score += bb_position_score * 3.5 * volatility_factor
```
- **Benefit**: High volatility = less confidence in signals
- **Benefit**: Avoids false signals during turbulent periods

### 9. **Medium-Term Blending Improved**

**Old System:**
```python
# Simple label addition
rec_scores = {"STRONG BUY": 2, "BUY": 1, "HOLD": 0, "SELL": -1}
medium_score = rec_scores[fundamental_label] + rec_scores[technical_label]
```
- **Problem**: Loses granularity (STRONG BUY + HOLD = BUY + BUY)
- **Problem**: Can't weight fundamental vs technical differently

**New System:**
```python
f_score = fundamental_rec.get('score', 50)  # 0-100 scale
t_score = technical_rec.get('score', 50)
medium_score = (f_score * 0.6) + (t_score * 0.4)  # 60% fundamental, 40% technical
```
- **Benefit**: Preserves full granularity
- **Benefit**: Can adjust weights (60/40 split for medium-term makes sense)
- **Benefit**: Fundamentals matter more over 3 months

## Comparison Example: Apple (AAPL)

**Scenario**: AAPL with PE=28, Revenue Growth=8%, Earnings Growth=12%, Debt/Equity=1.8

### Old System:
```
PE 28: +0 (not <25, not >40)
Revenue 8%: +0 (not >10%)
Earnings 12%: +1 (>10%)
Debt 1.8: -0 (not <1, not >2)
Total: +1 → BUY
```

### New System:
```
PE 28:
  score = 0.4 - (28-25)*0.015 = 0.355
  weighted = 0.355 * 3.0 = 1.065

Revenue 8%:
  score = 0.5 + (8-5)*0.03 = 0.59
  weighted = 0.59 * 4.0 = 2.36

Earnings 12%:
  score = 0.65 + (12-10)*0.02 = 0.69
  weighted = 0.69 * 5.0 = 3.45

Debt 1.8:
  score = 0.45 - (1.8-1.5)*0.2 = 0.39
  weighted = 0.39 * 3.5 = 1.365

Valuation: 1.065/3 * 10 = 3.55/10
Growth: 5.81/9 * 10 = 6.46/10
Health: 1.365/3.5 * 10 = 3.9/10

Normalized: (3.55+6.46+3.9)/30 * 100 = 46.4/100 → HOLD
Confidence: 62.5% (5/8 metrics available)
```

**Key Difference**: 
- Old: **BUY** (binary threshold crossed)
- New: **HOLD (46.4/100)** with **62.5% confidence** - more accurate given mediocre valuation and health

## How to Switch to Improved System

### Option 1: Direct Replacement
```python
# web/repositories/stock_repository.py
# Change:
from src.agent import StockAnalysisAgent
# To:
from src.agent_improved import StockAnalysisAgentImproved as StockAnalysisAgent
```

### Option 2: Gradual Transition (Recommended)
1. Keep both systems running
2. Compare results side-by-side
3. Tune weights based on real performance
4. Switch when confident

### Option 3: A/B Testing
```python
from src.agent import StockAnalysisAgent
from src.agent_improved import StockAnalysisAgentImproved

# Show both recommendations to users
old_rec = StockAnalysisAgent().get_recommendation(ticker)
new_rec = StockAnalysisAgentImproved().get_recommendation(ticker)

# Let users choose which they trust more
```

## Weight Tuning

The weights are currently educated guesses. You can tune them based on:

1. **Backtesting**: Historical data to see which weights predict future performance
2. **Sector Analysis**: Adjust sector weights based on what actually matters
3. **User Feedback**: Track which recommendations users follow and outcomes

Example tuning:
```python
# If you find PEG ratio is too heavily weighted:
peg_score * 3.0  # instead of 4.0

# If profit margins matter more than ROE in practice:
profit_score += pm_score * 5.0  # instead of 4.0
profit_score += roe_score * 3.5  # instead of 4.5
```

## Summary of Benefits

| Feature | Old System | New System |
|---------|-----------|------------|
| **Scoring** | Binary thresholds (+1, +2, -1) | Continuous weighted (0-1 scale) |
| **Differentiation** | 4 labels only | 0-100 score + labels |
| **Metric Weight** | All equal | Customized by importance |
| **Sector Awareness** | None | Sector-specific adjustments |
| **Confidence** | Not reported | 0-100% confidence score |
| **Smooth Transitions** | Jumps at thresholds | Gradual scoring curves |
| **Signal Strength** | Binary (yes/no) | Intensity-based |
| **Volatility Adjustment** | None | Reduces unreliable signals |
| **Medium-term Blend** | Label arithmetic | Weighted score blend |
| **Granularity** | Low (can't rank) | High (can rank stocks) |

## Next Steps

1. **Test with known stocks**: Run both systems on AAPL, TSLA, GOOGL, etc.
2. **Validate scores**: Do the scores "feel right" to you?
3. **Adjust weights**: Tune based on your investment philosophy
4. **Add sector detection**: Extract sector from yfinance data to use sector weights
5. **Backtest**: Historical performance comparison
6. **Deploy**: Switch production to improved system

## Files changed
- `web/services/agent_service.py` now forces full analysis when an analysis request gets a plain-text model response.
- `web/services/agent_service.py` now blocks full analysis for general company-info prompts unless recommendation intent is explicit.
- `web/services/agent_service.py` rewrites repetitive generic follow-up prompts into context-aware suggestions.
- `web/services/agent_service.py` appends deduplicated source citations when `get_news` or `web_search` tools are used.
- `web/services/formatting_service.py` now fails open instead of dropping the whole analysis card.
- `web/services/formatting_service.py` now renders recommendations before news and shows 5 news items by default with an expander for additional items.
- `web/index.html` renders tool chips, the analysis card, and the assistant reply separately.
- `web/index.html` includes request cancellation via Stop button.
- `web/services/stock_service.py` and `application/use_cases/run_stock_analysis.py` carry the current unified analysis path.

## Next work
1. Reduce duplicated legacy code in `src/`.
2. Add more end-to-end browser coverage for the chart toggle and heatmap.
3. Simplify the recommendation docs once the legacy comparison scripts are retired.
