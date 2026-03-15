---
phase: 5
slug: digest-generation-delivery
status: draft
nyquist_compliant: true
created: 2026-03-15
---

# Phase 5 - Validation Strategy

## Quick Commands

- `python -m compileall src`
- `python -m unittest discover -s tests -p "test_*.py"`

## Requirement Verification

| Requirement | Verification |
|-------------|--------------|
| DGST-01 | Unit tests verify digest file is written under `data/digests/<date>.md` when summaries exist |
| DGST-02 | Digest generator reads prompt text from `prompts/digest.txt` and output changes when prompt changes |
| DGST-03 | Digest output includes explicit failed-URLs section populated from failed pipeline items |
| DGST-04 | Telegram delivery path sends digest text to configured chat ID |
| DGST-05 | Delivery tests verify chunk splitting at paragraph boundaries with each chunk <= 4096 chars |
| DGST-06 | Orchestrator test verifies empty-day path skips digest write and Telegram send |

## Manual Smoke

After sending multiple URLs (including one intentionally broken URL):

```bash
python src/main.py
```

Expected:
- Digest file appears at `data/digests/YYYY-MM-DD.md`.
- Telegram receives digest in one or more ordered messages.
- Failed URL appears in digest failure section.

For empty-day verification (no new Telegram URLs):
- No new file under `data/digests/`.
- No Telegram delivery attempt in logs.
