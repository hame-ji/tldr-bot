# Roadmap: Telegram Research Digest Bot

**Project:** tldr-bot — Personal Telegram URL Digest Bot
**Core Value:** A daily digest of everything you saved, summarized and delivered automatically, so nothing you save goes unread.
**Created:** 2026-03-15
**Granularity:** Coarse (6 phases — dependency-driven; each phase is independently testable before the next begins)

---

## Phases

- [ ] **Phase 1: Infrastructure & Bot Setup** - Repo scaffold, GitHub Secrets, verified bot token, and workflow that can push commits
- [ ] **Phase 2: Telegram Polling Client** - Correct offset-based polling with state.json persistence and ALLOWED_CHAT_ID filtering
- [ ] **Phase 3: Content Fetching** - URL classification, article extraction via trafilatura, timeout safety, and failure records
- [ ] **Phase 4: Gemini Summarization** - AI summarization for articles and YouTube URLs with prompt file control and rate-limit resilience
- [ ] **Phase 5: Digest Generation & Delivery** - Daily digest assembled and chunked for Telegram delivery, with failure section and empty-day guard
- [ ] **Phase 6: Pipeline Orchestration & Git Integration** - Full pipeline wired via main.py, amend-or-create commit strategy, and end-to-end verified run

---

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Infrastructure & Bot Setup | 3/3 | Completed | 2026-03-15 |
| 2. Telegram Polling Client | 2/2 | Completed | 2026-03-15 |
| 3. Content Fetching | 2/2 | Completed | 2026-03-15 |
| 4. Gemini Summarization | 2/2 | Completed | 2026-03-15 |
| 5. Digest Generation & Delivery | 0/? | Not started | - |
| 6. Pipeline Orchestration & Git Integration | 0/? | Not started | - |

---

## Phase Details

### Phase 1: Infrastructure & Bot Setup
**Goal:** The repository is fully scaffolded, all credentials are provisioned and verified, the GitHub Actions workflow can authenticate and push commits, and the Telegram bot has no active webhook blocking polling.
**Depends on:** Nothing (first phase)
**Requirements:** INFRA-01, INFRA-02, INFRA-03, INFRA-04, INFRA-05, INFRA-06, INFRA-07, BOT-01, BOT-02, BOT-03
**Success Criteria** (what must be TRUE):
  1. `data/`, `prompts/`, and `src/` directories exist in the repository and `requirements.txt` pins exact versions of all five dependencies
  2. GitHub Secrets (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `GEMINI_API_KEY`) are set and the bot token is confirmed valid via a live BotFather test
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
  3. Messages from a chat ID not matching `ALLOWED_CHAT_ID` are silently ignored and do not appear in the URL list
  4. URLs embedded in surrounding text (e.g., "check this out https://example.com good stuff") are correctly extracted by regex
**Plans:** 2 plans
- [x] `02-01-PLAN.md` — Implement Telegram polling client and state offset persistence
- [x] `02-02-PLAN.md` — Add URL extraction/chat filtering tests and wire polling into entrypoint/CI

### Phase 3: Content Fetching
**Goal:** The pipeline can classify a URL as article or YouTube, fetch and extract article content via trafilatura with mandatory timeouts, and write a failure record for any URL that cannot be fetched — without aborting the pipeline.
**Depends on:** Phase 2
**Requirements:** FETCH-01, FETCH-02, FETCH-03, FETCH-04
**Success Criteria** (what must be TRUE):
  1. A valid article URL returns extracted main-body text (not HTML boilerplate); a YouTube URL is classified separately and not passed to trafilatura
  2. A URL that times out (or returns 403/paywall/empty content) produces a Markdown file in `data/failed/YYYY-MM-DD/slug.md` and the fetcher returns control to the caller — the pipeline does not abort
  3. All HTTP requests complete within the configured hard timeout (`timeout=(10, 30)`) — no request can hang indefinitely
**Plans:** 2 plans
- [x] `03-01-PLAN.md` — Implement URL classification and article extraction with hard timeouts
- [x] `03-02-PLAN.md` — Add failure-record behavior and content fetcher tests

### Phase 4: Gemini Summarization
**Goal:** The pipeline can summarize article text and YouTube URLs via Gemini 2.5 Flash using prompt files, handle rate limits gracefully, and write each summary as a dated Markdown file — without SDK import errors or silent safety-block failures.
**Depends on:** Phase 3
**Requirements:** SUM-01, SUM-02, SUM-03, SUM-04, SUM-05
**Success Criteria** (what must be TRUE):
  1. A real article URL produces a summary written to `data/sources/YYYY-MM-DD/slug.md` using the behavior defined in `prompts/summarize.txt`
  2. A YouTube URL is summarized natively by Gemini (no yt-dlp or transcript extraction) and produces a source file in the same format
  3. When the Gemini API returns a 429, the pipeline retries with backoff and eventually succeeds (or writes to `data/failed/` after exhausting retries) — it does not crash
  4. Changing `prompts/summarize.txt` changes the summary output without any code changes
**Plans:** 2 plans
- [x] `04-01-PLAN.md` — Implement Gemini summarizer wrapper and prompt-file control
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
**Plans:** TBD

### Phase 6: Pipeline Orchestration & Git Integration
**Goal:** All modules are wired together through main.py with per-URL failure isolation; the GitHub Actions workflow commits all outputs using an amend-or-create-per-day strategy; and a complete end-to-end run (cron or manual) succeeds in the Actions environment.
**Depends on:** Phase 5
**Requirements:** STOR-01, STOR-02, STOR-03, STOR-04
**Success Criteria** (what must be TRUE):
  1. A full pipeline run (send URLs → cron fires → digest delivered → commit pushed) completes successfully in GitHub Actions with a single commit containing all outputs
  2. Running the pipeline twice on the same day (manual re-trigger) produces one amended commit — not two commits — and the digest reflects all URLs from both runs
  3. `--force-with-lease` push succeeds after the amend; no force-push conflicts occur in the standard single-user workflow
  4. A URL that causes an unhandled exception in any module writes a failure record and allows the pipeline to continue processing remaining URLs
**Plans:** TBD

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
| DGST-01 | Phase 5 | Pending |
| DGST-02 | Phase 5 | Pending |
| DGST-03 | Phase 5 | Pending |
| DGST-04 | Phase 5 | Pending |
| DGST-05 | Phase 5 | Pending |
| DGST-06 | Phase 5 | Pending |
| STOR-01 | Phase 6 | Pending |
| STOR-02 | Phase 6 | Pending |
| STOR-03 | Phase 6 | Pending |
| STOR-04 | Phase 6 | Pending |

**Coverage:** 34/34 v1 requirements mapped ✓

---
*Roadmap created: 2026-03-15*
*Last updated: 2026-03-15*
