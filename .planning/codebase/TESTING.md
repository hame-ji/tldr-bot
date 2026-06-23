# Testing Patterns

**Analysis Date:** 2026-05-31

## Test Framework

**Runner:**
- `unittest` (stdlib) — no pytest
- Config: none (uses default unittest discovery)

**Assertion Library:**
- `unittest.TestCase` built-in assertions

**Run Commands:**
```bash
uv run python -m unittest discover -s tests -p "test_*.py"   # Run all tests (CI command)
uv run python -m unittest tests.test_main                     # Run single test module
uv run python -m unittest tests.test_summarizer.SummarizerTests.test_summarize_item_writes_source_file_for_article  # Run single test
```

**CI Integration:**
- `.github/workflows/ci.yml` runs `uv run python -m unittest discover -s tests -p "test_*.py"` on push/PR to `main`
- Python 3.11, ubuntu-latest, 10-minute timeout

## Test File Organization

**Location:**
- Separate `tests/` directory (not co-located with source)
- One test file per source module, matching name: `src/main.py` → `tests/test_main.py`

**Naming:**
- Files: `test_<module>.py`
- Classes: `<Module>Tests` or `<Feature>Tests` (e.g., `SummarizerTests`, `ClampConcurrencyTests`, `ConcurrencySummarizeItemsTests`)
- Methods: `test_<descriptive_behavior>` (e.g., `test_run_pipeline_returns_empty_day_outcome`, `test_fetch_url_classifies_tls_failures`)

**Structure:**
```
tests/
├── test_main.py                    # Pipeline orchestration (src/main.py)
├── test_content_fetcher.py         # URL fetching/extraction (src/content_fetcher.py)
├── test_summarizer.py              # Summarization orchestration (src/summarizer.py)
├── test_youtube_summarizer.py      # NotebookLM backend (src/summarization/notebooklm_backend.py)
├── test_digest_generator.py        # Digest assembly (src/digest_generator.py)
├── test_telegram_client.py         # Telegram API/chunking (src/telegram_client.py)
├── test_telemetry.py               # Metrics/log parsing (src/telemetry/*)
├── test_run_history.py             # Run history (src/telemetry/run_history/*)
├── test_workflow_commit_strategy.py # Commit decisions (src/workflow_commit_strategy.py)
├── test_ci_scripts.py              # Script entrypoints (scripts/*)
├── test_validate_claude_sync.py    # Pre-commit hook (scripts/validate_claude_sync.py)
└── CLAUDE.md                       # Test-specific guidance
```

## Test Structure

**Suite Organization:**
```python
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from src.digest_generator import generate_digest


class DigestGeneratorTests(unittest.TestCase):
    def test_generate_digest_writes_dated_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            prompt_path = Path(tmpdir) / "digest.txt"
            prompt_path.write_text("# Digest {{date}}\n\n{{summaries}}\n", encoding="utf-8")

            summary_file = Path(tmpdir) / "summary.md"
            summary_file.write_text("One summary", encoding="utf-8")

            result = generate_digest(
                items=[{"status": "ok", "url": "https://example.com/a", "summary_path": str(summary_file)}],
                run_date=date(2026, 3, 15),
                prompt_path=str(prompt_path),
                digests_base_dir=tmpdir,
            )

            digest_path = Path(result["digest_path"])
            self.assertTrue(digest_path.exists())
            self.assertEqual(digest_path.name, "2026-03-15.md")


if __name__ == "__main__":
    unittest.main()
```

**Patterns:**
- Each test class groups related behavior (e.g., `SummarizerTests`, `ClampConcurrencyTests`, `ConcurrencySummarizeItemsTests`, `OpenRouterThreadSafetyTests`)
- Multiple test classes per file when testing distinct aspects of the same module
- `if __name__ == "__main__": unittest.main()` at the bottom of every test file
- Return type annotation `-> None` on all test methods

## Mocking

**Framework:** `unittest.mock` (stdlib) — `patch`, `MagicMock`, `AsyncMock`

**Patterns:**

1. **Decorator stacking** — Multiple `@patch` decorators for I/O boundaries, applied bottom-up:
```python
@patch("src.main.send_digest_from_env")
@patch("src.main.generate_digest")
@patch("src.main.summarize_items")
@patch("src.main.fetch_urls")
@patch("src.main.poll_urls_from_env")
def test_run_pipeline_returns_non_empty_outcome(
    self,
    mock_poll_urls_from_env,
    mock_fetch_urls,
    mock_summarize_items,
    mock_generate_digest,
    mock_send_digest_from_env,
) -> None:
    mock_poll_urls_from_env.return_value = {
        "urls": ["https://one.example", "https://two.example"],
        "update_count": 2,
        "previous_offset": 10,
        "next_offset": 12,
    }
    mock_fetch_urls.return_value = [...]
    # ...
```

2. **Patch at module boundary** — Always patch where the name is looked up, not where defined:
```python
@patch("src.content_fetcher.requests.get")      # Correct: patches in consumer module
@patch("src.content_fetcher.trafilatura.extract") # Correct
```

3. **`side_effect` for exceptions and dynamic behavior:**
```python
mock_fetch_article_text.side_effect = SSLError("certificate verify failed")
mock_summarize_youtube.side_effect = YouTubeSummaryError(YOUTUBE_AUTH_EXPIRED, "session expired")
```

4. **`AsyncMock` for async NotebookLM client:**
```python
mock_client = AsyncMock()
mock_client.notebooks = mock_notebooks
mock_client.sources = mock_sources
mock_client.chat = mock_chat
mock_client.__aenter__ = AsyncMock(return_value=mock_client)
mock_client.__aexit__ = AsyncMock(return_value=False)
```

5. **Fake/stub classes instead of mocks for protocol implementations:**
```python
class _FakeSummarizer:
    def summarize_article(self, url: str, content: str) -> str:
        return "article summary for " + url

    def summarize_youtube(self, url: str) -> str:
        return "youtube summary for " + url
```

**What to Mock:**
- Network calls: `requests.get`, `requests.post`, `get_updates`, `_telegram_api`
- Filesystem: use `tempfile.TemporaryDirectory()` instead of mocking (real temp dirs)
- Environment variables: `patch.dict(os.environ, {...})` or custom `_override_env()` context manager
- External SDK clients: `NotebookLMClient`, `OpenRouterSummarizer`

**What NOT to Mock:**
- Pure functions (URL classification, slug generation, commit strategy decisions)
- Data transformations (metrics building, log parsing, digest rendering)
- Use real `tempfile.TemporaryDirectory()` for filesystem tests — don't mock `Path` operations

## Fixtures and Factories

**Test Data:**
- Inline dict literals matching the `FetchResult`/`SummaryResult` TypedDict contracts:
```python
# Fetch result fixture (inline in test)
{"status": "ok", "kind": "article", "url": "https://example.com/x", "content": "body"}
{"status": "failed", "kind": "article", "url": "https://x.com/status/123", "error": "x_low_signal_content", "failure_path": "data/failed/2026-03-15/x.md"}
{"status": "ok", "kind": "youtube", "url": "https://youtu.be/abc"}
{"status": "ignored", "kind": "unknown", "url": "https://example.com/unsupported"}
```

- Temporary prompt files written in test setup:
```python
with tempfile.TemporaryDirectory() as tmpdir:
    prompt_path = Path(tmpdir) / "digest.txt"
    prompt_path.write_text("# Digest {{date}}\n\n{{summaries}}\n", encoding="utf-8")
```

**Environment Override Helper** (defined in `tests/test_summarizer.py`):
```python
@contextlib.contextmanager
def _override_env(overrides: Dict[str, str]) -> Iterator[None]:
    """Temporarily set environment variables, restoring originals on exit."""
    saved: Dict[str, Optional[str]] = {name: os.environ.get(name) for name in overrides}
    os.environ.update(overrides)
    try:
        yield
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
```

**Usage:**
```python
with tempfile.TemporaryDirectory() as tmpdir, _override_env({"OPENROUTER_API_KEY": "key"}):
    results = summarize_items(items=[...], run_date=date(2026, 3, 15), sources_base_dir=tmpdir)
```

**Location:**
- No shared fixture files. All test data is inline or generated in temp directories.
- No conftest.py (unittest, not pytest).

## Coverage

**Requirements:** None enforced. No coverage tool configured in CI.

**View Coverage:**
```bash
uv run python -m coverage run -m unittest discover -s tests -p "test_*.py"
uv run python -m coverage report
```
(Not automated — manual only)

## Test Types

**Unit Tests:**
- Majority of the test suite. Each module's logic tested in isolation with mocked I/O.
- Focus on status dict contracts, routing decisions, counts — not formatting details.
- Files: `tests/test_main.py`, `tests/test_content_fetcher.py`, `tests/test_digest_generator.py`, `tests/test_telegram_client.py`, `tests/test_telemetry.py`, `tests/test_workflow_commit_strategy.py`, `tests/test_validate_claude_sync.py`

**Integration Tests:**
- `tests/test_ci_scripts.py` — runs scripts as subprocesses via `subprocess.run([sys.executable, "-m", "scripts.<name>"])`, verifying real CLI behavior, exit codes, and stdout/stderr output.
- `tests/test_summarizer.py` — `ConcurrencySummarizeItemsTests` tests real thread pool behavior with timing assertions.
- `tests/test_run_history.py` — `RunHistoryFetchTests` uses fake client classes to test multi-step fetch/parse pipeline.

**E2E Tests:**
- Not used. No browser or full-pipeline E2E tests.

**Concurrency Tests:**
- `tests/test_summarizer.py` has dedicated concurrency test classes:
  - `ConcurrencySummarizeItemsTests` — parallel articles + youtube, order preservation, failure isolation between backends
  - `OpenRouterThreadSafetyTests` — spacing lock, model init race, lock existence on new instances
  - `SummarizeItemsTimeoutTests` — per-item timeout isolation

```python
# Concurrency test pattern from tests/test_summarizer.py
def test_concurrent_articles_and_youtube_run_in_parallel(self, mock_cls, mock_yt) -> None:
    call_log: list[tuple[str, float]] = []
    lock = threading.Lock()

    class _SlowArticle:
        def summarize_article(self, url: str, content: str) -> str:
            start = time.monotonic()
            time.sleep(0.05)
            with lock:
                call_log.append(("article", start))
            return "article summary"

    mock_cls.from_config.return_value = _SlowArticle()
    # ... verify overlapping start times prove parallelism
```

## Common Patterns

**Async Testing:**
- `AsyncMock` from `unittest.mock` for async client methods
- Tests call synchronous wrappers (`summarize_youtube()`) that internally use `asyncio.run()`:
```python
@patch("src.summarization.notebooklm_backend.NotebookLMClient")
def test_happy_path_returns_answer(self, mock_client_cls, mock_resolve) -> None:
    mock_client = self._make_mock_client("video summary text")
    mock_client_cls.from_storage = AsyncMock(return_value=mock_client)
    result = summarize_youtube("https://youtu.be/abc", "Summarize this")
    self.assertEqual(result, "video summary text")
```

**Error Testing:**
- Assert on status dict fields, not exception types:
```python
def test_fetch_url_classifies_tls_failures(self, mock_fetch_article_text) -> None:
    mock_fetch_article_text.side_effect = SSLError("certificate verify failed")
    with tempfile.TemporaryDirectory() as tmpdir:
        result = fetch_url("https://example.com/tls", failed_base_dir=tmpdir)
    self.assertEqual(result["status"], "failed")
    self.assertEqual(result["reason"], TLS_ERROR)
```

- `assertRaises` for functions that raise directly (not status-dict functions):
```python
with self.assertRaises(RuntimeError):
    extract_pipeline_outputs("run_metrics:{}")

with self.assertRaises(YouTubeSummaryError) as ctx:
    summarize_youtube("https://youtu.be/abc", "Summarize")
self.assertEqual(ctx.exception.reason, YOUTUBE_AUTH_EXPIRED)
```

**Subprocess Testing** (for CI scripts):
```python
def test_extract_pipeline_outputs_module_writes_github_output(self) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        log_path = Path(temp_dir) / "pipeline.log"
        output_path = Path(temp_dir) / "github_output.txt"
        log_path.write_text(log_text, encoding="utf-8")

        env = os.environ.copy()
        env["GITHUB_OUTPUT"] = str(output_path)

        result = subprocess.run(
            [sys.executable, "-m", "scripts.extract_pipeline_outputs", str(log_path)],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
```

**Filesystem Testing:**
- Always use `tempfile.TemporaryDirectory()` for output directories
- Verify file existence with `Path(result["summary_path"]).exists()` or `Path(result["failure_path"]).exists()`
- Read back written content for content assertions

**Stdout Capture:**
```python
stdout = io.StringIO()
with redirect_stdout(stdout):
    main()
lines = stdout.getvalue().splitlines()
run_outcome_lines = [line for line in lines if line.startswith("run_outcome:")]
```

**Fake Client Pattern** (for testing without mocks):
```python
class FakeClient:
    def list_workflow_runs(self, workflow_file: str, per_page: int = 30):
        return [{"id": 300, "run_number": 30, "status": "completed", ...}]

    def download_run_logs_zip(self, run_id: int) -> bytes:
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, mode="w") as archive:
            archive.writestr("job/1.txt", 'run_metrics:{...}')
        return stream.getvalue()
```

## Key Testing Guidance

**From `tests/CLAUDE.md`:**
- Mock at I/O boundaries: network, filesystem, environment. Never hit real APIs.
- Tests are behavior-focused: assert on status dicts, counts, routing decisions — not formatting.
- Thread safety matters: `test_summarizer.py` verifies spacing locks, cache init races, and failure isolation under concurrency. Preserve these.
- Each module has a dedicated test file. New logic needs regression coverage in the matching file.
- Don't couple tests to unstable formatting unless formatting IS the contract (e.g., digest template).

**When adding tests:**
1. Identify the matching test file by module name: `src/X.py` → `tests/test_X.py`
2. Create a new test class if testing a distinct aspect, or add to existing class
3. Use `tempfile.TemporaryDirectory()` for any filesystem interaction
4. Mock at the I/O boundary (network, env vars), not internal functions
5. Assert on the status dict contract (`status`, `kind`, `url`, `error`, `reason`, `failure_path`)
6. For concurrency-sensitive code, add timing/ordering assertions
7. For subprocess scripts, test via `subprocess.run()` with `cwd=REPO_ROOT`

---

*Testing analysis: 2026-05-31*
