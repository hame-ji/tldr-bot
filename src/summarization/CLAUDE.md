# src/summarization/

Last-Reviewed-Date: 2026-05-12
Last-Reviewed-Commit: d182cea
Review-Note: NotebookLM auth preflight maps upstream auth-like ValueError failures to auth_expired while preserving backend_error for non-auth failures.

- `Summarizer` protocol in `common.py` defines the contract. Backends implement it.
- `notebooklm_backend.py`: NotebookLM backend for YouTube summarization and article fallback. Exposes `summarize_url()`, `summarize_youtube()`, and typed error classes.
- OpenRouter backend: auto-discovers free models, caches with TTL, retries with exponential backoff, respects rate-limit spacing.
- Dual-backend concurrency: separate ThreadPoolExecutors for OpenRouter (articles) and NotebookLM (youtube + article fallback). Capped at `_MAX_BACKEND_CONCURRENCY=3`. 600s timeout per item.
- Fallback: articles failing fetch (HTTP_BLOCKED, NETWORK_ERROR, etc.) are retried via NotebookLM when `NOTEBOOKLM_ARTICLE_FALLBACK_ENABLED=true`.
- Output contract: `{"status": "ok"|"failed"|"ignored", "kind": str, "url": str, ...}`.
- Keep backends isolated from orchestration. No network in constructors/imports.
- Imports use `from src._failures import ...`, `from src._prompts import ...`, `from src._url_utils import ...`.
- Test backend selection, fallback paths, concurrency edge cases, and thread safety.
