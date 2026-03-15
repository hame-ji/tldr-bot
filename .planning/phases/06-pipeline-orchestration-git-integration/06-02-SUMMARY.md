---
phase: 06-pipeline-orchestration-git-integration
plan: 02
subsystem: ci-workflow
tags: [github-actions, commit-strategy, amend, force-with-lease, tests]
requires:
  - phase: 06-01
    provides: structured run_outcome from pipeline
provides:
  - Daily digest workflow commit mode branching (skip/create/amend)
  - Safe amend push path with `--force-with-lease`
  - Unit coverage for commit strategy behavior
requirements-completed: [STOR-02, STOR-03, STOR-04]
key-files:
  created: [src/workflow_commit_strategy.py, tests/test_workflow_commit_strategy.py]
  modified: [.github/workflows/digest.yml, architecture.md]
completed: 2026-03-15
---

# Phase 6 Plan 02 Summary

Implemented commit integration in GitHub Actions with rerun-safe amend behavior.

- Updated `.github/workflows/digest.yml` to parse `run_outcome`, skip commit path when no URLs were processed, and stage/persist output artifacts.
- Added create-vs-amend commit logic keyed by UTC daily digest subject, with amend path pushing via `git push --force-with-lease`.
- Added `src/workflow_commit_strategy.py` and `tests/test_workflow_commit_strategy.py` to lock commit mode expectations in tests.
- Updated `architecture.md` with explicit workflow guardrails for empty-day skip and same-day amend behavior.

Verification:
- `python3 -m compileall src`
- `python3 -m unittest discover -s tests -p "test_*.py"`
