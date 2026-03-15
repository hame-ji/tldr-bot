# Project State: Telegram Research Digest Bot

**Last updated:** 2026-03-15
**Session:** Phase 3 execution complete

---

## Project Reference

**Core Value:** A daily digest of everything you saved, summarized and delivered automatically, so nothing you save goes unread.

**One-liner:** Serverless Telegram bot + GitHub Actions + Gemini 2.0 Flash — send URLs, receive a morning digest, no server required.

**Working directory:** `/Users/jonas/dev/hameji/tldr-bot`

---

## Current Position

**Current phase:** Phase 3 — Content Fetching
**Current plan:** None (all phase plans complete)
**Status:** Complete (ready for Phase 4)

```
Progress: [ Phase 1 ][ Phase 2 ][ Phase 3 ][ Phase 4 ][ Phase 5 ][ Phase 6 ]
           [  DONE  ][  DONE  ][  DONE  ][  TODO  ][  TODO  ][  TODO  ]
```

**Phase completion:** 3/6

---

## Performance Metrics

| Metric | Value |
|--------|-------|
| Phases total | 6 |
| Phases complete | 3 |
| Requirements mapped | 34/34 |
| Plans created | 7 |
| Plans complete | 7 |

---

## Accumulated Context

### Key Decisions

| Decision | Rationale |
|----------|-----------|
| 6 phases despite "coarse" granularity setting | Each phase tests an independently verifiable external integration (Telegram, trafilatura, Gemini, Git); merging would mask which layer fails during debugging |
| Polling offset committed before URL processing | POLL-04 / Pitfall 2: if pipeline crashes mid-run, offset must be persisted so next run doesn't reprocess same URLs |
| `google-genai` not `google-generativeai` | `google-generativeai` is inactive since Nov 2025; explicitly pin `google-genai` in requirements.txt |
| `parse_mode` decision deferred to Phase 5 | MarkdownV2 escaping complexity vs. plain Markdown vs. HTML — decide during Phase 5 implementation |

### Critical Pitfalls to Watch

1. **Telegram offset off-by-one** — Store `max(update_id) + 1`, not `max(update_id)` -> Implemented in Phase 2
2. **state.json not committed before processing** — Write offset commit before any URL fetching begins → Phase 6 (orchestration)
3. **GITHUB_TOKEN missing `contents: write`** — Must be explicit in workflow permissions → Phase 1
4. **requests without timeout** — Always `timeout=(10, 30)` -> Implemented in Phase 3
5. **Telegram 4096-char limit** — Chunk on paragraph boundaries before sending → Phase 5
6. **Webhook blocking getUpdates** — Run `deleteWebhook` during bot setup → Phase 1
7. **SDK confusion** — Only `from google import genai`; never `google.generativeai` → Phase 1 (deps) + Phase 4

### Research Flags

- **Phase 4 (Gemini):** Verify `contents=[youtube_url]` native processing before building YouTube path — MEDIUM confidence from research. Fallback: write YouTube URLs to `data/failed/` in v1.
- **Phase 4 (rate limits):** Exact Gemini 2.0 Flash free-tier RPM limits not verified. `sleep(1)` + retry is safe regardless; verify if running 10+ URL batches.
- **Phase 5 (parse_mode):** Choose between `parse_mode="Markdown"` (v1) and HTML mode to avoid MarkdownV2 escaping complexity.

### Architecture Notes

- **5 Python modules:** `telegram_client.py`, `content_fetcher.py`, `summarizer.py`, `digest_generator.py`, `main.py`
- **Prompt files:** `prompts/summarize.txt`, `prompts/digest.txt` — behavior-tunable without code changes
- **State:** `state.json` (repo root) — polling offset only
- **Outputs:** `data/sources/YYYY-MM-DD/slug.md`, `data/digests/YYYY-MM-DD.md`, `data/failed/YYYY-MM-DD/slug.md`
- **Commit strategy:** one-per-day, amend if same-date re-run, `--force-with-lease` push

---

## Todos

- [x] Create Telegram bot via BotFather and save token → Phase 1
- [x] Create Gemini API key → Phase 1
- [x] Verify `getUpdates` returns messages (no active webhook) → Phase 1
- [x] Implement Telegram polling, chat filtering, and URL extraction in code + tests -> Phase 2
- [x] Implement content fetching with timeout guards and failure records -> Phase 3
- [ ] Verify Gemini native YouTube URL processing in Phase 4 before building full YouTube path
- [ ] Decide `parse_mode` (Markdown v1 vs HTML) before Phase 5 delivery implementation

---

## Blockers

None.

---

## Session Continuity

### To resume this project:
1. Read `.planning/ROADMAP.md` — current phase and success criteria
2. Read `.planning/STATE.md` (this file) — decisions, pitfalls, todos
3. Run `/gsd-plan-phase 4` to start Gemini summarization implementation

### Planning artifacts:
- `.planning/PROJECT.md` — project goals and constraints
- `.planning/REQUIREMENTS.md` — all 34 v1 requirements with phase mapping
- `.planning/ROADMAP.md` — phases, success criteria, coverage table
- `.planning/research/SUMMARY.md` — stack decisions, pitfalls, phase rationale

---
*State initialized: 2026-03-15*
