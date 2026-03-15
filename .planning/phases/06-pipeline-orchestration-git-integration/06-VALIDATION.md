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
| STOR-02 | Workflow tests/dry-run checks verify one digest commit is created for a new UTC day when outputs changed |
| STOR-03 | Workflow tests/dry-run checks verify same-day re-run selects amend path instead of creating an additional commit |
| STOR-04 | Workflow logic verification confirms amend path uses `git push --force-with-lease` |

## Manual Smoke

1. Send URLs, run `workflow_dispatch` once:
   - digest arrives in Telegram,
   - one digest commit appears on remote.
2. Send additional URLs same UTC day, run `workflow_dispatch` again:
   - still one digest commit for that day (amended),
   - digest content reflects both runs.
3. Run workflow on empty day (no new URLs):
   - no digest message,
   - no new commit pushed.
