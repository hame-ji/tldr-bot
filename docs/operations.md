# Operations Playbook

This playbook covers the common failures for the live workflow in `.github/workflows/digest.yml`.

## Quick Triaging Order

1. Open the latest `digest` workflow run in GitHub Actions.
2. Check `Run pipeline entrypoint` step outcome and `/tmp/pipeline.log` artifact (uploaded on failure).
3. Check `run_outcome:` and `run_metrics:` lines in pipeline logs.
4. Check job summary warnings for extraction/history (non-blocking) failures.

## Incident Playbooks

### Telegram auth or polling validation failure

- Symptom: `Validate Telegram bot token and clear webhook` or `Validate polling endpoint` fails.
- Impact: no URL ingestion and no digest run.
- Immediate action:
  - Verify `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` secrets.
  - Confirm bot token validity (`getMe`) and polling viability (`getUpdates`).
  - Ensure no stale webhook blocks polling (`deleteWebhook` step should pass).
- Recovery check: rerun workflow; pipeline prints `updates=...` and reaches `run_outcome:`.

### OpenRouter failures (auth, rate limit, model discovery)

- Symptom: summary failures mentioning `OpenRouter` or repeated retries/exhaustion.
- Impact: article summaries may fail and move to `data/failed/`; digest can still complete.
- Immediate action:
  - Verify `OPENROUTER_API_KEY` secret.
  - Verify optional model/env config values in workflow env.
  - If transient 429/load issues, rerun workflow later (retry/backoff is already built in).
- Recovery check: run completes with `summary_ok_count > 0` for article items where fetch succeeded.

### NotebookLM failures (auth expired, source processing)

- Symptom: errors such as `notebooklm_auth_expired`, `youtube_source_failed`, or fallback failures.
- Impact: YouTube and/or article fallback summaries fail; failure records are written.
- Immediate action: execute `docs/runbooks/notebooklm-auth-renewal.md`.
- Recovery check: runbook verification checks pass and incident exits as `recovered` or `escalated`.

### Empty-day or no-change commit skip

- Symptom: job summary shows `commit_status=skipped_empty_day` or `commit_status=no_changes`.
- Impact: expected no-op persistence behavior; not an incident by itself.
- Immediate action:
  - None unless this is unexpected.
  - If unexpected, inspect `processed_urls` from `run_outcome:` and staged output presence.
- Recovery check: status explanation matches run context (no new URLs or no diff).

### Telemetry extraction or run-history summary failure

- Symptom: warnings in job summary for output extraction or run history step.
- Impact: observability/reporting degraded; digest persistence path remains valid.
- Immediate action:
  - Inspect step logs for parser or GitHub API errors.
  - Re-run workflow if issue looks transient.
  - If persistent, fix `scripts/extract_pipeline_outputs.py` or `scripts/write_run_history_summary.py` contracts.
- Recovery check: warnings disappear in subsequent runs; metrics appear in job summary.

## Artifact Locations

- Digests: `data/digests/YYYY-MM-DD.md`
- Sources: `data/sources/YYYY-MM-DD/*.md`
- Failures: `data/failed/YYYY-MM-DD/*.md`
- Polling cursor: `state.json`

## Live Contracts to Preserve

- Pipeline logs include `run_outcome:` JSON and `run_metrics:` JSON.
- Telemetry/reporting failures stay non-blocking to digest persistence.
- Empty-day and no-diff runs do not commit.
