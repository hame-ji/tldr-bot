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

A personal side project that turns saved URLs into a daily Telegram digest.

I built this for my own workflow: capture links with near-zero friction during the day, then receive a summarized digest automatically. This repository is intentionally single-user and optimized for architecture clarity, low operational overhead, and durable history.

## Why this exists

Saved links usually decay into unread tabs and bookmarks. This project keeps capture easy (`paste URL in Telegram`) and shifts the effort to automation (`daily synthesis + delivery`).

## Design constraints

- Single-user by design
- Serverless runtime only (GitHub Actions)
- Filesystem persistence only (Markdown in Git)
- Batch digest model over real-time processing

## Architecture at a glance

```text
User -> Telegram Bot
         |
         | URLs accumulate in chat messages
         v
   GitHub Action (daily cron or manual dispatch)
         |
         v
   Python pipeline
   |-- Poll Telegram updates (offset-based via state.json)
   |-- Filter messages by TELEGRAM_CHAT_ID
   |-- Extract URLs
   |-- Fetch article content (trafilatura)
   |-- Summarize via OpenRouter (free-model discovery + fallback)
   |-- Write summaries to data/sources/YYYY-MM-DD/
   |-- Write failures to data/failed/YYYY-MM-DD/
   |-- Generate digest at data/digests/YYYY-MM-DD.md
   `-- Deliver digest back to Telegram
```

## Key decisions and trade-offs

- Polling over webhooks to preserve serverless operation (no always-on endpoint)
- `state.json` as committed state for auditable Telegram offset tracking
- Filesystem-as-database for human-readable, diffable, portable outputs
- Prompt files (`prompts/*.txt`) as the behavior surface instead of hardcoded formatting rules
- Failure isolation: one bad URL writes a record and does not abort the daily run

## Repository map

- `src/` pipeline modules (polling, fetch, summarize, digest, orchestration)
- `data/sources/YYYY-MM-DD/` successful summary artifacts
- `data/failed/YYYY-MM-DD/` failure records with URL + error context
- `data/digests/YYYY-MM-DD.md` generated daily digest
- `prompts/summarize.txt` summarization behavior
- `prompts/digest.txt` digest rendering behavior
- `state.json` Telegram polling cursor

## Execution model

- Scheduled in `.github/workflows/digest.yml` (`07:00 UTC`) with manual dispatch support
- Single-user boundary enforced with `TELEGRAM_CHAT_ID`
- Day-scoped commit strategy:
  - first run of the day: standard commit/push
  - rerun on the same day: amend + `--force-with-lease`
- Empty-day runs skip digest delivery and commit

## Local verification

Install `uv` first: https://docs.astral.sh/uv/getting-started/installation/

```bash
uv sync --frozen
uv run python -m unittest discover -s tests -p "test_*.py"
uv run python src/main.py
```

Required environment variables:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `OPENROUTER_API_KEY`

## Documentation

- `architecture.md` - architecture rationale and trade-off analysis
- `.planning/REQUIREMENTS.md` - requirement traceability
- `.planning/ROADMAP.md` - phase-based implementation roadmap

## Scope and intent

This is intentionally a personal tool, not a multi-tenant product. The value of this repository is in architecture discipline under constraints: explicit decisions, transparent trade-offs, and reproducible automation.
