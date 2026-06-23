# Architecture

**Analysis Date:** 2026-05-31

## Pattern Overview

**Overall:** Serverless batch pipeline (cron-triggered, ephemeral execution)

**Key Characteristics:**
- Single-pass batch processing: poll → fetch → summarize → digest → send
- Filesystem-as-database: all state and output is Markdown/JSON files committed to Git
- No persistent server: runs exclusively as GitHub Actions workflow
- Failure isolation: one bad URL never stops the run; failures recorded as first-class artifacts
- Dual-backend summarization with concurrent thread pools (OpenRouter for articles, NotebookLM for YouTube + article fallback)

## Layers

**Orchestration Layer:**
- Purpose: Coordinates the pipeline stages, manages timing, emits telemetry
- Location: `src/main.py`
- Contains: `run_pipeline()`, `main()`, `_run_pipeline_with_context()`
- Depends on: All pipeline stage modules
- Used by: `src/__main__.py` (entry point), GitHub Actions workflow

**Ingestion Layer:**
- Purpose: Polls Telegram for new URLs, manages offset state
- Location: `src/telegram_client.py`
- Contains: `poll_urls()`, `poll_urls_from_env()`, `extract_urls()`, `load_offset()`, `save_offset()`
- Depends on: `src/_config.py` (TelegramConfig)
- Used by: `src/main.py`

**Content Fetching Layer:**
- Purpose: Retrieves article text from URLs, classifies URL types, handles PDFs
- Location: `src/content_fetcher.py`
- Contains: `fetch_urls()`, `fetch_url()`, `fetch_article_text()`, URL classification re-exports
- Depends on: `src/_url_utils.py`, `src/_failures.py`, `src/_prompts.py`, `trafilatura`, `pypdf`, `requests`
- Used by: `src/main.py`

**Summarization Layer:**
- Purpose: Generates summaries using LLM backends with retry, concurrency, and fallback
- Location: `src/summarizer.py` (orchestrator), `src/summarization/` (backends)
- Contains:
  - `src/summarizer.py`: `summarize_items()` — batch orchestrator with thread pools
  - `src/summarization/common.py`: `Summarizer` protocol, `summarize_item()`, shared helpers
  - `src/summarization/openrouter_backend.py`: `OpenRouterSummarizer` — free-model discovery, retry with backoff
  - `src/summarization/notebooklm_backend.py`: `summarize_url()`, `summarize_youtube()` — async NotebookLM client
- Depends on: `src/_config.py`, `src/_failures.py`, `src/_prompts.py`, `src/_url_utils.py`
- Used by: `src/main.py`

**Digest Assembly Layer:**
- Purpose: Renders Markdown digest from summary results using prompt template
- Location: `src/digest_generator.py`
- Contains: `generate_digest()`, `_render_digest()`
- Depends on: `src/_prompts.py` (digest template)
- Used by: `src/main.py`

**Delivery Layer:**
- Purpose: Sends digest to Telegram as chunked HTML messages
- Location: `src/telegram_client.py` (delivery functions)
- Contains: `send_digest()`, `send_digest_from_env()`, `chunk_text_by_paragraph()`, HTML formatting
- Depends on: `src/_config.py` (TelegramConfig), `requests`
- Used by: `src/main.py`

**Telemetry Layer:**
- Purpose: Structured metrics emission, log parsing, run history reporting
- Location: `src/telemetry/`
- Contains:
  - `src/telemetry/run_metrics.py`: `RunMetrics` dataclass, `build_run_metrics()`, `to_log_line()`
  - `src/telemetry/pipeline_log_parser.py`: `extract_pipeline_outputs()` — parses stdout for CI
  - `src/telemetry/run_history/`: GitHub Actions log fetching, metrics parsing, Markdown report rendering
- Depends on: Nothing in the pipeline core (pure parsing/rendering)
- Used by: `src/main.py` (emission), `scripts/` (CI consumption)

**Internal Utilities (underscore-prefixed):**
- Purpose: Shared primitives used across layers
- Location: `src/_config.py`, `src/_types.py`, `src/_failures.py`, `src/_prompts.py`, `src/_url_utils.py`
- Contains: Config dataclasses, TypedDict contracts, failure recording, prompt loading, URL utilities
- Depends on: Standard library + `python-slugify`
- Used by: All pipeline layers

## Data Flow

**Daily Digest Pipeline:**

1. `poll_urls_from_env()` reads `state.json` for Telegram offset, calls `getUpdates` API, extracts URLs, saves new offset
2. `fetch_urls()` iterates URLs: classifies each as `article` or `youtube`, fetches article text via HTTP (trafilatura for HTML, pypdf for PDFs), returns `FetchResult` dicts
3. `summarize_items()` partitions work into article pool (OpenRouter) and YouTube/fallback pool (NotebookLM), runs concurrent `ThreadPoolExecutor` pools (max 3 workers each, 600s timeout per item), writes summaries to `data/sources/YYYY-MM-DD/slug.md`
4. `generate_digest()` reads summary files, renders Markdown digest using `prompts/digest.txt` template, writes to `data/digests/YYYY-MM-DD.md`
5. `send_digest_from_env()` splits digest into sections, converts Markdown to HTML, chunks to 4096 chars, sends via Telegram `sendMessage` API
6. `build_run_metrics()` + `to_log_line()` emit structured `run_metrics:` JSON line to stdout for CI parsing

**State Management:**
- `state.json`: Single-field JSON (`{"telegram_offset": N}`), committed to repo, updated each run
- `data/sources/YYYY-MM-DD/slug.md`: Individual summary files per URL per day
- `data/digests/YYYY-MM-DD.md`: Assembled daily digest
- `data/failed/YYYY-MM-DD/slug.md`: Failure records with URL, error, reason, timestamp
- `data/cache/openrouter_models.json`: TTL-cached free model list (6h default)
- `data/replay/notebooklm/pending/`: JSONL replay queue for NotebookLM failures

**Failure Flow:**
- Fetch failure → `write_failure_record()` writes to `data/failed/` → item passes through to summarizer with `status: "failed"`
- Article fetch failure + NotebookLM fallback enabled → `summarize_failed_article_item()` retries via NotebookLM URL summarization
- Summarization failure → `write_failure_record()` → item included in digest with error info
- Timeout → `_timeout_result()` with `reason: "summarization_timeout"`

## Key Abstractions

**TypedDict Contracts (`src/_types.py`):**
- Purpose: Define inter-module data flow shapes without runtime overhead
- Examples: `FetchResult`, `SummaryResult`, `DigestResult`, `PollResult`, `PipelineOutcome`
- Pattern: `TypedDict` with `total=False` for optional fields; status field discriminates outcomes (`"ok"`, `"failed"`, `"ignored"`)

**Summarizer Protocol (`src/summarization/common.py`):**
- Purpose: Backend-agnostic summarization contract
- Examples: `Summarizer` protocol with `summarize_article()`, `summarize_article_from_url()`, `summarize_youtube()`
- Pattern: Protocol class; `_PipelineSummarizer` and `_NoopSummarizer` implement it

**Config Dataclasses (`src/_config.py`):**
- Purpose: Centralized, typed environment variable reading
- Examples: `OpenRouterConfig`, `NotebookLMConfig`, `TelegramConfig` — all `@dataclass(frozen=True)`
- Pattern: `*_from_env()` factory functions read `os.environ`, validate, return frozen dataclass

**Failure Reason Constants (`src/_failures.py`):**
- Purpose: Categorized failure types for routing and fallback decisions
- Examples: `HTTP_BLOCKED`, `TLS_ERROR`, `NETWORK_ERROR`, `ARTICLE_EXTRACT_TOO_SHORT`, `PDF_EXTRACT_FAILED`
- Pattern: String constants + `write_failure_record()` for artifact creation

**Commit Strategy (`src/workflow_commit_strategy.py`):**
- Purpose: Pure logic for deciding git commit mode (skip/create/amend)
- Examples: `decide_commit_mode()`, `daily_commit_message()`
- Pattern: Pure functions, no subprocess calls; consumed by workflow shell script

## Entry Points

**Pipeline Entry Point:**
- Location: `src/__main__.py` → `src/main.py:main()`
- Triggers: `uv run python -m src` (GitHub Actions digest workflow)
- Responsibilities: Runs full pipeline, emits `run_outcome:` and `run_metrics:` JSON lines to stdout

**CI Script Entry Points:**
- Location: `scripts/extract_pipeline_outputs.py`
- Triggers: `uv run python -m scripts.extract_pipeline_outputs /tmp/pipeline.log`
- Responsibilities: Parses pipeline stdout, writes GitHub Actions output variables

- Location: `scripts/extract_processed_urls.py`
- Triggers: `uv run python -m scripts.extract_processed_urls /tmp/pipeline.log`
- Responsibilities: Extracts processed URL count from `run_outcome:` line for commit gate

- Location: `scripts/write_run_history_summary.py`
- Triggers: `uv run python -m scripts.write_run_history_summary`
- Responsibilities: Fetches past workflow run logs, renders performance summary table to GitHub Step Summary

- Location: `scripts/validate_claude_sync.py`
- Triggers: Pre-commit hook (`.githooks/pre-commit`)
- Responsibilities: Validates child CLAUDE.md documents are co-staged with routed code changes

**Workflow Entry Points:**
- Location: `.github/workflows/digest.yml`
- Triggers: Daily cron (`0 7 * * *`), manual `workflow_dispatch`
- Responsibilities: Full pipeline execution, output persistence, telemetry

- Location: `.github/workflows/ci.yml`
- Triggers: Push to `main`, pull requests
- Responsibilities: Unit test execution via `unittest discover`

- Location: `.github/workflows/opencode.yml`
- Triggers: Issue/PR comments containing `/oc` or `/opencode`
- Responsibilities: AI-assisted code review via opencode

## Error Handling

**Strategy:** Failure isolation with explicit artifact recording. One bad item never stops the batch.

**Patterns:**
- Fetch errors: Caught broadly (`except Exception`), classified by `_classify_fetch_error()` into reason constants, written to `data/failed/YYYY-MM-DD/slug.md`
- Summarization errors: Caught broadly, written to failure records, item included in digest with error info
- Timeout: `FutureTimeoutError` from `ThreadPoolExecutor`, produces `_timeout_result()` with `reason: "summarization_timeout"`
- NotebookLM auth: `AuthError` mapped to `NOTEBOOKLM_AUTH_EXPIRED` reason, propagated as typed `NotebookLMSummaryError`/`YouTubeSummaryError`
- Config errors: Missing env vars raise `RuntimeError` with descriptive message at pipeline start (fail-fast for configuration)
- Telemetry errors: Non-blocking; `continue-on-error: true` in workflow, failures logged but don't block pipeline

## Cross-Cutting Concerns

**Logging:** `print()` for pipeline stage output (consumed by CI log parsing); `logging.getLogger(__name__)` for internal diagnostics in summarization and NotebookLM modules

**Validation:** URL classification via `classify_url()` (hostname matching); content length checks (`< 200` chars = extraction failure); Telegram message filtering by `allowed_chat_id`

**Authentication:** All credentials from environment variables via `src/_config.py` factories; NotebookLM storage state from `NOTEBOOKLM_STORAGE_STATE` env var or file path; Telegram bot token and chat ID from `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID`; OpenRouter API key from `OPENROUTER_API_KEY`

**Concurrency:** Dual `ThreadPoolExecutor` pools in `src/summarizer.py` — separate pools for OpenRouter (articles) and NotebookLM (YouTube + fallback), each capped at `_MAX_BACKEND_CONCURRENCY=3`. Rate-limit spacing via `_spacing_lock` in OpenRouter backend. 600s per-item timeout.

---

*Architecture analysis: 2026-05-31*
