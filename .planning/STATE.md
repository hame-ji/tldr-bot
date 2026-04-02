# Project State: Telegram Research Digest Bot

**Last updated:** 2026-04-02
**Session:** NotebookLM auth resilience + dedicated replay workflow hardening

---

## Project Reference

**Core Value:** A daily digest of everything you saved, summarized and delivered automatically, so nothing you save goes unread.

**One-liner:** Serverless Telegram URL digest pipeline on GitHub Actions. Poll updates, fetch content, summarize via routed backends, write artifacts, send digest.

**Working directory:** `/home/jonas/dev/github/tldr-bot`

---

## Current Position

**Current phase:** Roadmap implementation complete (6/6)
**Status:** Completed and operating with ongoing maintenance/docs hardening

```
Progress: [ Phase 1 ][ Phase 2 ][ Phase 3 ][ Phase 4 ][ Phase 5 ][ Phase 6 ]
           [  DONE  ][  DONE  ][  DONE  ][  DONE  ][  DONE  ][  DONE  ]
```

---

## Live Behavior Snapshot

- Runtime: `.github/workflows/digest.yml` (daily schedule + manual dispatch)
- Recovery workflow: `.github/workflows/replay-notebooklm.yml` (manual replay control plane)
- Entry point: `python -m src` (`src/main.py`)
- Polling state: `state.json` (`telegram_offset`)
- Summarization routing:
  - OpenRouter for fetched article/PDF content
  - NotebookLM for YouTube
  - NotebookLM fallback for eligible article fetch failures
- Persistence: `data/sources/`, `data/failed/`, `data/digests/`
- Commit policy (live workflow): create-only daily commit subject; skip commit on empty day or no staged changes
- NotebookLM policy: preflight guardrail in `enforce` mode, runtime auth circuit breaker, replay queue for auth failures

---

## Key Decisions (Live)

| Decision | Rationale |
|----------|-----------|
| Polling over webhooks | Preserves serverless/no-endpoint constraint |
| `state.json` committed in Git | Durable, auditable, simple state model |
| Markdown artifacts in repo | Human-readable outputs and portable history |
| Split backend routing | Better fit by source type and degraded-fetch cases |
| Per-item failure isolation | One URL failure should not abort digest run |
| Dedicated replay control plane | Recovery should not require Telegram re-polling |
| Shared workflow concurrency group | Prevent replay queue mutation races |

---

## Operational Contracts

- Pipeline emits `run_outcome:` JSON and `run_metrics:` JSON to logs.
- Workflow extraction/reporting is non-blocking and should not block successful content persistence.
- Empty-day behavior: no digest delivery and no commit/push.
- NotebookLM replay queue is persisted under `data/replay/notebooklm/` and drained by `replay-notebooklm.yml`.

---

## Continuity Notes

To resume with minimal ambiguity:

1. Read `.planning/REQUIREMENTS.md` for scope and requirement status.
2. Read `architecture.md` for rationale/trade-offs/failure model.
3. Read `.github/workflows/digest.yml` and `.github/workflows/replay-notebooklm.yml` for runtime and recovery behavior.
4. Read `docs/operations.md` for incident handling.

---
*State refreshed: 2026-04-02 for NotebookLM auth resilience alignment*
