# Codebase Structure

**Analysis Date:** 2026-05-31

## Directory Layout

```
tldr-bot/
├── src/                    # Pipeline source code (Python package)
│   ├── summarization/      # LLM summarization backends
│   └── telemetry/          # Metrics emission, log parsing, run history
│       └── run_history/    # GitHub Actions run history reporting
├── scripts/                # CI helper scripts (invoked as modules)
├── tests/                  # Unit tests (unittest, mirrors src/ layout)
├── prompts/                # LLM prompt templates (plain text)
├── data/                   # Pipeline output artifacts (committed)
│   ├── digests/            # Daily Markdown digests
│   ├── sources/            # Per-URL summary files, organized by date
│   ├── failed/             # Failure records, organized by date
│   ├── cache/              # OpenRouter model cache
│   └── replay/             # NotebookLM failure replay queue
├── docs/                   # Project documentation and images
├── .github/
│   └── workflows/          # GitHub Actions workflow definitions
├── .githooks/              # Git hooks (pre-commit)
├── .planning/              # GSD planning artifacts
├── .opencode/              # OpenCode configuration and GSD workflows
├── CLAUDE.md               # Root AI routing manifest
├── architecture.md         # Architecture design document (prose)
├── pyproject.toml          # Python project metadata (uv)
├── uv.lock                 # Dependency lockfile
├── state.json              # Telegram polling offset (committed state)
└── README.md               # Project overview
```

## Directory Purposes

**`src/`:**
- Purpose: Core pipeline implementation, importable as `src` package
- Contains: Python modules for each pipeline stage + internal utilities
- Key files:
  - `src/main.py`: Pipeline orchestrator (`run_pipeline()`, `main()`)
  - `src/__main__.py`: Entry point for `python -m src`
  - `src/telegram_client.py`: Telegram polling + digest delivery
  - `src/content_fetcher.py`: URL fetching, HTML/PDF extraction, public facade
  - `src/summarizer.py`: Batch summarization orchestrator with thread pools
  - `src/digest_generator.py`: Digest Markdown assembly
  - `src/workflow_commit_strategy.py`: Pure commit mode decision logic
  - `src/_config.py`: Config dataclasses + `*_from_env()` factories
  - `src/_types.py`: TypedDict contracts (`FetchResult`, `SummaryResult`, etc.)
  - `src/_failures.py`: Failure reason constants + `write_failure_record()`
  - `src/_prompts.py`: `load_prompt()` — reads prompt template files
  - `src/_url_utils.py`: URL classification, slugification, normalization
  - `src/CLAUDE.md`: Module-specific AI guidance

**`src/summarization/`:**
- Purpose: LLM backend implementations for summarization
- Contains: Protocol definition, OpenRouter backend, NotebookLM backend
- Key files:
  - `src/summarization/common.py`: `Summarizer` protocol, `summarize_item()`, `_timeout_result()`
  - `src/summarization/openrouter_backend.py`: `OpenRouterSummarizer` with free-model discovery, retry, rate-limit spacing
  - `src/summarization/notebooklm_backend.py`: Async NotebookLM client for YouTube + article fallback
  - `src/summarization/CLAUDE.md`: Subpackage-specific AI guidance

**`src/telemetry/`:**
- Purpose: Pipeline observability — metrics emission, log parsing, run history
- Contains: Metrics dataclass, stdout log parser, GitHub Actions run history subsystem
- Key files:
  - `src/telemetry/run_metrics.py`: `RunMetrics` frozen dataclass, `build_run_metrics()`, `to_log_line()`
  - `src/telemetry/pipeline_log_parser.py`: `extract_pipeline_outputs()` for CI output extraction
  - `src/telemetry/CLAUDE.md`: Subpackage-specific AI guidance

**`src/telemetry/run_history/`:**
- Purpose: Fetches past workflow run logs, parses metrics, renders performance table
- Contains: GitHub API client, log zip parser, snapshot models, report renderer
- Key files:
  - `src/telemetry/run_history/github_client.py`: `GitHubActionsClient` — lightweight urllib-based API client
  - `src/telemetry/run_history/parser.py`: `extract_run_metrics_from_logs_zip()` — parses zipped workflow logs
  - `src/telemetry/run_history/models.py`: `RunHistorySnapshot` frozen dataclass
  - `src/telemetry/run_history/report.py`: `fetch_history_snapshots()`, `render_performance_summary()`

**`scripts/`:**
- Purpose: CI helper scripts invoked as `python -m scripts.<name>`
- Contains: Pipeline output extraction, commit gate helper, CLAUDE.md sync validator, run history writer
- Key files:
  - `scripts/extract_pipeline_outputs.py`: Parses pipeline log, writes GitHub Actions outputs
  - `scripts/extract_processed_urls.py`: Extracts processed URL count for commit gate
  - `scripts/validate_claude_sync.py`: Pre-commit hook validating child CLAUDE.md co-staging
  - `scripts/write_run_history_summary.py`: Fetches history, writes performance table to step summary
  - `scripts/__init__.py`: Empty package marker

**`tests/`:**
- Purpose: Unit tests using `unittest` framework
- Contains: One test file per source module, mirroring `src/` naming
- Key files:
  - `tests/test_main.py`: Pipeline orchestration tests
  - `tests/test_content_fetcher.py`: URL fetching/extraction tests
  - `tests/test_summarizer.py`: Summarization backend, concurrency, thread safety tests
  - `tests/test_telegram_client.py`: Polling, URL extraction, chunking, HTML formatting tests
  - `tests/test_digest_generator.py`: Digest rendering tests
  - `tests/test_telemetry.py`: Metrics and log parser tests
  - `tests/test_run_history.py`: Run history snapshot and report tests
  - `tests/test_workflow_commit_strategy.py`: Commit mode decision tests
  - `tests/test_ci_scripts.py`: CI script subprocess tests
  - `tests/test_validate_claude_sync.py`: Pre-commit hook validation tests
  - `tests/test_youtube_summarizer.py`: YouTube/NotebookLM backend tests
  - `tests/CLAUDE.md`: Test-specific AI guidance

**`prompts/`:**
- Purpose: LLM prompt templates controlling output format
- Contains: Plain text files loaded at runtime by `src/_prompts.py`
- Key files:
  - `prompts/summarize.txt`: Article summarization prompt (OpenRouter + NotebookLM fallback)
  - `prompts/youtube_summarize.txt`: YouTube summarization prompt (NotebookLM)
  - `prompts/digest.txt`: Digest assembly template with `{{placeholder}}` substitution

**`data/`:**
- Purpose: Pipeline output artifacts, committed to Git
- Contains: Date-organized Markdown files + model cache
- Structure:
  - `data/digests/YYYY-MM-DD.md`: Daily assembled digests
  - `data/sources/YYYY-MM-DD/slug.md`: Per-URL summaries
  - `data/failed/YYYY-MM-DD/slug.md`: Failure records
  - `data/cache/openrouter_models.json`: TTL-cached model list
  - `data/replay/notebooklm/pending/YYYY-MM-DD.jsonl`: Replay queue entries

**`.github/workflows/`:**
- Purpose: GitHub Actions workflow definitions
- Key files:
  - `.github/workflows/digest.yml`: Daily pipeline (cron + manual)
  - `.github/workflows/ci.yml`: Unit tests on push/PR
  - `.github/workflows/opencode.yml`: AI code review on comment trigger
  - `.github/CLAUDE.md`: Workflow/scripts-specific AI guidance

**`.githooks/`:**
- Purpose: Git hooks for development workflow enforcement
- Key files:
  - `.githooks/pre-commit`: Runs `scripts/validate_claude_sync.py`

## Key File Locations

**Entry Points:**
- `src/__main__.py`: Pipeline entry (`python -m src`)
- `src/main.py:main()`: Pipeline logic entry
- `scripts/extract_pipeline_outputs.py`: CI output extraction entry
- `scripts/extract_processed_urls.py`: CI commit gate entry
- `scripts/write_run_history_summary.py`: CI run history entry
- `scripts/validate_claude_sync.py`: Pre-commit hook entry

**Configuration:**
- `pyproject.toml`: Project metadata, dependencies, Python version constraint
- `uv.lock`: Dependency lockfile
- `src/_config.py`: Runtime environment variable configuration
- `.github/workflows/digest.yml`: Workflow-level env vars and secrets

**Core Logic:**
- `src/main.py`: Pipeline orchestration
- `src/content_fetcher.py`: URL fetching and content extraction
- `src/summarizer.py`: Summarization batch orchest
- `src/summarization/openrouter_backend.py`: OpenRouter LLM integration
- `src/summarization/notebooklm_backend.py`: NotebookLM LLM integration
- `src/digest_generator.py`: Digest assembly
- `src/telegram_client.py`: Telegram API interaction

**Testing:**
- `tests/`: All test files
- Run command: `uv run python -m unittest discover -s tests -p "test_*.py"`

**State:**
- `state.json`: Telegram polling offset (single-field JSON)

## Naming Conventions

**Files:**
- Pipeline modules: `snake_case.py` (e.g., `content_fetcher.py`, `digest_generator.py`)
- Internal utilities: `_snake_case.py` with leading underscore (e.g., `_config.py`, `_types.py`, `_url_utils.py`)
- Test files: `test_<module>.py` mirroring source module name (e.g., `test_main.py` for `main.py`)
- Prompt templates: `snake_case.txt` (e.g., `summarize.txt`, `youtube_summarize.txt`)
- Data artifacts: `YYYY-MM-DD.md` for digests, `slug.md` for sources/failures

**Directories:**
- Subpackages: `snake_case/` (e.g., `summarization/`, `telemetry/`, `run_history/`)
- Data directories: date-based `YYYY-MM-DD/` subdirectories under `sources/`, `failed/`

**Imports:**
- All `src/` imports use `from src.X import Y` (absolute, no relative imports except within `run_history/`)
- `run_history/` uses relative imports internally (`from .github_client import ...`)

## Where to Add New Code

**New Pipeline Stage:**
- Primary code: `src/<stage_name>.py`
- TypedDict contract: Add to `src/_types.py`
- Tests: `tests/test_<stage_name>.py`
- Wire into: `src/main.py:_run_pipeline_with_context()`

**New Summarization Backend:**
- Implementation: `src/summarization/<backend_name>_backend.py`
- Implement the `Summarizer` protocol from `src/summarization/common.py`
- Wire into: `src/summarizer.py:_build_pipeline_summarizer()` and `summarize_items()`
- Tests: Add to `tests/test_summarizer.py` or `tests/test_youtube_summarizer.py`

**New CI Script:**
- Implementation: `scripts/<script_name>.py` with `main()` function and `if __name__ == "__main__"` guard
- Invoke as: `uv run python -m scripts.<script_name>`
- Tests: `tests/test_ci_scripts.py` (subprocess-based)

**New Telemetry Metric:**
- Add field to: `src/telemetry/run_metrics.py:RunMetrics` dataclass
- Populate in: `src/telemetry/run_metrics.py:build_run_metrics()`
- Parse in: `src/telemetry/pipeline_log_parser.py:extract_pipeline_outputs()`
- Update consumers: `.github/workflows/digest.yml` step outputs
- Tests: `tests/test_telemetry.py`

**New Prompt Template:**
- File: `prompts/<name>.txt`
- Load via: `src/_prompts.py:load_prompt("prompts/<name>.txt")`
- Config path: Add to relevant config dataclass in `src/_config.py`

**New Failure Reason:**
- Constant: Add to `src/_failures.py`
- Classify in: `src/content_fetcher.py:_classify_fetch_error()` if fetch-related
- Use in fallback routing: `src/summarizer.py:_ARTICLE_FETCH_FAILURE_REASONS`

**Utilities:**
- Shared helpers: `src/_<utility_name>.py` (underscore prefix for internal modules)
- URL utilities: Extend `src/_url_utils.py`
- Config: Extend `src/_config.py` with new dataclass + factory

## Special Directories

**`data/`:**
- Purpose: Pipeline output artifacts (digests, summaries, failures, cache)
- Generated: Yes — written by pipeline at runtime
- Committed: Yes — `git add data/` in digest workflow step

**`.claude/worktrees/`:**
- Purpose: Claude Code worktree copies (development artifacts)
- Generated: Yes — created by Claude Code tooling
- Committed: Yes (present in repo)

**`.planning/`:**
- Purpose: GSD planning documents and codebase analysis
- Generated: Yes — created by GSD commands
- Committed: Yes

**`.opencode/`:**
- Purpose: OpenCode configuration, GSD workflows, and references
- Generated: Partially
- Committed: Yes

---

*Structure analysis: 2026-05-31*
