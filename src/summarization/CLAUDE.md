# src/summarization - Summarization Module Instructions

Last-Reviewed-Date: 2026-03-21
Last-Reviewed-Commit: HEAD
Review-Note: Initial child CLAUDE split from parent.

## Scope

Applies to all files under `src/summarization/`.

## Module Intent

- Keep backend selection and summarization behavior explicit and auditable.
- Preserve stable prompt and output contracts consumed by upstream pipeline code.
- Treat model/backend fallbacks as deterministic behavior, not implicit retries.

## Implementation Rules

- Keep backend adapters isolated from orchestration concerns.
- Preserve typed helper boundaries and narrow function responsibilities.
- Avoid introducing network-heavy side effects in constructors or imports.

## Test Expectations

- Add focused tests for backend selection, fallback behavior, and formatting contracts
  when any summarization logic changes.
