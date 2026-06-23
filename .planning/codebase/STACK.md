# Technology Stack

**Analysis Date:** 2026-05-31

## Languages

**Primary:**
- Python 3.11 (pinned `>=3.11,<3.12`) - All application code, scripts, tests

**Secondary:**
- Shell (POSIX sh) - Git hooks (`.githooks/pre-commit`)
- YAML - GitHub Actions workflow definitions (`.github/workflows/`)

## Runtime

**Environment:**
- CPython 3.11 on `ubuntu-latest` (GitHub Actions runner)
- Local development: macOS (darwin), Python 3.11 via uv

**Package Manager:**
- uv (Astral) - fast Python package installer and resolver
- Lockfile: `uv.lock` (present, committed, version 1 / revision 3)
- Install command: `uv sync --frozen`
- Run command: `uv run python -m src` (pipeline), `uv run python -m unittest discover -s tests -p "test_*.py"` (tests)
- Project is non-installable (`[tool.uv] package = false` in `pyproject.toml`)

## Frameworks

**Core:**
- None - The application is a batch pipeline script with no web framework. It runs as a single-pass module invoked via `python -m src`.

**Testing:**
- `unittest` (Python stdlib) - Test runner and assertion library
- Config: No config file; discovered via `python -m unittest discover -s tests -p "test_*.py"`

**Build/Dev:**
- uv - Dependency resolution, virtual environment management, script execution
- GitHub Actions - CI/CD orchestration (no local build step)

## Key Dependencies

**Critical (declared in `pyproject.toml`):**
- `requests` 2.32.5 - HTTP client for Telegram Bot API, OpenRouter API, and article fetching
- `trafilatura` 1.12.2 - HTML-to-text extraction for article content
- `notebooklm-py` 0.3.4 - Python SDK for Google NotebookLM (YouTube and fallback summarization)
- `pypdf` 5.4.0 - PDF text extraction for PDF article URLs
- `python-slugify` 8.0.4 - URL-to-slug conversion for output file naming
- `lxml_html_clean` 0.4.4 - HTML sanitization dependency for trafilatura

**Transitive (from `uv.lock`, notable):**
- `anyio` 4.12.1 - Async I/O (used by notebooklm-py)
- `certifi` 2026.2.25 - TLS certificate bundle (used by requests)
- `charset-normalizer` 3.4.6 - Encoding detection (used by requests)
- `click` 8.3.1 - CLI framework (used by notebooklm-py)
- `babel` 2.18.0 - Internationalization (used by trafilatura)

## Configuration

**Environment:**
- All configuration via environment variables, read centrally in `src/_config.py`
- Three config dataclasses: `OpenRouterConfig`, `NotebookLMConfig`, `TelegramConfig`
- Factory functions: `openrouter_config_from_env()`, `notebooklm_config_from_env()`, `telegram_config_from_env()`
- No `.env` files used; secrets injected via GitHub Actions `secrets` context
- Boolean env vars parsed by `_env_enabled()` accepting `0/false/no/off` and `1/true/yes/on`

**Build:**
- `pyproject.toml` - Project metadata and dependency declaration
- `uv.lock` - Frozen dependency resolution
- No `setup.py`, `setup.cfg`, or `Makefile`

**Prompt Templates:**
- `prompts/summarize.txt` - Article summarization system prompt (OpenRouter)
- `prompts/youtube_summarize.txt` - YouTube summarization prompt (NotebookLM)
- `prompts/digest.txt` - Digest assembly template with `{{placeholder}}` tokens

## Platform Requirements

**Development:**
- Python 3.11 (`>=3.11,<3.12`)
- uv package manager
- Git with custom hooks path: `git config core.hooksPath .githooks`
- Optional: local NotebookLM storage state at `~/.notebooklm/storage_state.json`

**Production:**
- GitHub Actions `ubuntu-latest` runner
- 20-minute timeout per digest run
- Daily cron at `0 7 * * *` (7:00 AM UTC)
- Manual trigger via `workflow_dispatch`
- No persistent server; fully ephemeral execution

**CI:**
- GitHub Actions `ubuntu-latest` runner
- 10-minute timeout per CI run
- Triggers on push to `main` and pull requests
- Runs `unittest discover` only (no linting, no type checking)

---

*Stack analysis: 2026-05-31*
