# .github/ and scripts/

Last-Reviewed-Date: 2026-03-23
Last-Reviewed-Commit: d66105c
Review-Note: Run history summary script now fetches a larger recent pool before selecting comparable runs for reporting.

- `ci.yml`: runs `unittest discover` on push/PR. Python 3.11 + uv. No secrets needed.
- `digest.yml`: daily 7am UTC cron + manual trigger. Validates Telegram creds, runs pipeline via `uv run python -m src`, extracts outputs in a separate module step, and treats telemetry/history failures as non-blocking while skipping empty-day commits.
- `scripts/extract_processed_urls.py`: helper entrypoint used by commit gate to read processed URL count from `run_outcome` contract only.
- `scripts/validate_claude_sync.py`: pre-commit hook. Ensures child CLAUDE.md files are co-staged with routed code changes and have updated review headers.
- Secrets handling: explicit and minimal. Don't scatter secrets across steps.
- Workflow output variable names are a contract (consumed by downstream steps). Don't rename without updating consumers.
- Test script behavior changes; hook validation has its own test module (`tests/test_validate_claude_sync.py`).
