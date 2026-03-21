# .github and scripts - CI/Workflow Instructions

Last-Reviewed-Date: 2026-03-21
Last-Reviewed-Commit: HEAD
Review-Note: Initial child CLAUDE split from parent.

## Scope

Applies to:

- `.github/workflows/`
- `scripts/` used by CI/workflow jobs

## Module Intent

- Keep GitHub Actions workflows reproducible and failure-diagnosable.
- Keep helper scripts deterministic and safe for CI execution.
- Preserve pipeline observability and summary reporting behavior.

## Implementation Rules

- Keep secrets handling explicit and minimal in workflows.
- Keep scripts robust to missing/unknown telemetry values.
- Preserve existing workflow entrypoints and output variable contracts.

## Test Expectations

- Add or update tests when workflow-facing scripts change behavior, outputs, or
  parsing contracts used by workflow steps.
