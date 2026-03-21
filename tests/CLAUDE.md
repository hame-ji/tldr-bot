# tests - Test Suite Instructions

Last-Reviewed-Date: 2026-03-21
Last-Reviewed-Commit: HEAD
Review-Note: Initial child CLAUDE split from parent.

## Scope

Applies to all files under `tests/`.

## Module Intent

- Keep tests behavior-focused and deterministic.
- Prefer small fixtures and explicit assertions over broad snapshot coverage.
- Protect key pipeline invariants: failure isolation, output contracts, and parsing.

## Implementation Rules

- Add targeted tests for each behavior change in runtime, telemetry, or workflow scripts.
- Avoid test coupling to unstable formatting unless formatting is the contract.
- Keep mock boundaries at external I/O (network, filesystem side effects, environment).

## Test Expectations

- New logic in `src/`, `scripts/`, or workflow parsing paths must include regression
  coverage in the relevant test module.
