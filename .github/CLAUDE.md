# .github/ and scripts/

Last-Reviewed-Date: 2026-03-22
Last-Reviewed-Commit: 12e0453
Review-Note: Restored empty-day commit skip by parsing run_outcome directly from pipeline.log in commit step.

- `ci.yml`: runs `unittest discover` on push/PR. Python 3.11 + uv. No secrets needed.
- `digest.yml`: daily 7am UTC cron + manual trigger. Validates Telegram creds, runs pipeline via `uv run python -m src`, extracts outputs in a separate module step, and treats telemetry/history failures as non-blocking while skipping empty-day commits.
- `scripts/validate_claude_sync.py`: pre-commit hook. Ensures child CLAUDE.md files are co-staged with routed code changes and have updated review headers.
- Secrets handling: explicit and minimal. Don't scatter secrets across steps.
- Workflow output variable names are a contract (consumed by downstream steps). Don't rename without updating consumers.
- Test script behavior changes; hook validation has its own test module (`tests/test_validate_claude_sync.py`).
