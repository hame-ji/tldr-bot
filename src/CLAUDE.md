# src/

Last-Reviewed-Date: 2026-03-21
Last-Reviewed-Commit: 1ee4e95
Review-Note: Polish: test/orchestration bullet; headers refreshed with amend.

Covers `src/` except `src/summarization/` and `src/telemetry/` (routed separately).

- Pipeline is batch-oriented: poll URLs, fetch, summarize, digest, send. One pass.
- Failure isolation: one bad item must not stop the run. Log it, continue.
- Module contracts are dict-based (`{"status": "ok"|"failed", ...}`). Keep them explicit.
- Output artifacts go under `data/` (digests, sources, failures). Preserve conventions.
- No globals or hidden side effects. Functions return values.
- `workflow_commit_strategy.py` is pure logic (no subprocess). Keep it that way.
- When changing orchestration, digest assembly, or commit strategy, extend or adjust
  tests for those flows and keep dict contracts explicit.
