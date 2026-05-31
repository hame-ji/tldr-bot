# External Integrations

**Analysis Date:** 2026-05-31

## APIs & External Services

**Telegram Bot API:**
- Purpose: Input source (URL polling) and output delivery (digest messages)
- SDK/Client: Raw HTTP via `requests` (no Telegram SDK)
- Implementation: `src/telegram_client.py`
- Endpoints used:
  - `GET /bot{token}/getUpdates` - Poll for new messages with offset-based pagination
  - `POST /bot{token}/sendMessage` - Deliver digest chunks (HTML parse mode, 4096 char limit)
  - `GET /bot{token}/getMe` - Token validation (in CI workflow)
  - `GET /bot{token}/deleteWebhook` - Clear webhook on startup (in CI workflow)
- Auth: `TELEGRAM_BOT_TOKEN` (env var / GitHub secret)
- Chat filtering: `TELEGRAM_CHAT_ID` (env var / GitHub secret, integer)
- State: `state.json` stores `telegram_offset` for resumable polling

**OpenRouter API:**
- Purpose: LLM-based article summarization using free models
- SDK/Client: Raw HTTP via `requests` (OpenAI-compatible chat completions format)
- Implementation: `src/summarization/openrouter_backend.py`
- Endpoints used:
  - `GET /api/v1/models` - Model discovery (free models only, cached with TTL)
  - `POST /api/v1/chat/completions` - Chat completion for summarization
- Auth: `OPENROUTER_API_KEY` (env var / GitHub secret, Bearer token)
- Base URL: `OPENROUTER_API_BASE` (default: `https://openrouter.ai/api/v1`)
- Model selection: `OPENROUTER_PREFERRED_MODELS` (comma-separated, e.g., `google/gemma-3-27b-it:free,qwen/qwen3-32b:free,deepseek/deepseek-r1:free`)
- Rate limiting: Configurable min spacing, exponential backoff with jitter, max retries
- Model cache: `data/cache/openrouter_models.json` (TTL: 6 hours / 21600s by default)
- Key config env vars:
  - `OPENROUTER_MIN_SPACING_SECONDS` (default: 1)
  - `OPENROUTER_MAX_RETRIES` (default: 6)
  - `OPENROUTER_INITIAL_BACKOFF_SECONDS` (default: 5)
  - `OPENROUTER_MAX_BACKOFF_SECONDS` (default: 120)
  - `OPENROUTER_MODELS_CACHE_TTL_SECONDS` (default: 21600)

**Google NotebookLM (via notebooklm-py):**
- Purpose: YouTube video summarization and article fallback summarization
- SDK/Client: `notebooklm-py` 0.3.4 (`notebooklm.NotebookLMClient`)
- Implementation: `src/summarization/notebooklm_backend.py`
- Workflow:
  1. Create temporary notebook (`client.notebooks.create`)
  2. Add URL as source (`client.sources.add_url`, with `wait=True`)
  3. Ask summarization prompt (`client.chat.ask`)
  4. Delete temporary notebook (`client.notebooks.delete`)
- Auth: `NOTEBOOKLM_STORAGE_STATE` (env var / GitHub secret, JSON browser storage state)
  - Alternative: `NOTEBOOKLM_STORAGE_PATH` (file path) or `~/.notebooklm/storage_state.json` (local default)
- Async: Uses `asyncio.run()` to bridge sync pipeline with async SDK
- Fallback: Articles failing fetch (HTTP_BLOCKED, NETWORK_ERROR, TLS_ERROR, etc.) retried via NotebookLM when `NOTEBOOKLM_ARTICLE_FALLBACK_ENABLED=true` (default: true)
- Prompt files:
  - `prompts/youtube_summarize.txt` - YouTube summarization
  - `prompts/summarize.txt` - Article fallback summarization

**GitHub Actions API:**
- Purpose: Run history telemetry and performance reporting
- SDK/Client: `urllib.request` (stdlib, no GitHub SDK)
- Implementation: `src/telemetry/run_history/github_client.py`
- Endpoints used:
  - `GET /repos/{repo}/actions/workflows/{file}/runs` - List past workflow runs
  - `GET /repos/{repo}/actions/runs/{id}/logs` - Download run logs (zip)
- Auth: `GITHUB_TOKEN` (automatic workflow token, Bearer)
- API version: `2022-11-28` (set via `X-GitHub-Api-Version` header)
- Used by: `scripts/write_run_history_summary.py` to build performance summary table in job summary

## Data Storage

**Databases:**
- None - No database. All state is file-based.

**File-Based State:**
- `state.json` - Telegram polling offset (`{"telegram_offset": int}`)
- `data/digests/{date}.md` - Generated daily digest Markdown files
- `data/sources/{date}/{slug}.md` - Individual summarization outputs
- `data/failed/{date}/{slug}.md` - Failure records with URL, timestamp, reason, error
- `data/cache/openrouter_models.json` - Cached OpenRouter free model list with TTL
- `data/replay/` - Replay data directory

**File Storage:**
- Local filesystem only (ephemeral GitHub Actions runner)
- Output artifacts committed back to repository via `git add state.json data/ && git commit && git push`

**Caching:**
- OpenRouter model list: JSON file cache at `data/cache/openrouter_models.json` with configurable TTL
- uv dependency cache: GitHub Actions `astral-sh/setup-uv@v7` with `enable-cache: true`

## Authentication & Identity

**Auth Provider:**
- Custom - No auth framework. All credentials are API keys/tokens passed via environment variables.

**Credential Summary:**
| Secret | Source | Used By |
|--------|--------|---------|
| `TELEGRAM_BOT_TOKEN` | GitHub secret | `src/telegram_client.py` |
| `TELEGRAM_CHAT_ID` | GitHub secret | `src/telegram_client.py` |
| `OPENROUTER_API_KEY` | GitHub secret | `src/summarization/openrouter_backend.py` |
| `NOTEBOOKLM_STORAGE_STATE` | GitHub secret | `src/summarization/notebooklm_backend.py` |
| `GITHUB_TOKEN` | Automatic (workflow) | `src/telemetry/run_history/github_client.py` |
| `OPENCODE_API_KEY` | GitHub secret | `.github/workflows/opencode.yml` (opencode bot) |

**Validation:**
- Pipeline validates required secrets at startup via shell `test -n` in `digest.yml`
- Config factories raise `RuntimeError` for missing required env vars (`src/_config.py`)
- Telegram token validated via `getMe` API call before pipeline runs

## Monitoring & Observability

**Error Tracking:**
- None - No external error tracking service

**Logs:**
- Structured stdout logging via Python `logging` module and `print()` statements
- Two machine-readable log contracts emitted to stdout:
  - `run_outcome:{JSON}` - Pipeline outcome dict (consumed by `scripts/extract_pipeline_outputs.py` and `scripts/extract_processed_urls.py`)
  - `run_metrics:{JSON}` - Run metrics dataclass (consumed by `src/telemetry/pipeline_log_parser.py`)
- Pipeline log captured to `/tmp/pipeline.log` in CI, uploaded as artifact on failure
- Run history performance table written to `$GITHUB_STEP_SUMMARY` (visible in GitHub Actions UI)

**Telemetry Modules:**
- `src/telemetry/run_metrics.py` - `RunMetrics` frozen dataclass, `build_run_metrics()`, `to_log_line()`
- `src/telemetry/pipeline_log_parser.py` - Parse `run_outcome:` and `run_metrics:` from log text
- `src/telemetry/run_history/` - GitHub Actions log fetching, metrics parsing, Markdown report rendering

## CI/CD & Deployment

**Hosting:**
- GitHub Actions (serverless, no persistent infrastructure)

**CI Pipeline:**
- `.github/workflows/ci.yml` - Unit tests on push/PR to `main`
- `.github/workflows/digest.yml` - Daily digest pipeline (cron + manual)
- `.github/workflows/opencode.yml` - AI code review bot triggered by `/oc` comments

**Deployment Model:**
- No deployment. Pipeline runs in CI, outputs committed back to repo.
- Daily commit message format: `chore(digest): {YYYY-MM-DD} daily digest`
- Commit strategy logic in `src/workflow_commit_strategy.py` (pure logic, decides skip/create/amend)
- Empty-day commits skipped (no processed URLs = no commit)

**Git Hooks:**
- `.githooks/pre-commit` - Runs `scripts/validate_claude_sync.py` to enforce child `CLAUDE.md` co-staging with routed code changes

## Environment Configuration

**Required env vars (pipeline):**
- `TELEGRAM_BOT_TOKEN` - Telegram bot authentication
- `TELEGRAM_CHAT_ID` - Target chat for digest delivery
- `OPENROUTER_API_KEY` - OpenRouter LLM API access
- `NOTEBOOKLM_STORAGE_STATE` - NotebookLM browser storage state (JSON)

**Optional env vars (pipeline):**
- `OPENROUTER_API_BASE` - Override OpenRouter base URL
- `OPENROUTER_PREFERRED_MODELS` - Comma-separated preferred model order
- `OPENROUTER_MIN_SPACING_SECONDS` - Rate limit spacing
- `OPENROUTER_MAX_RETRIES` - Retry count
- `OPENROUTER_INITIAL_BACKOFF_SECONDS` - Initial backoff
- `OPENROUTER_MAX_BACKOFF_SECONDS` - Max backoff cap
- `OPENROUTER_MODELS_CACHE_PATH` - Model cache file path
- `OPENROUTER_MODELS_CACHE_TTL_SECONDS` - Model cache TTL
- `OPENROUTER_MAX_CONCURRENCY` - Thread pool size (default: 1, max: 3)
- `NOTEBOOKLM_MAX_CONCURRENCY` - Thread pool size (default: 1, max: 3)
- `NOTEBOOKLM_STORAGE_PATH` - File path alternative to storage state env var
- `NOTEBOOKLM_SUMMARIZE_PROMPT_PATH` - YouTube prompt file path
- `NOTEBOOKLM_ARTICLE_SUMMARIZE_PROMPT_PATH` - Article fallback prompt file path
- `NOTEBOOKLM_ARTICLE_FALLBACK_ENABLED` - Enable/disable article fallback (default: true)

**Secrets location:**
- GitHub repository secrets (Settings > Secrets and variables > Actions)
- No local `.env` files present or used

## Webhooks & Callbacks

**Incoming:**
- None - No webhook endpoints. Telegram interaction is poll-based via `getUpdates`.

**Outgoing:**
- None - No outbound webhook calls. All external communication is request-response.

---

*Integration audit: 2026-05-31*
