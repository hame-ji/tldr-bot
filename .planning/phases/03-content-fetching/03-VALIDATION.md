---
phase: 3
slug: content-fetching
status: draft
nyquist_compliant: true
created: 2026-03-15
---

# Phase 3 - Validation Strategy

## Quick Commands

- `python -m compileall src`
- `python -m unittest discover -s tests -p "test_*.py"`

## Requirement Verification

| Requirement | Verification |
|-------------|--------------|
| FETCH-01 | Unit tests cover YouTube/article URL classification |
| FETCH-02 | Unit tests mock `trafilatura.extract` and verify extracted content path |
| FETCH-03 | Unit tests assert `requests.get(..., timeout=(10, 30))` |
| FETCH-04 | Unit tests verify failure record path/file creation and non-throwing per-url flow |

## Manual Smoke

Send one article URL and one clearly invalid URL to the bot, then run:

```bash
python src/main.py
```

Expected:
- Article URL prints `ok:article:<url>`.
- Invalid URL prints `failed:<url> -> data/failed/...`.
