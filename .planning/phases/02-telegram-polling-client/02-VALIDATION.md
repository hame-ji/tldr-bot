---
phase: 2
slug: telegram-polling-client
status: draft
nyquist_compliant: true
created: 2026-03-15
---

# Phase 2 - Validation Strategy

## Quick Commands

- `python -m compileall src`
- `python -m unittest discover -s tests -p "test_*.py"`

## Per-Requirement Verification

| Requirement | Verification |
|-------------|--------------|
| POLL-01 | `poll_urls` calls `get_updates` with prior offset |
| POLL-02 | Unit test asserts `next_offset == max(update_id) + 1` |
| POLL-03 | Unit tests validate `load_offset` and `save_offset` round-trip `state.json` |
| POLL-04 | `poll_urls` writes offset before returning URL set for downstream use |
| POLL-05 | Unit test validates regex extraction from embedded text |
| POLL-06 | Unit test validates chat-id filtering |

## Manual Check

After sending one URL to the bot, run:

```bash
python src/main.py
python src/main.py
```

Expected:
- First run prints URL(s) and advances offset.
- Second run prints no duplicate URL from the same message.
