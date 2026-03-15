# Phase 6: Pipeline Orchestration & Git Integration - Research

**Researched:** 2026-03-15
**Status:** Ready for planning

## Objective

Finalize end-to-end pipeline behavior in GitHub Actions so output artifacts are committed with a one-commit-per-day strategy (amend on same-day re-run), pushed safely with `--force-with-lease`, and skipped entirely on empty days.

## Requirement Mapping

- **STOR-01**: Persist summaries and digests as Markdown files in-repo.
- **STOR-02**: Commit pipeline changes using one-commit-per-day strategy.
- **STOR-03**: Amend same-day digest commit instead of creating duplicates.
- **STOR-04**: Push amended commit with `--force-with-lease`.

## Current Baseline

- `src/main.py` already orchestrates poll -> fetch -> summarize -> digest -> Telegram delivery.
- Empty-day guard exists in `src/main.py`: no digest write or delivery when no URLs are processed.
- `digest.yml` currently runs tests and pipeline but does not implement daily amend-or-create commit behavior for output artifacts.
- Existing smoke push step in `digest.yml` uses plain `git push`; this must not be used for daily digest amend flow.

## Design Notes

- Add an explicit run outcome signal from pipeline execution (processed URL count and/or digest path created) so workflow can skip commit/push on empty-day runs.
- Implement workflow commit logic as deterministic shell steps:
  - stage tracked outputs (`data/`, `state.json`),
  - no-op if no staged changes,
  - detect same-day digest commit by message prefix,
  - amend existing same-day commit or create a new one,
  - push with `--force-with-lease` only for amend path.
- Keep commit message date-keyed (UTC) so re-runs converge to one commit per day.
- Add orchestration tests around run outcome and commit gating inputs (unit-level where possible).

## Validation Architecture

- Fast path: run Python compile + full unit suite after orchestration code changes.
- Workflow validation: add scriptable checks for commit mode selection (create vs amend vs no-op) using mocked git history in CI-safe shell tests or dry-run helpers.
- Manual smoke: two `workflow_dispatch` runs on same UTC date should yield one updated digest commit on remote.

## Risks and Mitigations

1. **Accidental commit on empty day** -> gate git commit on explicit pipeline outcome (`processed_urls > 0`) and staged diff check.
2. **Unsafe amend push overwrites unexpected remote state** -> require `--force-with-lease` for amend path only.
3. **Date mismatch between runtime and commit logic** -> compute UTC date once in workflow and reuse for commit lookup/message.
4. **Pipeline exception aborts whole run** -> isolate per-item failures and ensure orchestrator still emits stable outcome summary.

---

*Phase: 06-pipeline-orchestration-git-integration*
*Research complete: 2026-03-15*
