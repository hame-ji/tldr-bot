<div align="center">
<pre> ______   __         _____     ______     ______     ______     ______
/\__  _\ /\ \       /\  __-.  /\  == \   /\  == \   /\  __ \   /\__  _\
\/_/\ \/ \ \ \____  \ \ \/\ \ \ \  __<   \ \  __<   \ \ \/\ \  \/_/\ \/
   \ \_\  \ \_____\  \ \____-  \ \_\ \_\  \ \_____\  \ \_____\    \ \_\
    \/_/   \/_____/   \/____/   \/_/ /_/   \/_____/   \/_____/     \/_/
</pre>
</div>

<p align="center">
  <img src="docs/header.png" alt="tldr-bot header" width="420" />
</p>

A personal Telegram-to-digest pipeline for turning saved URLs into a daily readable summary.

Built for a single-user workflow: capture links with near-zero friction during the day, then receive a structured digest automatically. The project is intentionally optimized for clear boundaries, low operational overhead, and durable history rather than product breadth.

## Why this exists

Saved links usually decay into unread tabs and bookmarks. This project keeps capture easy (`paste URL in Telegram`) and moves the effort to automation (`fetch -> summarize -> assemble -> deliver`).

## Design constraints

- Single-user by design
- Serverless runtime only (`GitHub Actions`)
- Filesystem persistence only (Markdown in Git)
- Batch digest model over real-time processing

## How it works

```text
User -> Telegram Bot
         |
         | URLs accumulate in chat messages
         v
   GitHub Action (daily cron or manual dispatch)
         |
         v
   Python pipeline
   |-- Poll Telegram updates via state.json
   |-- Filter messages by TELEGRAM_CHAT_ID
   |-- Extract URLs
   |-- Fetch article/PDF content
   |-- Route summarization:
   |   |-- article fetch ok -> OpenRouter
   |   |-- YouTube -> NotebookLM
   |   `-- eligible article fetch failure -> NotebookLM fallback
   |-- Write sources, failures, and digest under data/
   |-- Deliver digest back to Telegram
   `-- Emit structured run telemetry to workflow logs

   Workflow post-processing
   |-- Extract run outputs from pipeline logs
   |-- Write GitHub job summary
   `-- Append recent run-history summary
```

## What this repo optimizes for

- Polling over webhooks to preserve serverless operation
- `state.json` as committed state for auditable Telegram offset tracking
- Filesystem-as-database for human-readable, diffable, portable outputs
- OpenRouter for article summaries; NotebookLM for YouTube and fallback paths
- Prompt files (`prompts/*.txt`) as the main behavior surface
- One failed URL does not abort the daily run

## Repository map

- `src/` pipeline modules
- `data/sources/YYYY-MM-DD/` successful summary artifacts
- `data/failed/YYYY-MM-DD/` failure records with URL and error context
- `data/digests/YYYY-MM-DD.md` generated daily digest
- `prompts/` summarization and digest behavior
- `state.json` Telegram polling cursor

## Outputs and visibility

- Daily digests are written to `data/digests/`
- Per-URL summaries are written to `data/sources/`
- Failures are preserved in `data/failed/` rather than dropped from the run
- The pipeline emits structured `run_outcome` and `run_metrics` log lines consumed by the workflow summary layer
- GitHub Actions writes a job summary and a recent run-history summary for operational visibility

## Execution model

- Scheduled in `.github/workflows/digest.yml` (`07:00 UTC`) with manual dispatch support
- Single-user boundary enforced with `TELEGRAM_CHAT_ID`
- Empty-day and no-change runs skip persistence
- Successful runs with output changes create a standard daily commit and push it
- Telemetry and run-history reporting are non-blocking; they do not prevent digest persistence

## Local verification

Install `uv` first: https://docs.astral.sh/uv/getting-started/installation/

```bash
uv sync --frozen
uv run python -m unittest discover -s tests -p "test_*.py"
uv run python -m src
```

Enable repository hooks once per clone:

```bash
git config core.hooksPath .githooks
```

Required environment variables:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `OPENROUTER_API_KEY`

NotebookLM authentication is also required for YouTube summarization and NotebookLM article fallback. Configure one of:

- `NOTEBOOKLM_STORAGE_STATE`, or
- `NOTEBOOKLM_STORAGE_PATH`, or
- local `~/.notebooklm/storage_state.json` from `notebooklm login`

Optional NotebookLM auth preflight mode:

- `NOTEBOOKLM_PREFLIGHT_MODE` = `observe` (default), `enforce`, or `off`

## Documentation

- `architecture.md` - architecture rationale, backend routing, failure model, and observability
- `docs/operations.md` - operator playbook for common pipeline and provider failures
- `docs/drift-register.md` - resolved high-risk contract drift records
- `.planning/REQUIREMENTS.md` - requirement traceability
- `.planning/ROADMAP.md` - phase-based implementation roadmap

## Scope and intent

This is intentionally a personal tool, not a multi-tenant product. The repository centers on explicit constraints, transparent trade-offs, and reproducible automation.
