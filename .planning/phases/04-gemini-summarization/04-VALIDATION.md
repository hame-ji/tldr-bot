---
phase: 4
slug: gemini-summarization
status: draft
nyquist_compliant: true
created: 2026-03-15
---

# Phase 4 - Validation Strategy

## Quick Commands

- `python -m compileall src`
- `python -m unittest discover -s tests -p "test_*.py"`

## Requirement Verification

| Requirement | Verification |
|-------------|--------------|
| SUM-01 | Unit tests verify article summary path writes output file via OpenRouter summarizer |
| SUM-02 | Unit tests verify YouTube URL transcript extraction path and transcript-backed summarization flow |
| SUM-03 | Prompt file exists and is loaded in summarizer runtime path |
| SUM-04 | Unit tests verify source output file path under `data/sources/<date>/` |
| SUM-05 | Summarizer implementation includes spacing + retry path for rate limits and free-model fallback ordering |

## Manual Smoke

After sending one article URL and one YouTube URL to the bot:

```bash
python src/main.py
```

Expected:
- Summary files appear under `data/sources/YYYY-MM-DD/`.
- Any OpenRouter or transcript-access failure is recorded under `data/failed/YYYY-MM-DD/`.
