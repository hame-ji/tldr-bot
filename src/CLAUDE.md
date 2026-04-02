# src/

Last-Reviewed-Date: 2026-04-01
Last-Reviewed-Commit: 680150e
Review-Note: Pipeline outcome now exposes NotebookLM preflight/circuit-breaker/replay queue signals as the observability contract consumed by telemetry and workflows.

Covers `src/` except `src/summarization/` and `src/telemetry/` (routed separately).

- Pipeline is batch-oriented: poll URLs, fetch, summarize, digest, send. One pass.
- Failure isolation: one bad item must not stop the run. Log it, continue.
- Module contracts use TypedDict (`_types.py`): `FetchResult`, `SummaryResult`, `DigestResult`, `PollResult`, `PipelineOutcome`.
- Output artifacts go under `data/` (digests, sources, failures). Preserve conventions.
- No globals or hidden side effects. Functions return values.
- `workflow_commit_strategy.py` is pure logic (no subprocess). Keep it that way.
- When changing orchestration, digest assembly, or commit strategy, extend or adjust
  tests for those flows and keep dict contracts explicit.

## Internal modules (underscore-prefixed, not entry points)

- `_types.py`: TypedDict contracts for inter-module data flow.
- `_prompts.py`: `load_prompt()` — reads prompt template files.
- `_failures.py`: failure reason constants (`HTTP_BLOCKED`, etc.) and `write_failure_record()`.
- `_url_utils.py`: URL classification, slugification, normalization. Pure functions.
- `_config.py`: centralized env-var reading. `OpenRouterConfig`, `NotebookLMConfig`, `TelegramConfig` dataclasses and `*_from_env()` factories.

## Entry point

- `__main__.py` enables `python -m src`. CI uses this.
- `main.py` retains `if __name__ == "__main__"` for backward compat.

## Conventions

- All `src/` imports use `from src.X import Y` (no dual-import hack).
- Type hints use modern syntax via `from __future__ import annotations`: `X | None`, `dict[str, Any]`, `list[X]`.
- `content_fetcher.py` is a public facade: re-exports from `_failures`, `_prompts`, `_url_utils` for backward compat.
