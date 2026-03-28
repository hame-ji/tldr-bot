---
phase: 6
slug: pipeline-orchestration-git-integration
status: draft
nyquist_compliant: true
created: 2026-03-15
---

# Phase 6 - Validation Strategy

## Quick Commands

- `python3 -m compileall src`
- `python3 -m unittest discover -s tests -p "test_*.py"`

## Requirement Verification

| Requirement | Verification |
|-------------|--------------|
| STOR-01 | Unit tests and runtime checks verify summaries/digests are written as Markdown under `data/sources/` and `data/digests/` |
| STOR-02 | Workflow tests/dry-run checks verify output changes produce a daily digest commit with the standard subject format |
| STOR-03 | Workflow tests/dry-run checks verify runs skip commit/push when processed URL count is zero or when no staged output changes exist |
| STOR-04 | Workflow logic verification confirms the live path uses standard `git push` (no amend/force path) |

## Manual Smoke

1. Send URLs, run `workflow_dispatch` once:
   - digest arrives in Telegram,
   - one digest commit appears on remote.
2. Send additional URLs same UTC day, run `workflow_dispatch` again:
   - a new digest commit appears only if new outputs are staged,
   - digest content reflects both runs.
3. Run workflow on empty day (no new URLs):
   - no digest message,
   - no new commit pushed.
