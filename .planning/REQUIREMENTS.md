# Requirements: Telegram Research Digest Bot

**Defined:** 2026-03-15
**Core Value:** A daily digest of everything you saved, summarized and delivered automatically, so nothing you save goes unread.

## v1 Requirements

### Infrastructure

- [x] **INFRA-01**: GitHub repository is scaffolded with the required directory structure (`data/`, `prompts/`, `src/`)
- [x] **INFRA-02**: Python dependencies are pinned in `pyproject.toml` / `uv.lock` (including `requests`, `trafilatura`, `python-slugify`, and backend SDKs)
- [x] **INFRA-03**: GitHub Secrets are configured (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `OPENROUTER_API_KEY`)
- [x] **INFRA-04**: GitHub Actions workflow `digest.yml` is created with daily cron trigger (07:00 UTC) and manual dispatch
- [x] **INFRA-05**: Workflow declares `permissions: contents: write` to allow `GITHUB_TOKEN` push
- [x] **INFRA-06**: Workflow checkout depth is explicitly configured (`fetch-depth: 1`) for predictable CI behavior
- [x] **INFRA-07**: Workflow has `concurrency: cancel-in-progress: false` to queue rather than cancel runs

### Bot Setup

- [x] **BOT-01**: Telegram bot is created via BotFather and token is confirmed valid
- [x] **BOT-02**: Any active webhook is cleared on the bot token (so `getUpdates` polling works)
- [x] **BOT-03**: `TELEGRAM_CHAT_ID` is configured to filter messages to a single Telegram chat

### Telegram Polling

- [x] **POLL-01**: Pipeline fetches Telegram updates via `getUpdates` polling at pipeline start (not webhook)
- [x] **POLL-02**: Polling offset is stored as `last_update_id + 1` (correct acknowledgement semantics)
- [x] **POLL-03**: Polling offset is read from and written to `state.json` in the repository root
- [x] **POLL-04**: `state.json` offset is written immediately after `getUpdates`, before URL processing begins
- [x] **POLL-05**: URL extraction uses regex to parse URLs from raw message text (handles surrounding words)
- [x] **POLL-06**: Only messages from `TELEGRAM_CHAT_ID` are processed

### Content Fetching

- [x] **FETCH-01**: Pipeline detects URL type and fetches article/PDF content while routing YouTube URLs to summarization without article extraction
- [x] **FETCH-02**: Articles are fetched and main content extracted via `trafilatura`
- [x] **FETCH-03**: All HTTP requests use a hard timeout (`timeout=(10, 30)`) to prevent workflow hangs
- [x] **FETCH-04**: Failed fetches (timeout, 403, paywall, empty content) write a failure record to `data/failed/YYYY-MM-DD/slug.md` and continue — the pipeline does not abort

### Summarization

- [x] **SUM-01**: Article content is summarized via OpenRouter using free-model selection with cached model discovery
- [x] **SUM-02**: YouTube URLs are summarized via NotebookLM, while article content uses OpenRouter (with NotebookLM fallback for eligible article fetch failures)
- [x] **SUM-03**: Summarization behavior is controlled by a prompt file (`prompts/summarize.txt`) — not hardcoded
- [x] **SUM-04**: Each summary is written to `data/sources/YYYY-MM-DD/slug.md` as a Markdown file
- [x] **SUM-05**: OpenRouter API calls include request spacing and retry logic to handle rate limits across free-model fallbacks

### Digest & Delivery

- [x] **DGST-01**: A daily digest file is assembled from all summaries and written to `data/digests/YYYY-MM-DD.md`
- [x] **DGST-02**: Digest format is controlled by a prompt file (`prompts/digest.txt`) — not hardcoded
- [x] **DGST-03**: Digest includes a section for failed URLs (so user sees what didn't process)
- [x] **DGST-04**: Digest is delivered to the configured Telegram chat at the end of each run
- [x] **DGST-05**: Digest delivery chunks messages at paragraph boundaries to stay within Telegram's 4096-char limit
- [x] **DGST-06**: If no URLs were processed (empty day), no commit or delivery is made

### Storage & History

- [x] **STOR-01**: All summaries and digests are stored as Markdown files in the repository (no external database)
- [x] **STOR-02**: The pipeline commits output changes to the repository with a standard daily commit message
- [x] **STOR-03**: If no URLs are processed or no staged outputs exist, commit/push is skipped
- [x] **STOR-04**: Git push uses standard `git push` behavior (no amend/force path in live workflow)

## v2 Requirements

### Bot Commands

- **CMD-01**: User can send `/queue` to see pending unprocessed URLs
- **CMD-02**: User can send `/retry` to reprocess URLs from `data/failed/`
- **CMD-03**: User can trigger an on-demand digest via a Telegram command

### Extended Ingestion

- **ING-01**: Cross-day URL deduplication (same URL sent on two days produces one summary)
- **ING-02**: RSS/feed ingestion as an alternative URL source
- **ING-03**: Acknowledgement message sent to Telegram when a URL is received (requires always-on listener — incompatible with v1 serverless model)

### Extended Output

- **OUT-01**: Weekly digest assembled from the week's daily digest files
- **OUT-02**: Tag support via Markdown frontmatter in source files
- **OUT-03**: Search across the knowledge base (JSON manifest or vector index)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Multi-user / team mode | Single-user personal tool; `TELEGRAM_CHAT_ID` is the permanent boundary |
| Real-time / webhook processing | Fundamentally incompatible with serverless batch model |
| Persistent server / VPS / hosted bot | Contradicts the zero-infrastructure design axiom |
| Mobile or web UI | Not needed; Telegram is the interface |
| Custom transcript scraping stack (`yt-dlp`/Whisper) | Not needed in v1 because YouTube routing is handled by NotebookLM URL-native processing |
| External databases or state stores | Filesystem + Git is the database |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| INFRA-01 | Phase 1 — Infrastructure & Bot Setup | Completed |
| INFRA-02 | Phase 1 — Infrastructure & Bot Setup | Completed |
| INFRA-03 | Phase 1 — Infrastructure & Bot Setup | Completed |
| INFRA-04 | Phase 1 — Infrastructure & Bot Setup | Completed |
| INFRA-05 | Phase 1 — Infrastructure & Bot Setup | Completed |
| INFRA-06 | Phase 1 — Infrastructure & Bot Setup | Completed |
| INFRA-07 | Phase 1 — Infrastructure & Bot Setup | Completed |
| BOT-01 | Phase 1 — Infrastructure & Bot Setup | Completed |
| BOT-02 | Phase 1 — Infrastructure & Bot Setup | Completed |
| BOT-03 | Phase 1 — Infrastructure & Bot Setup | Completed |
| POLL-01 | Phase 2 — Telegram Polling Client | Completed |
| POLL-02 | Phase 2 — Telegram Polling Client | Completed |
| POLL-03 | Phase 2 — Telegram Polling Client | Completed |
| POLL-04 | Phase 2 — Telegram Polling Client | Completed |
| POLL-05 | Phase 2 — Telegram Polling Client | Completed |
| POLL-06 | Phase 2 — Telegram Polling Client | Completed |
| FETCH-01 | Phase 3 — Content Fetching | Completed |
| FETCH-02 | Phase 3 — Content Fetching | Completed |
| FETCH-03 | Phase 3 — Content Fetching | Completed |
| FETCH-04 | Phase 3 — Content Fetching | Completed |
| SUM-01 | Phase 4 — Summarization Routing | Completed |
| SUM-02 | Phase 4 — Summarization Routing | Completed |
| SUM-03 | Phase 4 — Summarization Routing | Completed |
| SUM-04 | Phase 4 — Summarization Routing | Completed |
| SUM-05 | Phase 4 — Summarization Routing | Completed |
| DGST-01 | Phase 5 — Digest Generation & Delivery | Completed |
| DGST-02 | Phase 5 — Digest Generation & Delivery | Completed |
| DGST-03 | Phase 5 — Digest Generation & Delivery | Completed |
| DGST-04 | Phase 5 — Digest Generation & Delivery | Completed |
| DGST-05 | Phase 5 — Digest Generation & Delivery | Completed |
| DGST-06 | Phase 5 — Digest Generation & Delivery | Completed |
| STOR-01 | Phase 6 — Pipeline Orchestration & Git Integration | Completed |
| STOR-02 | Phase 6 — Pipeline Orchestration & Git Integration | Completed |
| STOR-03 | Phase 6 — Pipeline Orchestration & Git Integration | Completed |
| STOR-04 | Phase 6 — Pipeline Orchestration & Git Integration | Completed |

**Coverage:**
- v1 requirements: 34 total
- Mapped to phases: 34
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-15*
*Last updated: 2026-03-28 after truth-alignment refresh*
