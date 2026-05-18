# FinBERT Sentiment Setup

Last updated: 2026-05-17 — Commit-ready

## Current status
FinBERT is used through `FinbertSentimentAdapter`. The model is loaded once per process and reused, so sentiment scoring no longer reloads the weights on every request.

## Install
```bash
pip install -r requirements.txt
```

If you are setting up the sentiment stack separately:
```bash
pip install torch transformers sentencepiece
```

## Runtime behavior
1. Finnhub news articles are fetched.
2. The adapter sends headlines and summaries to FinBERT.
3. The aggregated sentiment score and confidence feed the recommendation engine.
4. If the model cannot load, the adapter returns a safe unavailable result and the app continues with the other signals.

## Notes
- CPU is the fallback, with MPS or CUDA used when available.
- The first run may download the model from Hugging Face.
- The live chat app does not require any extra manual setup beyond installing dependencies.
