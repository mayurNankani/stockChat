# Recommendation Logic

Last updated: 2026-05-17 — Commit-ready

## Current source of truth
The live weights and label mapping are defined in `core/analysis/recommendation_engine.py`. This document explains the current scoring model used by the chat app and the comparison scripts.

## Current horizon weights
| Horizon | Fundamental | Technical | Sentiment |
|---------|-------------|-----------|-----------|
| Short | 0.00 | 0.80 | 0.20 |
| Medium | 0.55 | 0.35 | 0.10 |
| Long | 0.80 | 0.20 | 0.00 |

## Current label mapping
| Weighted score | Label |
|----------------|-------|
| 70+ | buy |
| 40-69 | hold |
| < 40 | sell |

The UI converts those labels into the badge text shown in the analysis card.

---

## 1. Fundamental Analysis Scoring (0-100 Scale)

### Purpose
Evaluates the company's **financial health, profitability, and growth potential** using balance sheet and income statement data.

### Improved Scoring System
- **Each metric scored 0-100** with non-linear curves (not just binary good/bad)
- **Weighted by importance** (PEG ratio weight: 4.0, Earnings growth: 5.0, etc.)
- **Sector-adjusted** (tech gets 1.5x growth weight, utilities get 0.6x)
- **Confidence score** based on how many key metrics are available

### Metrics Analyzed (with Weights)

#### A. Valuation Metrics

**PEG Ratio (P/E to Growth) - Weight: 4.0 (HIGHEST)**
- **< 1**: Score ~90 (growth justifies price - excellent value)
- **1-2**: Score ~60 (reasonable valuation)
- **> 3**: Score ~20 (overvalued for growth)
- *Why weighted highest*: Best single metric combining valuation + growth

**P/E Ratio (Price-to-Earnings) - Weight: 3.0**
- **< 15**: Score ~80 (undervalued)
- **15-25**: Score ~60 (fair value)
- **> 40**: Score ~30 (overvalued)
- *Curve*: Non-linear - extreme P/E ratios (< 5 or > 50) penalized

**Price-to-Book Ratio - Weight: 2.5**
- **< 1**: Score ~85 (trading below book value)
- **1-3**: Score ~60 (fair)
- **> 5**: Score ~25 (expensive vs assets)

#### B. Growth Metrics

**Earnings Growth (YoY) - Weight: 5.0 (HIGHEST)**
- **> 30%**: Score ~95 (exceptional growth)
- **20-30%**: Score ~80 (strong growth)
- **10-20%**: Score ~60 (moderate growth)
- **0-10%**: Score ~40 (slow growth)
- **< 0%**: Score ~15 (declining profits)
- *Why weighted highest*: Profit growth is the ultimate driver of long-term returns

**Revenue Growth (YoY) - Weight: 4.0**
- **> 20%**: Score ~85 (high growth)
- **10-20%**: Score ~65 (moderate growth)
- **< 0%**: Score ~20 (declining sales)

#### C. Financial Health Metrics

**Debt-to-Equity Ratio - Weight: 3.5**
- **< 0.5**: Score ~90 (conservative leverage)
- **0.5-1.0**: Score ~70 (moderate debt)
- **1.0-2.0**: Score ~45 (elevated debt)
- **> 2.0**: Score ~20 (high leverage risk)
- *Curve*: Exponential penalty for high debt

**Current Ratio (Short-term Liquidity) - Weight: 3.0**
- **> 2.5**: Score ~90 (strong liquidity)
- **1.5-2.5**: Score ~70 (healthy)
- **1.0-1.5**: Score ~45 (adequate)
- **< 1.0**: Score ~15 (liquidity concerns)

#### D. Profitability Metrics

**Profit Margins - Weight: 4.0**
- **> 20%**: Score ~90 (highly profitable)
- **10-20%**: Score ~65 (decent margins)
- **0-10%**: Score ~35 (low margins)
- **< 0%**: Score ~5 (losing money)

**Return on Equity (ROE) - Weight: 3.5**
- **> 20%**: Score ~90 (excellent returns)
- **15-20%**: Score ~70 (good returns)
- **10-15%**: Score ~50 (average)
- **< 5%**: Score ~20 (poor returns)

### Sector-Specific Weight Adjustments

Different industries have different priorities:

| Sector | Growth Weight | Valuation Weight | Profitability Weight | Health Weight |
|--------|---------------|------------------|---------------------|---------------|
| **Technology** | 1.5x | 0.7x | 1.3x | 0.8x |
| **Financial** | 0.8x | 1.2x | 1.1x | 1.5x |
| **Healthcare** | 1.3x | 0.9x | 1.0x | 1.2x |
| **Energy** | 0.9x | 1.3x | 1.4x | 1.1x |
| **Utilities** | 0.6x | 1.1x | 1.0x | 1.3x |
| **Consumer** | 1.0x | 1.0x | 1.2x | 1.0x |

**Example**: A tech company gets 1.5x weight on earnings growth (because tech is valued on growth), but only 0.7x on P/E ratio (because tech stocks naturally trade at higher multiples).

### Final Score Calculation

```python
weighted_sum = 0
total_weight = 0

for metric in metrics:
    metric_score = calculate_score(metric_value)  # 0-100
    sector_adjusted_weight = base_weight * sector_multiplier
    weighted_sum += metric_score * sector_adjusted_weight
    total_weight += sector_adjusted_weight

final_score = weighted_sum / total_weight  # Normalized 0-100
```

### Confidence Score

Based on how many key metrics are available:
- **8/8 metrics**: 100% confidence
- **6/8 metrics**: 75% confidence
- **4/8 metrics**: 50% confidence
- **< 4 metrics**: Low confidence warning

**Key metrics**: PEG, PE, Earnings Growth, Revenue Growth, Debt/Equity, Profit Margin, ROE, Current Ratio

### Fundamental Label Determination (New Thresholds)
```
Score >= 70:  STRONG BUY
Score >= 55:  BUY
Score >= 45:  HOLD
Score >= 30:  SELL
Score < 30:   STRONG SELL
```

### Example Calculation (Weighted System)
```
Tech Company XYZ Analysis:
Earnings Growth = 25% → Score: 82, Weight: 5.0 × 1.5 (tech) = 7.5
Revenue Growth = 30% → Score: 90, Weight: 4.0 × 1.5 = 6.0
PEG Ratio = 1.2 → Score: 65, Weight: 4.0 × 0.7 = 2.8
Profit Margin = 22% → Score: 88, Weight: 4.0 × 1.3 = 5.2
Debt/Equity = 0.3 → Score: 92, Weight: 3.5 × 0.8 = 2.8
ROE = 28% → Score: 95, Weight: 3.5 × 1.3 = 4.55
P/E = 32 → Score: 45, Weight: 3.0 × 0.7 = 2.1
Current Ratio = 2.1 → Score: 75, Weight: 3.0 × 0.8 = 2.4

weighted_sum = (82×7.5 + 90×6.0 + 65×2.8 + 88×5.2 + 92×2.8 + 95×4.55 + 45×2.1 + 75×2.4)
             = 2485.65
total_weight = 33.35

Final Score = 2485.65 / 33.35 = 74.5 → STRONG BUY
Confidence = 8/8 metrics = 100%

Summary: "High earnings growth (25%), Strong revenue growth (30%), Excellent ROE (28%), Strong margins (22%)"
```

## 2. Technical Analysis Scoring (0-100 Scale)

### Purpose
Evaluates **price momentum, trends, and trading signals** using chart patterns and mathematical indicators.

### Improved Scoring System
- **Each indicator category weighted** (moving averages: weight 4.0, RSI: 3.5, etc.)
- **Non-linear scoring curves** (extreme RSI values score higher than moderate)
- **Confidence based on indicator availability** (9 indicators tracked)
- **Long-term indicators added**: SMA 200, major golden cross (SMA 50 × 200)

### Indicators Analyzed (with Weights)

#### A. Momentum Oscillators

**RSI (Relative Strength Index, 0-100) - Weight: 3.5**
- **< 30**: Score ~95 (oversold, potential bounce)
- **30-40**: Score ~70 (slightly oversold)
- **40-60**: Score ~50 (neutral)
- **60-70**: Score ~30 (slightly overbought)
- **> 70**: Score ~5 (overbought, potential pullback)
- *Curve*: U-shaped (extreme values better than moderate)

**Stochastic Oscillator (K & D lines, 0-100) - Weight: 3.0**
- **Both < 20**: Score ~90 (oversold)
- **Both > 80**: Score ~10 (overbought)
- **K crosses above D + both < 50**: Score ~85 (bullish crossover in oversold zone)
- **K crosses below D + both > 50**: Score ~15 (bearish crossover in overbought zone)

**MFI (Money Flow Index, 0-100) - Weight: 3.0**
- **< 20**: Score ~90 (money flowing out, oversold)
- **> 80**: Score ~10 (money flowing in, overbought)
- *Volume-weighted RSI*: Shows buying/selling pressure

#### B. Trend Indicators

**MACD (Moving Average Convergence Divergence) - Weight: 3.5**
- **MACD > Signal + Histogram growing**: Score ~85 (strong bullish momentum)
- **MACD > Signal + Histogram shrinking**: Score ~60 (weakening bullish)
- **MACD < Signal + Histogram falling**: Score ~15 (strong bearish momentum)

**ADX (Average Directional Index, 0-100) - Weight: 3.5**
- **ADX > 25 + +DI > -DI**: Score ~85 (strong uptrend)
- **ADX > 25 + -DI > +DI**: Score ~15 (strong downtrend)
- **ADX < 20**: Score ~50 (no clear trend - neutral)

**Moving Averages - Weight: 4.0 (HIGHEST for technicals)**
- **SMA 20** (short-term trend):
  - Price > SMA 20: +0.6 × weight
  - Price < SMA 20: +0.4 × weight
- **SMA 50** (medium-term trend):
  - Price > SMA 50: +0.7 × weight
  - Price < SMA 50: +0.3 × weight  
- **SMA 200** (long-term trend): **NEW!**
  - Price > SMA 200: +0.8 × weight
  - Price < SMA 200: +0.2 × weight
- **Golden Cross (SMA 20 × 50)**: +1.0 × 3.5 weight (bullish signal)
- **Major Golden Cross (SMA 50 × 200)**: **NEW!** +1.0 × 4.0 weight (very bullish)
- **Death Cross (SMA 20 × 50)**: +0.0 × weight (bearish)

*Why weight 4.0*: Moving averages are the most reliable trend indicators

#### C. Volatility Indicators

**Bollinger Bands Width - Weight: 2.5**
- **Width < 0.05**: Score ~75 (low volatility, potential breakout)
- **Width > 0.15**: Score ~35 (high volatility, risk)

**ATR (Average True Range) - Weight: 2.0**
- Used for volatility context, not directly scored

#### D. Volume Indicators

**OBV (On-Balance Volume) - Weight: 2.5**
- **OBV trending up**: Score ~75 (volume confirms uptrend)
- **OBV trending down**: Score ~25 (volume confirms downtrend)

### Confidence Score (Technical)

Based on indicator availability (9 total):
- RSI, Stochastic, MFI, MACD, ADX, SMA 20, SMA 50, SMA 200, Bollinger Bands

**Confidence = (available_indicators / 9) × 100**

### Technical Label Determination (New Thresholds)
```
Score >= 70:  STRONG BUY
Score >= 55:  BUY
Score >= 45:  HOLD
Score >= 30:  SELL
Score < 30:   STRONG SELL
```

### Example Calculation (Weighted System)
```
Stock ABC Technical Analysis:
RSI = 28 → Score: 95, Weight: 3.5
Stochastic K=15, D=18 → Score: 90, Weight: 3.0
MFI = 22 → Score: 88, Weight: 3.0
MACD > Signal → Score: 70, Weight: 3.5
ADX = 32, +DI > -DI → Score: 85, Weight: 3.5
Price > SMA 20 → Score: 60 (0.6×100), Weight: 4.0
Price > SMA 50 → Score: 70 (0.7×100), Weight: 4.0
Price > SMA 200 → Score: 80 (0.8×100), Weight: 4.0
SMA 50 crossed SMA 200 → Score: 100, Weight: 4.0

weighted_sum = (95×3.5 + 90×3.0 + 88×3.0 + 70×3.5 + 85×3.5 + 60×4.0 + 70×4.0 + 80×4.0 + 100×4.0)
             = 2352.5
total_weight = 33.0

Final Score = 2352.5 / 33.0 = 71.3 → STRONG BUY
Confidence = 9/9 = 100%

Summary: "RSI oversold (28), Stochastic oversold, Major golden cross (SMA50×200), Price above all MAs, Strong uptrend (ADX=32)"
```

---

## 3. Sentiment Analysis (News-Based, 0-100 Scale)

### Purpose **NEW!**
Analyzes **financial news sentiment** using FinBERT (AI model trained on financial text) to gauge market perception and news flow.

### How It Works
1. **Fetch latest news** (5-7 articles from past week via Finnhub API)
2. **Analyze each article** headline (70% weight) + summary (30% weight)
3. **Classify sentiment**: Positive, Negative, or Neutral (with confidence scores)
4. **Aggregate** across all articles

### Sentiment Scoring
- **Positive sentiment**: Score 60-100 (bullish news)
- **Neutral sentiment**: Score 40-60 (mixed/no strong opinion)
- **Negative sentiment**: Score 0-40 (bearish news)

### Confidence Score
Based on **agreement** among articles:
- All articles same sentiment: 90-100% confidence
- 4/5 articles agree: 80% confidence
- 3/5 articles agree: 60% confidence
- Evenly split: 30-40% confidence

### Example
```
Apple (AAPL) News Analysis:
Article 1: "Apple reports record Q4 earnings" → Positive (95%)
Article 2: "iPhone sales exceed expectations" → Positive (88%)
Article 3: "Apple stock reaches new high" → Positive (92%)
Article 4: "Analysts raise AAPL price targets" → Positive (85%)
Article 5: "Supply chain concerns ease for Apple" → Neutral (65%)

Aggregate: 4 positive, 1 neutral
Overall Score = 78/100 (Positive)
Confidence = 80% (4/5 agree)

Summary: "Positive news sentiment (4 positive, 1 neutral from 5 articles)"
```

### When Sentiment Matters
- ✅ **Short-term (1 week)**: News drives immediate price moves
- ✅ **Medium-term (3 months)**: Sentiment shifts can change momentum
- ❌ **Long-term (6-12 months)**: News is fleeting, fundamentals matter more

---

## 4. Time Horizon Recommendations (Updated Weights)

The system generates **three different recommendations** with updated blending:

### Short-Term (1 Week)
**Formula: 80% Technical + 20% Sentiment**

**Reasoning:**
- Short-term moves driven by **momentum and news**
- Sentiment captures immediate market reaction to news
- Fundamentals don't change week-to-week

**Example:**
```
Technical Score: 72/100
Sentiment Score: 65/100
Short-term = (72 × 0.80) + (65 × 0.20) = 70.6 → STRONG BUY

Summary: "Technical: RSI oversold, MACD bullish | Sentiment: Positive news (4 positive articles)"
```

### Medium-Term (3 Months)
**Formula: 55% Fundamental + 35% Technical + 10% Sentiment**

**Reasoning:**
- **Fundamentals** start to drive price over months
- **Technical** momentum can extend trends
- **Sentiment** provides context on market perception

**Example:**
```
Fundamental: 68/100
Technical: 72/100  
Sentiment: 55/100
Medium-term = (68 × 0.55) + (72 × 0.35) + (55 × 0.10) = 67.9 → BUY

Summary: "Fundamentals: Strong growth, good margins | Technical: Uptrend confirmed | Sentiment: Neutral news"
```

### Long-Term (6-12 Months)
**Formula: 80% Fundamental + 20% Technical (No Sentiment)**

**Reasoning:**
- **Fundamentals** are the primary driver of long-term value
- **Technical** trends provide confirmation:
  - Is the stock in a long-term uptrend (above SMA 200)?
  - Major golden cross (SMA 50 × 200)?
  - Strong long-term momentum (ADX)?
- **Sentiment removed** - news is fleeting, doesn't matter for 6-12 months
- A great company in a long-term downtrend deserves caution
- Technical provides **timing** confirmation for fundamental thesis

**Example:**
```
Fundamental: 75/100
Technical: 58/100 (in uptrend but not strong)
Long-term = (75 × 0.80) + (58 × 0.20) = 71.6 → STRONG BUY

Summary: "Fundamentals: Excellent growth, strong ROE | Technical: Price above SMA 200, moderate trend"
```

**Why 20% Technical for Long-Term?**
- Catches stocks in long-term downtrends despite good fundamentals (sector rotation, loss of market favor)
- Rewards stocks breaking out of long bases (SMA 50 crossing SMA 200)
- Provides better entry timing (don't buy fundamentally strong stocks in clear downtrends)

---

## 5. Summary of Updated Recommendation Logic

| Time Horizon | Formula | Logic | Best For |
|-------------|---------|-------|----------|
| **Short-term (1 week)** | 80% Technical<br/>20% Sentiment | Momentum + news-driven | Day/swing traders |
| **Medium-term (3 months)** | 55% Fundamental<br/>35% Technical<br/>10% Sentiment | Balanced with news context | Active investors |
| **Long-term (6-12 months)** | 80% Fundamental<br/>20% Technical | Quality with trend confirmation | Buy-and-hold |

### Key Improvements Over Old System

1. **Weighted continuous scoring (0-100)** vs simple +1/+2 points
   - More nuanced (difference between PE=16 and PE=40 now captured)
   - Sector-adjusted (tech vs utility valued differently)
   
2. **Confidence scores** show data quality
   - High confidence (90%+): Many metrics available
   - Low confidence (< 50%): Limited data, use caution
   
3. **Sentiment analysis** adds news context
   - Captures market perception
   - Explains why stock moves despite fundamentals
   
4. **Advanced technical indicators**
   - SMA 200 for long-term trend
   - Major golden cross (50×200)
   - 9 indicators vs 6 in old system
   
5. **Better thresholds**
   - Old: ≥3 = STRONG BUY (too easy to achieve)
   - New: ≥70/100 = STRONG BUY (more meaningful)

### What's Still Missing

- **Market context**: Overall market conditions (bull/bear market)
- **Sector rotation**: Industry trends and cycles
- **Macro events**: Fed policy, inflation, geopolitical risks
- **Analyst estimates**: Earnings surprises vs expectations
- **Insider trading**: Director/executive buying/selling
- **Short interest**: Potential squeeze dynamics
- **Options flow**: Institutional positioning

These would require additional data sources and complexity.

---

## 6. How to Use These Recommendations

### Reading the Output

Each recommendation shows:
- **Label**: STRONG BUY, BUY, HOLD, SELL, STRONG SELL
- **Score**: 0-100 (exact score, e.g., 68.5)
- **Confidence**: 0-100% (data quality)
- **Summary**: Top reasons driving the decision
- **Separate sections**: 📊 Fundamental, 📈 Technical, 💭 Sentiment

### Decision Framework

**All aligned (all STRONG BUY):**
- High conviction setup
- Fundamentals strong + technicals aligned + positive news
- Best risk/reward

**Conflicting signals:**
- Short BUY, Long HOLD → Good for trading, not investing
- Short SELL, Long BUY → Great company in pullback (buying opportunity)
- All timeframes say SELL → Strong avoid signal

**Low confidence warnings:**
- < 50% confidence → Limited data, proceed with caution
- Missing key metrics (no earnings growth, no debt data)
- Use as starting point, do more research

### Real-World Example: Tesla (TSLA)

**Scenario:** TSLA down 20% after earnings, but long-term growth intact

```
FUNDAMENTAL (Score: 72/100, Confidence: 88%):
- Earnings Growth: 35% → 90 points
- Revenue Growth: 28% → 85 points
- Profit Margin: 15% → 62 points
- Debt/Equity: 0.8 → 72 points
→ Sector-adjusted (Tech): Growth weighted 1.5x
→ Label: STRONG BUY

TECHNICAL (Score: 38/100, Confidence: 100%):
- RSI: 32 → 88 points (oversold)
- Price < SMA 50 → 30 points (downtrend)
- Price < SMA 200 → 20 points (long-term downtrend)
- MACD bearish → 20 points
- ADX: 28, -DI > +DI → 15 points (strong downtrend)
→ Label: SELL

SENTIMENT (Score: 42/100, Confidence: 65%):
- 2 negative articles (earnings miss, guidance cut)
- 2 neutral articles
- 1 positive article (long-term bullish)
→ Label: NEUTRAL (slightly negative)

RECOMMENDATIONS:
- Short-term (80% Tech, 20% Sent): (38×0.8 + 42×0.2) = 38.8 → SELL
  → Don't buy yet, momentum still bearish
  
- Medium-term (55% Fund, 35% Tech, 10% Sent): (72×0.55 + 38×0.35 + 42×0.1) = 57.9 → BUY
  → Good fundamentals + oversold = potential bounce in months
  
- Long-term (80% Fund, 20% Tech): (72×0.80 + 38×0.2) = 65.2 → BUY
  → Strong growth story, ignore short-term weakness

INVESTOR ACTION:
- Day trader: Stay out (downtrend intact)
- Swing trader: Consider entry if RSI < 30 (wait for capitulation)
- Long-term investor: BUY (great company, temporary selloff)
```

This is a perfect example of why different timeframes matter - fundamentally strong but technically weak means different things to different investors!
