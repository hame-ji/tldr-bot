# src/telemetry - Telemetry Module Instructions

Last-Reviewed-Date: 2026-03-21
Last-Reviewed-Commit: HEAD
Review-Note: Initial child CLAUDE split from parent.

## Scope

Applies to all files under `src/telemetry/`.

## Module Intent

- Preserve the telemetry contract consumed by CI log parsing and run history reporting.
- Keep telemetry output machine-readable and backward compatible where possible.
- Keep parsing/reporting resilient to malformed or partial historical data.

## Implementation Rules

- Prefer explicit schemas and strict key naming for emitted metrics.
- Keep parser behavior tolerant on input but explicit on output defaults.
- Isolate network access to dedicated clients; keep report rendering pure.

## Test Expectations

- Add regression tests for metrics parsing, fallback behavior, and run-history table
  rendering when telemetry contract or parser logic changes.
