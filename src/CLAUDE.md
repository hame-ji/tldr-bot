# src - Runtime/Core Instructions

Last-Reviewed-Date: 2026-03-21
Last-Reviewed-Commit: HEAD
Review-Note: Initial child CLAUDE split from parent.

## Scope

Applies to `src/` except paths covered by more specific child routes:

- `src/summarization/`
- `src/telemetry/`

## Module Intent

- Keep the runtime pipeline deterministic and batch-oriented.
- Preserve failure isolation: one bad item must not stop the full run.
- Keep orchestration logic in `src/main.py` explicit and testable.

## Implementation Rules

- Keep interfaces between modules dictionary/typing contracts explicit.
- Preserve existing output artifact conventions under `data/`.
- Avoid hidden side effects; prefer explicit return values over globals.

## Test Expectations

- Add or update tests for behavior changes in orchestration, digest generation, or
  Telegram/workflow commit strategy interactions.
