# Project State: Telegram Research Digest Bot

**Last updated:** 2026-03-15
**Session:** Phase 6 execution complete

---

## Project Reference

**Core Value:** A daily digest of everything you saved, summarized and delivered automatically, so nothing you save goes unread.

**One-liner:** Serverless Telegram bot + GitHub Actions + OpenRouter free models — send URLs, receive a morning digest, no server required.

**Working directory:** `/Users/jonas/dev/hameji/tldr-bot`

---

## Current Position

**Current phase:** Phase 6 — Pipeline Orchestration & Git Integration
**Current plan:** None (all phase plans complete)
**Status:** Complete (roadmap finished)

```
Progress: [ Phase 1 ][ Phase 2 ][ Phase 3 ][ Phase 4 ][ Phase 5 ][ Phase 6 ]
           [  DONE  ][  DONE  ][  DONE  ][  DONE  ][  DONE  ][  DONE  ]
```

**Phase completion:** 6/6

---

## Performance Metrics

| Metric | Value |
|--------|-------|
| Phases total | 6 |
| Phases complete | 6 |
| Requirements mapped | 34/34 |
| Plans created | 13 |
| Plans complete | 13 |

---

## Accumulated Context

### Key Decisions

| Decision | Rationale |
|----------|-----------|
| 6 phases despite "coarse" granularity setting | Each phase tests an independently verifiable external integration (Telegram, trafilatura, OpenRouter, Git); merging would mask which layer fails during debugging |
| Polling offset committed before URL processing | POLL-04 / Pitfall 2: if pipeline crashes mid-run, offset must be persisted so next run doesn't reprocess same URLs |
| Article-only summarization scope | YouTube transcript access from CI is unreliable without paid proxy; v1 keeps zero-cost by silently ignoring non-article URLs |
| `parse_mode="HTML"` for Telegram digest delivery | Avoid MarkdownV2 escaping fragility while preserving safe formatting with escaped dynamic text |

### Critical Pitfalls to Watch

1. **Telegram offset off-by-one** — Store `max(update_id) + 1`, not `max(update_id)` -> Implemented in Phase 2
2. **state.json not committed before processing** — Write offset commit before any URL fetching begins → Phase 6 (orchestration)
3. **GITHUB_TOKEN missing `contents: write`** — Must be explicit in workflow permissions → Phase 1
4. **requests without timeout** — Always `timeout=(10, 30)` -> Implemented in Phase 3
5. **Telegram 4096-char limit** — Chunk on paragraph boundaries before sending -> Implemented in Phase 5
6. **Webhook blocking getUpdates** — Run `deleteWebhook` during bot setup → Phase 1
7. **Non-article URL handling drift** — Keep YouTube/non-article URLs ignored end-to-end so they do not create failures or digest noise

### Research Flags

- **Phase 4 (YouTube):** Non-article URLs are intentionally ignored in v1 article-only mode.
- **Phase 4 (rate limits):** Free OpenRouter models can change/limit dynamically. Keep model discovery cache + retry/backoff enabled and verify fallback ordering in CI.
- **Phase 5 (parse_mode):** Use `parse_mode="HTML"` with escaped dynamic text to avoid MarkdownV2 escaping complexity.

### Architecture Notes

- **5 Python modules:** `telegram_client.py`, `content_fetcher.py`, `summarizer.py`, `digest_generator.py`, `main.py`
- **Prompt files:** `prompts/summarize.txt`, `prompts/digest.txt` — behavior-tunable without code changes
- **State:** `state.json` (repo root) — polling offset only
- **Outputs:** `data/sources/YYYY-MM-DD/slug.md`, `data/digests/YYYY-MM-DD.md`, `data/failed/YYYY-MM-DD/slug.md`
- **Commit strategy:** one-per-day, amend if same-date re-run, `--force-with-lease` push

---

## Todos

- [x] Create Telegram bot via BotFather and save token → Phase 1
- [x] Create OpenRouter API key → Phase 1
- [x] Verify `getUpdates` returns messages (no active webhook) → Phase 1
- [x] Implement Telegram polling, chat filtering, and URL extraction in code + tests -> Phase 2
- [x] Implement content fetching with timeout guards and failure records -> Phase 3
- [x] Implement OpenRouter summarizer with prompt file control, retries, and source-file outputs -> Phase 4
- [x] Implement digest generation, failed-URL section, and Telegram delivery chunking -> Phase 5
- [ ] Run live verification for article-only handling (YouTube URLs ignored, article summaries delivered)

---

## Blockers

None.

---

## Session Continuity

### To resume this project:
1. Read `.planning/ROADMAP.md` — current phase and success criteria
2. Read `.planning/STATE.md` (this file) — decisions, pitfalls, todos
3. Run manual smoke in GitHub Actions (`workflow_dispatch`) to confirm same-day amend path on remote history

### Planning artifacts:
- `.planning/PROJECT.md` — project goals and constraints
- `.planning/REQUIREMENTS.md` — all 34 v1 requirements with phase mapping
- `.planning/ROADMAP.md` — phases, success criteria, coverage table
- `.planning/research/SUMMARY.md` — stack decisions, pitfalls, phase rationale

---
*State initialized: 2026-03-15*
