# src/summarization/

Last-Reviewed-Date: 2026-03-21
Last-Reviewed-Commit: 1ee4e95
Review-Note: Polish: headers refreshed with parent CLAUDE.md amend.

- `Summarizer` protocol in `common.py` defines the contract. Backends implement it.
- OpenRouter backend: auto-discovers free models, caches with TTL, retries with exponential backoff, respects rate-limit spacing.
- Dual-backend concurrency: separate ThreadPoolExecutors for OpenRouter (articles) and NotebookLM (youtube + article fallback). Capped at `_MAX_BACKEND_CONCURRENCY=3`. 600s timeout per item.
- Fallback: articles failing fetch (HTTP_BLOCKED, NETWORK_ERROR, etc.) are retried via NotebookLM when `NOTEBOOKLM_ARTICLE_FALLBACK_ENABLED=true`.
- Output contract: `{"status": "ok"|"failed"|"ignored", "kind": str, "url": str, ...}`.
- Keep backends isolated from orchestration. No network in constructors/imports.
- Test backend selection, fallback paths, concurrency edge cases, and thread safety.
