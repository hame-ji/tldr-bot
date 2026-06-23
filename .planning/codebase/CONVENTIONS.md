# Coding Conventions

**Analysis Date:** 2026-05-31

## Naming Patterns

**Files:**
- `snake_case.py` for all Python modules
- Underscore-prefixed files (`_types.py`, `_config.py`, `_failures.py`, `_prompts.py`, `_url_utils.py`) are internal/private modules — not entry points
- Test files use `test_<module>.py` prefix, one test file per source module

**Functions:**
- `snake_case` for all functions and methods
- Private helpers use leading underscore: `_extract_html_text()`, `_classify_fetch_error()`, `_split_digest_sections()`
- Factory functions use `*_from_env` suffix: `openrouter_config_from_env()`, `telegram_config_from_env()`, `notebooklm_config_from_env()`
- Public API functions are concise and verb-led: `fetch_url()`, `summarize_items()`, `generate_digest()`, `poll_urls()`, `send_digest()`

**Variables:**
- `snake_case` for all variables
- Module-level constants use `UPPER_SNAKE_CASE`: `HTTP_BLOCKED`, `TLS_ERROR`, `REQUEST_HEADERS`, `YOUTUBE_HOSTS`, `_MAX_BACKEND_CONCURRENCY`, `_FUTURE_TIMEOUT_SECONDS`
- Private module-level constants use `_UPPER_SNAKE_CASE`

**Types/Classes:**
- `PascalCase` for classes: `OpenRouterConfig`, `FetchProcessingError`, `OpenRouterSummarizer`
- `PascalCase` for TypedDicts: `FetchResult`, `SummaryResult`, `DigestResult`, `PollResult`, `PipelineOutcome`
- `PascalCase` for Protocols: `Summarizer`
- Private classes use leading underscore: `_PipelineSummarizer`, `_NoopSummarizer`, `_RetryingSummarizerBase`
- Custom exceptions suffix `Error`: `FetchProcessingError`, `YouTubeSummaryError`, `NotebookLMSummaryError`, `SourceAddError`

## Code Style

**Formatting:**
- No explicit formatter config (no `.prettierrc`, no `ruff.toml`, no `pyproject.toml` tool sections for formatting)
- Consistent 4-space indentation throughout
- Line length appears to target ~120 characters (no hard enforcement)
- String concatenation uses `+` operator for simple cases, f-strings for interpolation

**Linting:**
- No linter config file detected (no `.eslintrc`, `ruff.toml`, `pyproject.toml [tool.ruff]`)
- `# noqa: BLE001` used to suppress broad-exception warnings where intentional
- `# noqa: E402` used after try/except import blocks where import order is affected

**Type Annotations:**
- All modules begin with `from __future__ import annotations` to enable modern syntax
- Use `X | None` instead of `Optional[X]` (except `Optional` still used in `src/telemetry/run_metrics.py` and `src/telemetry/run_history/` — legacy pattern)
- Use `dict[str, Any]`, `list[str]` — lowercase generic containers
- TypedDict for inter-module data contracts (not dataclasses for pipeline data flow)
- `@dataclass(frozen=True)` for configuration objects: `OpenRouterConfig`, `NotebookLMConfig`, `TelegramConfig`, `RunMetrics`, `RunHistorySnapshot`
- `Protocol` for structural typing: `Summarizer` protocol in `src/summarization/common.py`
- `Literal` for constrained string types: `CommitMode = Literal["skip", "create", "amend"]`
- Return type annotations on all public and private functions

## Import Organization

**Order:**
1. `from __future__ import annotations` (always first)
2. Standard library imports (alphabetical)
3. Third-party imports (`requests`, `trafilatura`, `slugify`)
4. Internal `src.*` imports

**Pattern:**
```python
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any

import requests

from src._types import PipelineOutcome
from src.content_fetcher import fetch_urls
```

**Path Aliases:**
- None. All imports use absolute `from src.X import Y` paths.
- No relative imports except within `src/telemetry/run_history/` package (uses `from .github_client import ...`)

**Import rules:**
- All `src/` imports use `from src.X import Y` — never `import src.X`
- Optional dependencies use try/except with fallback stubs (see `src/content_fetcher.py` for `trafilatura` and `pypdf`, `src/summarization/notebooklm_backend.py` for `notebooklm`)

## Error Handling

**Strategy: Failure isolation — one bad item must not stop the pipeline run.**

**Patterns:**

1. **Status dict contract** — Functions return `dict[str, Any]` with `"status": "ok" | "failed" | "ignored"`, never raise on expected failures:
```python
# From src/content_fetcher.py
def fetch_url(url: str, failed_base_dir: str = "data/failed") -> dict[str, Any]:
    try:
        content = fetch_article_text(url)
    except Exception as exc:  # noqa: BLE001
        reason = _classify_fetch_error(exc)
        failure_path = write_failure_record(...)
        return {"status": "failed", "kind": "article", "url": url, "error": str(exc), ...}
    return {"status": "ok", "kind": "article", "url": url, "content": content}
```

2. **Failure record files** — All failures write a Markdown failure record via `write_failure_record()` in `src/_failures.py` to `data/failed/<date>/<slug>.md`.

3. **Reason constants** — Failure reasons are string constants defined in `src/_failures.py` and `src/summarization/notebooklm_backend.py`:
```python
HTTP_BLOCKED = "http_blocked"
TLS_ERROR = "tls_error"
PDF_EXTRACT_FAILED = "pdf_extract_failed"
NETWORK_ERROR = "network_error"
YOUTUBE_AUTH_EXPIRED = "youtube_auth_expired"
```

4. **Typed error classes with `.reason`** — Custom exceptions carry a `.reason` attribute for classification:
```python
class FetchProcessingError(RuntimeError):
    def __init__(self, reason: str, message: str) -> None:
        self.reason = reason
        super().__init__(message)
```

5. **Broad exception catching at boundaries** — `except Exception as exc:  # noqa: BLE001` at pipeline boundaries (fetch, summarize), with classification via `_classify_fetch_error()` or `getattr(exc, "reason", ...)`.

6. **RuntimeError for configuration errors** — Missing env vars, missing prompt files raise `RuntimeError` with descriptive messages:
```python
raise RuntimeError("Missing OPENROUTER_API_KEY environment variable")
raise RuntimeError("Missing prompt file: " + path)
```

## Logging

**Framework:** `logging` module (stdlib)

**Patterns:**
- Logger per module: `LOGGER = logging.getLogger(__name__)`
- Used in `src/summarizer.py` and `src/summarization/notebooklm_backend.py`
- Structured key=value format for machine-parseable log lines:
```python
LOGGER.info(
    "summarize_item kind=%s work_type=%s status=%s elapsed=%.2fs url=%s",
    kind, work_type, status, elapsed, url,
)
```
- `LOGGER.warning()` for non-fatal cleanup failures (e.g., notebook deletion after success)
- `print()` used in `src/main.py` for pipeline progress output (consumed by CI log parser)
- Structured stdout lines for CI parsing: `run_outcome:{json}`, `run_metrics:{json}`

## Comments

**When to comment:**
- Minimal inline comments. Code is self-documenting through naming.
- Comments explain "why" not "what" — e.g., `# noqa: BLE001` for intentional broad catches
- Docstrings are rare — only `_override_env` in `tests/test_summarizer.py` has one

**JSDoc/TSDoc:**
- Not applicable (Python codebase). No docstring convention enforced.

## Function Design

**Size:** Functions are small and focused. Most are under 30 lines. The largest functions are in `src/summarizer.py` (`summarize_items` at ~170 lines) due to concurrency orchestration.

**Parameters:**
- Use keyword arguments for clarity at call sites
- Default values for paths: `base_dir: str = "data/sources"`, `failed_base_dir: str = "data/failed"`
- Configuration objects (`OpenRouterConfig`, `TelegramConfig`) passed as single params instead of many individual args
- `@classmethod from_config()` factory pattern: `OpenRouterSummarizer.from_config(config)`

**Return Values:**
- Pipeline functions return `dict[str, Any]` status dicts (not dataclasses)
- Pure functions return simple types: `str`, `list[str]`, `bool`
- Config factories return frozen dataclasses
- Telemetry uses frozen dataclass `RunMetrics` serialized to JSON

## Module Design

**Exports:**
- `__all__` defined only in `src/content_fetcher.py` (public facade re-exporting from internal modules)
- Other modules rely on conventional Python import visibility

**Barrel Files:**
- `src/content_fetcher.py` acts as a public facade, re-exporting from `_failures`, `_prompts`, `_url_utils` for backward compatibility
- `src/__init__.py` is empty — no package-level exports

**Internal module pattern:**
- Underscore-prefixed modules (`_types.py`, `_config.py`, `_failures.py`, `_prompts.py`, `_url_utils.py`) are private implementation details
- Import from them directly when building new internal code: `from src._failures import write_failure_record`
- Public modules may re-export for backward compat

**Subpackage pattern:**
- `src/summarization/` — Backends isolated from orchestration. `common.py` defines `Summarizer` Protocol + shared helpers. Each backend (`openrouter_backend.py`, `notebooklm_backend.py`) implements the protocol independently.
- `src/telemetry/` — Metrics, log parsing, and run history. `run_history/` is a sub-subpackage with clean separation: `models.py` (data), `parser.py` (parsing), `github_client.py` (network), `report.py` (rendering, pure).

**No globals or hidden side effects:**
- Functions return values. No module-level mutable state.
- `__main__.py` is the single entry point: `from src.main import main; main()`

## Data Contracts

**TypedDict for pipeline data flow:**
```python
# src/_types.py
class FetchResult(TypedDict, total=False):
    status: str   # "ok" | "failed" | "ignored"
    kind: str     # "article" | "youtube" | "unknown"
    url: str
    content: str  # present when status="ok" and kind="article"
```

**Status dict keys are the contract:**
- `"status"`: always present — `"ok"`, `"failed"`, or `"ignored"`
- `"kind"`: always present — `"article"`, `"youtube"`, or `"unknown"`
- `"url"`: always present
- `"error"`: present when `status="failed"`
- `"failure_path"`: present when `status="failed"`
- `"reason"`: present when `status="failed"` — classifies the failure type
- `"summary_path"`: present when `status="ok"` for summarization results
- `"content"`: present when `status="ok"` for fetch results (articles only)

**Metric keys are the contract** — renaming or removing a key in `RunMetrics` breaks CI parsing. Add new keys, don't rename old ones.

## Environment Configuration

**Centralized env-var reading** in `src/_config.py`:
- Each config domain has a frozen dataclass + `*_from_env()` factory
- `OpenRouterConfig` / `openrouter_config_from_env()`
- `NotebookLMConfig` / `notebooklm_config_from_env()`
- `TelegramConfig` / `telegram_config_from_env()`
- Boolean env vars parsed via `_env_enabled()` accepting `true/false/yes/no/on/off/1/0`

## Concurrency Patterns

**Thread pools with bounded concurrency:**
- `ThreadPoolExecutor` with named threads: `thread_name_prefix="openrouter"` / `"notebooklm"`
- Concurrency clamped via `_clamp_concurrency()` with env-var control and max cap
- Per-future timeout with `_FUTURE_TIMEOUT_SECONDS = 600`
- Order preservation via pre-allocated `results[idx]` list

**Thread safety:**
- `threading.Lock()` for shared mutable state (spacing enforcement, model cache init)
- Double-checked locking for lazy initialization: `_models()` in `OpenRouterSummarizer`

---

*Convention analysis: 2026-05-31*
