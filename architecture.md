# Architecture Design Document - Telegram Research Digest Bot

> A serverless, zero-infrastructure personal knowledge pipeline built on GitHub Actions, Telegram, and Gemini.

---

## Problem & Context

Engineers accumulate URLs throughout the day - articles shared in chats, YouTube talks flagged for later, threads worth reading. The default outcome is a browser graveyard: tabs that never get read, bookmarks that never get revisited.

Existing tools either require too much friction at ingestion time (tagging, categorizing, opening an app) or too much infrastructure to self-host (servers, databases, background workers). The result is that most saved content is never consumed.

The goal here is different: **make saving effortless and let the system do the synthesis work**, delivering a daily digest you actually read because it's already summarized.

---

## Design Philosophy

Four principles govern every decision in this system. They are listed here not as constraints but as *axioms* - the reasoning that makes the architecture coherent rather than accidental.

```
Filesystem as database
Git as history
Telegram as ingestion queue
GitHub Actions as scheduler
```

**Filesystem as database** means every piece of knowledge is a Markdown file you can read, grep, diff, and back up without tooling. No schema migrations, no connection strings, no vendor lock-in.

**Git as history** means the audit trail is the repository itself. Every day's digest is a commit. You can see what you were reading in any given week by browsing the log.

**Telegram as ingestion queue** means the capture friction is exactly one action: paste a URL. No app to open, no form to fill. The phone you already have open is the interface.

**GitHub Actions as scheduler** means there is no server to provision, patch, or pay for. Execution is triggered, runs to completion, and disappears. The pipeline exists only when it's needed.

---

## Architecture Overview

```
User -> Telegram Bot
         |
         |  URLs accumulate as messages (polling at run time)
         v
   GitHub Action (daily cron or manual dispatch)
         |
         v
   Python Pipeline
   |-- Read Telegram updates (offset-based, stateful)
   |-- Filter by ALLOWED_CHAT_ID
   |-- Extract & normalize URLs
   |-- For each URL:
   |   |-- Detect type (article / YouTube)
   |   |-- Fetch or pass content to Gemini
   |   |-- Generate summary -> write data/sources/YYYY-MM-DD/slug.md
   |   `-- On failure -> write data/failed/YYYY-MM-DD/slug.md
   |-- Generate digest -> write data/digests/YYYY-MM-DD.md
   |-- Commit all changes
   `-- Send digest to Telegram
```

**Components:**

| Component | Role | Rationale |
|---|---|---|
| Telegram Bot | Ingestion interface + delivery channel | Ubiquitous, zero-friction, API-first |
| GitHub Actions | Execution runtime + scheduler | Free, ephemeral, no ops burden |
| GitHub Repository | Storage + version history | Durable, browsable, diffable |
| Gemini 2.0 Flash | Summarization + YouTube processing | 1M context window; free tier; native YouTube URL support |
| `state.json` | Telegram polling cursor | Single-field, committed, auditable |

---

## Key Design Decisions

### 1. No persistent server

**Decision:** The pipeline runs exclusively as a GitHub Actions workflow. There is no always-on process.

**Alternative considered:** A lightweight server (VPS, fly.io, Railway) hosting a webhook receiver and background worker.

**Why we didn't:** A server introduces operational surface area - uptime monitoring, SSL, restarts, cost - that is disproportionate to the problem. The digest is inherently a batch operation; near-real-time delivery adds no value. GitHub Actions gives us scheduling, secrets management, logging, and a free execution environment with zero ongoing maintenance.

---

### 2. Polling over webhooks

**Decision:** Telegram updates are fetched via `getUpdates` polling at pipeline start, not via webhooks.

**Alternative considered:** Telegram webhook pointing to a persistent endpoint.

**Why we didn't:** Webhooks require a reachable HTTPS endpoint, which requires a server. Since the serverless constraint is non-negotiable, polling is the only viable model. The design accepts the trade-off: URLs sent during the day accumulate and are processed in batch, not in real time. This is a feature, not a bug - it aligns with the digest model.

---

### 3. State as a committed file

**Decision:** `state.json` holds a single value - the last processed Telegram update ID - and is committed to the repository as part of the daily digest commit.

**Alternative considered:** External state store (Redis, DynamoDB, a GitHub Gist).

**Why we didn't:** External state adds a dependency, credentials to manage, and a failure mode. A committed file is durable, inspectable, and version-controlled. If something goes wrong, the state is visible in the Git log. The single-daily-run model means there is no meaningful concurrency risk - the concurrency guard in the workflow (`cancel-in-progress: false`) ensures only one execution runs at a time.

The commit strategy is intentionally simple: if a commit already exists for that day, amend it. This keeps history clean - one commit per day, date-keyed, regardless of whether the run was triggered by cron or manually.

---

### 4. Filesystem as knowledge base

**Decision:** Summaries and digests are Markdown files organized by date in the repository.

**Alternative considered:** SQLite, a vector store, or a hosted notes service.

**Why we didn't:** A database would make the knowledge base opaque and non-portable. Markdown files are human-readable, git-diffable, searchable with standard tools, and renderable on GitHub with no additional tooling. The structure (`data/sources/YYYY-MM-DD/`) makes temporal browsing natural. For the current use case - personal knowledge archival and daily consumption - filesystem access patterns are sufficient.

---

### 5. Prompt files as the configuration surface

**Decision:** LLM output format and length are controlled entirely by prompt files (`prompts/*.txt`). No token limits or format rules are hardcoded in pipeline logic.

**Alternative considered:** Hardcoded instructions inline in Python; a structured config file.

**Why we didn't:** Prompt files make the system's behavior tunable without touching code. Changing the digest format, adjusting summary length, or adding a new section to outputs is a text edit, not a deployment. This separation of concerns is especially valuable in a one-person project where experimentation should be low-friction.

---

### 6. Gemini native YouTube processing

**Decision:** YouTube URLs are passed directly to Gemini 2.0 Flash, which processes them natively. No transcript extraction.

**Alternative considered:** `yt-dlp` + Whisper transcription + summarization; YouTube Data API for metadata.

**Why we didn't:** Gemini's native YouTube support eliminates an entire infrastructure layer - no audio download, no transcription model, no storage for audio files. For an MVP targeting a single user with 1-10 URLs per day, the simplicity gain is significant. The risk (dependency on a model capability that could be deprecated) is accepted explicitly; if that changes, the fallback path (yt-dlp + transcript) is well-defined and can be added without architectural changes.

---

### 7. Silent failure with explicit record

**Decision:** When a URL fails (timeout, paywall, extraction error), the pipeline writes a failure record to `data/failed/YYYY-MM-DD/` and continues. The run does not abort.

**Alternative considered:** Fail-fast (abort on first error); retry with backoff.

**Why we didn't:** Fail-fast would mean one bad URL kills the entire digest. Given that paywalled content is a common and expected failure mode, this is unacceptable. Retry with backoff adds complexity and extends runtime unpredictably. The failure record in `data/failed/` is a first-class artifact - visible, inspectable, and usable by a future `/retry` command without any architectural changes.

---

## Accepted Trade-offs

These are known limitations explicitly accepted for this version. They are not oversights.

| Trade-off | Accepted because |
|---|---|
| No cross-day URL deduplication | Same URL on two days is rare; two summaries is harmless; the fix (a URL index file) is additive when needed |
| No on-demand digest from Telegram | Requires a persistent process or webhook; incompatible with the serverless constraint; manual dispatch from GitHub UI is sufficient |
| Gemini free-tier rate limits | 1-10 URLs/day is well within limits; if usage grows, the API client is the only thing that changes |
| No retry mechanism | Failure records provide the data; a `/retry` command is the natural future interface without pipeline changes |
| Partial results on mid-run API failure | Acceptable for a personal digest; the committed partial state is better than nothing |

---

## Evolution Path

The architecture was designed to grow along two axes without requiring structural changes.

**Additive (no rewrites):**
- Telegram bot commands (`/queue`, `/retry`, `/digest`) - add a command parser to `telegram_client.py`
- Weekly digests - add a second workflow trigger and a `weekly_digest.py` script consuming existing daily files
- RSS ingestion - add a new ingestion module; the pipeline from URL onwards is unchanged
- URL preview feedback on save - extend the acknowledgement message with title extraction
- Tag support - add a metadata field to Markdown frontmatter; the filesystem structure supports it natively

**Requires architectural evolution:**
- Multi-user / team mode - `ALLOWED_CHAT_ID` becomes a list or a shared channel; state scoping becomes per-user; Git history remains shared
- Search across the knowledge base - the flat Markdown structure supports `git grep` today; a proper index (simple JSON manifest or embeddings file) would need to be built and maintained incrementally
- Real-time processing - fundamentally incompatible with the serverless model; would require a persistent process and a webhook, which invalidates the core constraint

The deliberate choice to keep the architecture simple now means the evolution path is clear: additive features slot in without rewrites, and the one genuinely breaking change (real-time) is also the one that contradicts the original design axioms.

---

*System designed for single-user operation. All execution is ephemeral. No infrastructure to maintain beyond the repository itself.*
