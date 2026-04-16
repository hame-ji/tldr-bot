# NotebookLM Auth Renewal Runbook

Last-Reviewed-Date: 2026-04-01
Owner: @team-oncall
Service: digest pipeline (`.github/workflows/digest.yml`)

## Objective

Restore NotebookLM-backed summarization after auth expiration with deterministic steps and explicit closure criteria.

## Scope

- In scope: renewal and validation of NotebookLM auth material used by `NOTEBOOKLM_STORAGE_STATE`.
- Out of scope: changing fail-fast policy or workflow architecture.

## Trigger Conditions

Run this playbook when one or more are true:

- Pipeline logs include `notebooklm_auth_expired`.
- Job summary shows `NotebookLM preflight status: auth_expired` or `misconfigured`.
- Job summary shows `NotebookLM auth failures` greater than `0`.
- YouTube processing fails with NotebookLM auth-related errors.
- Article fallback to NotebookLM fails with auth-related errors.

## Impact

- YouTube summaries fail.
- Article fallback summaries fail.
- Failure records increase under `data/failed/YYYY-MM-DD/`.

## Prerequisites

- Access to the Google account used for NotebookLM.
- Repo write access to update GitHub Actions secrets.
- `notebooklm` CLI available locally.
- `gh` CLI authenticated for this repository (preferred path).

## Procedure

1. Refresh local NotebookLM session.

   ```bash
   uv run notebooklm login
   ```

2. Validate the refreshed state file exists and is valid JSON.

   ```bash
   test -f ~/.notebooklm/storage_state.json
   uv run python -m json.tool ~/.notebooklm/storage_state.json >/dev/null
   ```

3. Rotate `NOTEBOOKLM_STORAGE_STATE` in GitHub Actions.

   Preferred (`gh` CLI):

   ```bash
   gh secret set NOTEBOOKLM_STORAGE_STATE < ~/.notebooklm/storage_state.json
   ```

   UI fallback:

   - Repo `Settings` -> `Secrets and variables` -> `Actions`.
   - Update `NOTEBOOKLM_STORAGE_STATE` with full JSON from `~/.notebooklm/storage_state.json`.

4. Trigger a validation run.

   ```bash
   gh workflow run digest.yml
   ```

5. Open the newest `digest` run and inspect `Run pipeline entrypoint` logs.

   ```bash
    gh run list --workflow digest.yml --limit 1
    ```

6. Replay queued NotebookLM auth failures.

   ```bash
   gh workflow run replay-notebooklm.yml -f replay_limit=0
   ```

## Verification (Required)

Mark incident as `recovered` only if all checks pass:

- No `notebooklm_auth_expired` errors in the rerun.
- Job summary reports `NotebookLM preflight status: ok`.
- Job summary reports `NotebookLM auth failures: 0`.
- Replay summary shows pending remaining count is `0` (or bounded remainder if `replay_limit` was set).
- NotebookLM processing resumes (`summary:youtube:` log lines present when YouTube URLs are part of that run).
- New source outputs are written under `data/sources/YYYY-MM-DD/` for affected items.

If any check fails, incident is not recovered.

## Retry and Escalation

- Retry budget: 2 full renewal attempts max.
- If still failing after attempt 2, mark incident `escalated` and hand off.

Escalation evidence bundle:

- GitHub Actions run URL(s) for both attempts.
- Exact error lines (including first `notebooklm_*` failure).
- Timestamp and actor for the secret update.
- Confirmation that JSON validation passed locally.

## Common Pitfalls

- Updating a different repository's secret.
- Partial/truncated JSON pasted into the secret.
- Logging in with the wrong Google account.
- Declaring recovery before checking logs and artifacts.

## Exit Criteria

- `recovered`: all verification checks pass.
- `escalated`: retry budget exhausted with evidence bundle attached.
