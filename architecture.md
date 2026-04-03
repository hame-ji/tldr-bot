# Architecture Design Document - Telegram Research Digest Bot

> A serverless personal knowledge pipeline built on GitHub Actions, Telegram, OpenRouter, and NotebookLM.

---

## Problem and Context

Engineers accumulate URLs throughout the day: articles shared in chats, YouTube talks flagged for later, PDFs worth reading, threads that should not disappear into a tab graveyard.

Most capture tools fail in one of two ways:

- they add friction at ingestion time
- they require more infrastructure than the problem warrants

The goal here is different: keep capture trivial, do the synthesis in batch, and deliver something readable without adding a server, database, or always-on worker.

---

## Design Axioms

These choices shape the system more than any implementation detail:

```text
Filesystem as database
Git as history
Telegram as ingestion queue
GitHub Actions as scheduler
```

- Filesystem as database: outputs are Markdown files that can be read, diffed, searched, and backed up with standard tools.
- Git as history: state and artifacts live in the repository, so operational history and content history stay aligned.
- Telegram as ingestion queue: the capture interface is a chat window that is already open on the device where links appear.
- GitHub Actions as scheduler: execution is ephemeral, scheduled, and self-contained.

---

## System Overview

```text
User -> Telegram Bot
         |
         | URLs accumulate as chat messages
         v
   GitHub Action (cron or manual dispatch)
         |
         v
   Python pipeline
   |-- Poll Telegram updates via state.json
   |-- Filter messages by TELEGRAM_CHAT_ID
   |-- Extract and normalize URLs
   |-- Fetch article/PDF content when applicable
   |-- Route summarization work:
   |   |-- article fetch ok -> OpenRouter
   |   |-- YouTube -> NotebookLM
   |   `-- eligible article fetch failure -> NotebookLM fallback
   |-- Write source artifacts to data/sources/YYYY-MM-DD/
   |-- Write failure artifacts to data/failed/YYYY-MM-DD/
   |-- Generate digest at data/digests/YYYY-MM-DD.md
   |-- Send digest back to Telegram
   `-- Emit run_outcome / run_metrics to stdout

   Workflow post-processing
   |-- Extract pipeline outputs from logs
   |-- Persist state/data changes when required
   |-- Write GitHub job summary
   `-- Append recent run-history summary
```

The main path is content processing. The observability path runs beside it and turns structured pipeline output into workflow-level visibility.

---

## Components

| Component | Role | Notes |
|---|---|---|
| Telegram Bot | Ingestion interface and delivery channel | Same interface for input and output; filtered to one chat via `TELEGRAM_CHAT_ID` |
| GitHub Actions | Scheduler and execution runtime | Daily cron plus manual dispatch; no persistent process |
| Python pipeline (`src/`) | Orchestration, fetch, summarize, digest | Batch-oriented, one pass per run |
| OpenRouter | Article summarization backend | Used when article content was fetched successfully |
| NotebookLM | YouTube summarization and article fallback backend | Used directly for YouTube and selectively for fetch failures |
| Git repository | State, artifacts, and audit history | `state.json` plus `data/` outputs are committed |
| Telemetry layer | Operational visibility | Structured log lines, workflow extraction, job summary, run-history report |

---

## Data and State Ownership

- `state.json` stores the Telegram update cursor and is the only persistent polling state.
- `data/sources/YYYY-MM-DD/` stores successful summary artifacts.
- `data/failed/YYYY-MM-DD/` stores failure records with URL and error context.
- `data/digests/YYYY-MM-DD.md` stores the rendered daily digest.
- Workflow logs store operational signals (`run_outcome`, `run_metrics`) that can be parsed without reading repository files.

This keeps two concerns separate:

- content artifacts live in the repository as first-class outputs
- run visibility lives in workflow logs and summaries as first-class operational signals

---

## Backend Routing and Fallback

The system no longer has a single summarization path. Routing is based on URL kind and fetch outcome.

| Input / outcome | Backend / result |
|---|---|
| Article URL, fetch succeeds | Summarize with OpenRouter |
| YouTube URL | Summarize with NotebookLM |
| Article URL, fetch fails with supported fallback reason and fallback enabled | Retry summarization from URL with NotebookLM |
| Any URL with irrecoverable failure | Write failure record to `data/failed/` |

Supported article fallback reasons include network failures, blocked responses, TLS issues, short extraction results, and PDF extraction failures. This keeps the pipeline moving without hiding degraded cases.

The effect is deliberate:

- OpenRouter handles the normal article path where content is already available.
- NotebookLM handles source types or failure modes where URL-native processing is a better fit.
- Failure records remain visible even when fallback is available.

---

## Key Design Decisions

### 1. Batch processing over real-time processing

**Decision:** URLs accumulate during the day and are processed in one scheduled run.

**Why:** The value is in synthesis, not immediacy. Batch processing matches the digest model and keeps the runtime ephemeral.

### 2. Polling over webhooks

**Decision:** Telegram updates are fetched with polling at run time.

**Why:** Webhooks would require a reachable HTTPS endpoint and therefore a persistent service. Polling preserves the serverless constraint.

### 3. Committed state over external state stores

**Decision:** The Telegram cursor lives in `state.json` and is committed with the repository outputs.

**Why:** A single committed file is inspectable, durable, and easy to recover from. It avoids adding a second persistence system for one integer.

### 4. Filesystem artifacts over database records

**Decision:** Summaries, failures, and digests are stored as Markdown files under `data/`.

**Why:** The output is meant to be read directly. Markdown keeps the system portable and makes review/debugging possible with normal repository tools.

### 5. Provider split by capability, not by branding

**Decision:** OpenRouter and NotebookLM are used for different classes of work.

**Why:** Article summaries and URL-native source handling have different constraints. A split backend model keeps the normal path simple while preserving a fallback path for degraded fetch cases and YouTube sources.

### 6. Failure isolation over fail-fast behavior

**Decision:** A bad URL writes a failure record and the run continues.

**Why:** A daily digest is more useful with partial results than with no results. Failures are preserved as artifacts rather than hidden in logs only.

---

## Execution Model

The live workflow behavior is intentionally simple:

- the digest workflow runs on a daily cron and via manual dispatch
- required secrets are validated before the pipeline runs
- the pipeline executes through `python -m src`
- pipeline outputs are extracted from logs in a separate workflow step
- if no URLs were processed, the workflow skips commit and push
- if URLs were processed but no staged output changes exist, the workflow skips commit and push
- otherwise the workflow creates a standard daily commit and pushes it

The repository also contains pure commit-strategy logic for a one-commit-per-day amend policy, but the checked-in workflow currently documents and executes the simpler create-only behavior. This document describes the live workflow.

### NotebookLM credential lifecycle

- **Data plane (`digest.yml`)**
  - runs ingestion and daily digest generation
  - uses NotebookLM preflight in `enforce` mode as the default guardrail
  - keeps provider isolation: NotebookLM failures do not abort non-NotebookLM work
  - applies a NotebookLM auth circuit breaker: first auth failure in enforce mode skips remaining NotebookLM items in that batch

- **Control plane (`replay-notebooklm.yml`)**
  - runs operator-initiated auth-failure replay only
  - does not poll Telegram and does not mutate `state.json`
  - drains queued auth failures from `data/replay/notebooklm/pending/` and archives recovered entries under `data/replay/notebooklm/completed/`

- **Concurrency and consistency**
  - digest and replay workflows share the same GitHub Actions concurrency group (`digest-pipeline`)
  - this serializes queue mutations and prevents replay rewrite vs digest append races

---

## Observability and Run Telemetry

Observability is part of the system design, not an afterthought.

The pipeline emits two structured log contracts:

- `run_outcome`: digest creation and delivery outcome
- `run_metrics`: processed URL counts, source mix, failures, and elapsed time

The workflow consumes those signals in later steps to:

- extract outputs without re-running business logic
- write a job summary for the current run
- build a recent run-history summary from prior workflow logs

Telemetry failures are treated as non-blocking. A digest run that succeeds should still persist outputs even if summary extraction or historical reporting fails.

This separation has two effects:

- content generation remains independent from workflow reporting
- operational visibility improves without making the content path more fragile

---

## Failure Model

The system assumes individual URLs will fail for ordinary reasons: timeouts, blocked pages, extraction failures, provider errors, or stale authentication state.

The response is layered:

- recover when a different backend can handle the case
- record failures as dated artifacts when recovery is not possible
- continue the batch rather than abort the run
- keep telemetry/reporting non-blocking so successful content still lands

That model keeps the system honest about degraded inputs while preserving the daily digest as the primary output.

---

## Accepted Trade-offs

These limitations are deliberate for the current scope:

| Trade-off | Accepted because |
|---|---|
| No real-time processing | Conflicts with the serverless batch model |
| Single-user boundary | Keeps state, permissions, and delivery simple |
| Markdown artifacts instead of a queryable store | Readability and portability matter more than complex retrieval |
| Workflow-log telemetry instead of a dedicated monitoring stack | Operational visibility is needed, but full observability infrastructure would outweigh the problem |
| Partial results on degraded inputs | A daily digest with explicit failures is better than an all-or-nothing run |

---

## Evolution Path

The current shape leaves room for additive changes without changing the core architecture:

- alternate ingestion sources can feed the same fetch/summarize/digest pipeline
- richer Telegram commands can be layered onto the existing single-user interface
- additional reporting can build on existing telemetry contracts
- a richer retrieval layer can be added later without changing the artifact format

The clearest architectural break would be real-time or multi-user operation. Both would require revisiting the current state, scheduling, and delivery assumptions rather than extending them incrementally.

---

*Single-user system. Ephemeral execution. Durable artifacts and visible failure handling.*
