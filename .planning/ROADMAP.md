# Roadmap: Telegram Research Digest Bot

**Project:** tldr-bot — Personal Telegram URL Digest Bot
**Core Value:** A daily digest of everything you saved, summarized and delivered automatically, so nothing you save goes unread.
**Created:** 2026-03-15
**Granularity:** Coarse (6 phases — dependency-driven; each phase is independently testable before the next begins)

---

## Phases

- [x] **Phase 1: Infrastructure & Bot Setup** - Repo scaffold, GitHub Secrets, verified bot token, and workflow that can push commits
- [x] **Phase 2: Telegram Polling Client** - Correct offset-based polling with `state.json` persistence and `TELEGRAM_CHAT_ID` filtering
- [x] **Phase 3: Content Fetching** - URL classification, article/PDF extraction, timeout safety, and failure records
- [x] **Phase 4: Summarization Routing** - OpenRouter article summarization plus NotebookLM YouTube and fallback routing
- [x] **Phase 5: Digest Generation & Delivery** - Daily digest assembled and chunked for Telegram delivery, with failure section and empty-day guard
- [x] **Phase 6: Pipeline Orchestration & Git Integration** - Full pipeline wired via main.py, create-only daily commit strategy, and end-to-end verified run

---

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Infrastructure & Bot Setup | 3/3 | Completed | 2026-03-15 |
| 2. Telegram Polling Client | 2/2 | Completed | 2026-03-15 |
| 3. Content Fetching | 2/2 | Completed | 2026-03-15 |
| 4. Summarization Routing | 2/2 | Completed | 2026-03-15 |
| 5. Digest Generation & Delivery | 2/2 | Completed | 2026-03-15 |
| 6. Pipeline Orchestration & Git Integration | 2/2 | Completed | 2026-03-15 |

---

## Phase Details

### Phase 1: Infrastructure & Bot Setup
**Goal:** The repository is fully scaffolded, all credentials are provisioned and verified, the GitHub Actions workflow can authenticate and push commits, and the Telegram bot has no active webhook blocking polling.
**Depends on:** Nothing (first phase)
**Requirements:** INFRA-01, INFRA-02, INFRA-03, INFRA-04, INFRA-05, INFRA-06, INFRA-07, BOT-01, BOT-02, BOT-03
**Success Criteria** (what must be TRUE):
  1. `data/`, `prompts/`, and `src/` directories exist in the repository and dependencies are pinned in `pyproject.toml` / `uv.lock`
  2. GitHub Secrets (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `OPENROUTER_API_KEY`) are set and the bot token is confirmed valid via a live BotFather test
  3. `digest.yml` workflow runs successfully (manually dispatched), authenticates with `GITHUB_TOKEN`, and can push a test commit to the repo
  4. `getUpdates` returns real messages (not an empty array), confirming no active webhook is blocking polling
**Plans:** 3 plans
- [x] `01-01-PLAN.md` — Scaffold required directories and pin exact dependencies
- [x] `01-02-PLAN.md` — Create workflow triggers and CI guardrails (permissions, checkout, concurrency)
- [x] `01-03-PLAN.md` — Wire secrets and complete Telegram setup validation checkpoint

### Phase 2: Telegram Polling Client
**Goal:** The pipeline can retrieve new Telegram messages, extract URLs from message text, filter by chat ID, and correctly persist the polling offset so no message is processed twice.
**Depends on:** Phase 1
**Requirements:** POLL-01, POLL-02, POLL-03, POLL-04, POLL-05, POLL-06
**Success Criteria** (what must be TRUE):
  1. Sending a URL to the bot and running the pipeline produces that URL in the extracted list; running the pipeline again does NOT re-produce the same URL (offset is correctly advanced)
  2. `state.json` in the repository root contains `last_update_id + 1` (not `last_update_id`) after a successful poll
  3. Messages from a chat ID not matching `TELEGRAM_CHAT_ID` are silently ignored and do not appear in the URL list
  4. URLs embedded in surrounding text (e.g., "check this out https://example.com good stuff") are correctly extracted by regex
**Plans:** 2 plans
- [x] `02-01-PLAN.md` — Implement Telegram polling client and state offset persistence
- [x] `02-02-PLAN.md` — Add URL extraction/chat filtering tests and wire polling into entrypoint/CI

### Phase 3: Content Fetching
**Goal:** The pipeline can classify incoming URLs, fetch and extract article/PDF content with mandatory timeouts, return YouTube URLs as routeable inputs, and write a failure record for article fetch failures without aborting the pipeline.
**Depends on:** Phase 2
**Requirements:** FETCH-01, FETCH-02, FETCH-03, FETCH-04
**Success Criteria** (what must be TRUE):
  1. A valid article URL returns extracted main-body text (not HTML boilerplate); a YouTube URL is identified and routed without trafilatura extraction
  2. A URL that times out (or returns 403/paywall/empty content) produces a Markdown file in `data/failed/YYYY-MM-DD/slug.md` and the fetcher returns control to the caller — the pipeline does not abort
  3. All HTTP requests complete within the configured hard timeout (`timeout=(10, 30)`) — no request can hang indefinitely
**Plans:** 2 plans
- [x] `03-01-PLAN.md` — Implement URL classification and article extraction with hard timeouts
- [x] `03-02-PLAN.md` — Add failure-record behavior and content fetcher tests

### Phase 4: Summarization Routing
**Goal:** The pipeline can summarize article text via OpenRouter free models, summarize YouTube via NotebookLM, apply NotebookLM fallback for eligible article fetch failures, and write each summary as a dated Markdown file.
**Depends on:** Phase 3
**Requirements:** SUM-01, SUM-02, SUM-03, SUM-04, SUM-05
**Success Criteria** (what must be TRUE):
  1. A real article URL produces a summary written to `data/sources/YYYY-MM-DD/slug.md` using the behavior defined in `prompts/summarize.txt`
  2. YouTube URLs are summarized via NotebookLM and written to `data/sources/`; backend errors write failure records in `data/failed/`
  3. When OpenRouter returns 429/rate-limit errors, the pipeline retries with backoff and model fallback and eventually succeeds (or writes to `data/failed/`) — it does not crash
  4. Changing `prompts/summarize.txt` changes the summary output without any code changes
**Plans:** 2 plans
- [x] `04-01-PLAN.md` — Implement OpenRouter summarizer wrapper and prompt-file control
- [x] `04-02-PLAN.md` — Persist summaries and add summarizer failure-handling tests

### Phase 5: Digest Generation & Delivery
**Goal:** The pipeline assembles a daily Markdown digest from all summaries, delivers it to Telegram in correctly-chunked messages, includes a section for failed URLs, and skips delivery entirely on days with no processed URLs.
**Depends on:** Phase 4
**Requirements:** DGST-01, DGST-02, DGST-03, DGST-04, DGST-05, DGST-06
**Success Criteria** (what must be TRUE):
  1. After a run with 3+ URLs, a dated digest file exists at `data/digests/YYYY-MM-DD.md` and a Telegram message (or message series) arrives with the digest content
  2. A digest exceeding 4096 characters is delivered as multiple sequential Telegram messages, each split at a paragraph boundary — no `400 Bad Request` errors
  3. Failed URLs appear in a dedicated section of the digest (user can see what didn't process)
  4. On a day with no URLs sent, no digest is generated, no Telegram message is sent, and no commit is made
  5. Changing `prompts/digest.txt` changes the digest format without any code changes
**Plans:** 2 plans
- [x] `05-01-PLAN.md` — Implement digest assembly module with prompt-file formatting and failed URL section
- [x] `05-02-PLAN.md` — Add chunked Telegram delivery and empty-day no-send guard

### Phase 6: Pipeline Orchestration & Git Integration
**Goal:** All modules are wired together through `main.py` with per-URL failure isolation; the GitHub Actions workflow commits all outputs with create-only daily commits when outputs change; and a complete end-to-end run (cron or manual) succeeds in the Actions environment.
**Depends on:** Phase 5
**Requirements:** STOR-01, STOR-02, STOR-03, STOR-04
**Success Criteria** (what must be TRUE):
  1. A full pipeline run (send URLs → cron fires → digest delivered → commit pushed) completes successfully in GitHub Actions with a single commit containing all outputs
  2. Running the pipeline twice on the same day (manual re-trigger) creates a second daily commit only when new/staged outputs exist
  3. Standard `git push` succeeds on output commits with no force-push path in the live workflow
  4. A URL that causes an unhandled exception in any module writes a failure record and allows the pipeline to continue processing remaining URLs
**Plans:** 2 plans
- [x] `06-01-PLAN.md` — Add orchestration run-outcome signaling and tests for commit gating
- [x] `06-02-PLAN.md` — Implement workflow output persistence gates and finalize create-only commit/push behavior

---

## Coverage

| Requirement | Phase | Status |
|-------------|-------|--------|
| INFRA-01 | Phase 1 | Completed |
| INFRA-02 | Phase 1 | Completed |
| INFRA-03 | Phase 1 | Completed |
| INFRA-04 | Phase 1 | Completed |
| INFRA-05 | Phase 1 | Completed |
| INFRA-06 | Phase 1 | Completed |
| INFRA-07 | Phase 1 | Completed |
| BOT-01 | Phase 1 | Completed |
| BOT-02 | Phase 1 | Completed |
| BOT-03 | Phase 1 | Completed |
| POLL-01 | Phase 2 | Completed |
| POLL-02 | Phase 2 | Completed |
| POLL-03 | Phase 2 | Completed |
| POLL-04 | Phase 2 | Completed |
| POLL-05 | Phase 2 | Completed |
| POLL-06 | Phase 2 | Completed |
| FETCH-01 | Phase 3 | Completed |
| FETCH-02 | Phase 3 | Completed |
| FETCH-03 | Phase 3 | Completed |
| FETCH-04 | Phase 3 | Completed |
| SUM-01 | Phase 4 | Completed |
| SUM-02 | Phase 4 | Completed |
| SUM-03 | Phase 4 | Completed |
| SUM-04 | Phase 4 | Completed |
| SUM-05 | Phase 4 | Completed |
| DGST-01 | Phase 5 | Completed |
| DGST-02 | Phase 5 | Completed |
| DGST-03 | Phase 5 | Completed |
| DGST-04 | Phase 5 | Completed |
| DGST-05 | Phase 5 | Completed |
| DGST-06 | Phase 5 | Completed |
| STOR-01 | Phase 6 | Completed |
| STOR-02 | Phase 6 | Completed |
| STOR-03 | Phase 6 | Completed |
| STOR-04 | Phase 6 | Completed |

**Coverage:** 34/34 v1 requirements mapped ✓

---
*Roadmap created: 2026-03-15*
*Last updated: 2026-03-28 after truth-alignment refresh*
