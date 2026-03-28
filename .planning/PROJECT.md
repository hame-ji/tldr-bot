# Telegram Research Digest Bot

## What This Is

A serverless personal knowledge pipeline that turns low-friction URL capture into a daily digest. URLs are captured through Telegram, processed in GitHub Actions, summarized via backend routing, assembled into Markdown, and delivered back to Telegram.

## Core Value

A daily digest of everything you saved, summarized and delivered automatically, so nothing you save goes unread.

## Current Product Scope (v1)

- Single-user Telegram capture (`TELEGRAM_CHAT_ID` boundary)
- Batch processing on daily schedule plus manual dispatch
- Article/PDF fetching and extraction with failure records
- Summarization routing:
  - OpenRouter for fetched article content
  - NotebookLM for YouTube URLs
  - NotebookLM fallback for eligible article fetch failures
- Digest generation and Telegram delivery
- Filesystem persistence in Git (`state.json`, `data/`)

## Out of Scope (v1)

- Multi-user / team mode
- Real-time webhook listener or always-on server
- Telegram command surface (`/queue`, `/retry`)
- Weekly digest, RSS ingestion, and cross-day deduplication
- External database/state store

## Constraints

- **Runtime:** GitHub Actions only
- **Storage:** repository filesystem + Git history
- **Users:** single-user boundary (`TELEGRAM_CHAT_ID`)
- **Language:** Python (`python -m src` entrypoint)
- **Backend split:** OpenRouter and NotebookLM are used for different source/quality paths

## Key Decisions (Live)

| Decision | Rationale |
|----------|-----------|
| Polling over webhooks | Preserves serverless operation; no externally reachable endpoint required |
| Committed polling cursor in `state.json` | Simple, auditable, recoverable state model |
| Filesystem artifacts under `data/` | Human-readable outputs, git-diffable history |
| Failure isolation | One bad URL should not abort the whole batch |
| Split summarization backends | Different source types/failure modes need different backend strengths |

## Source of Truth

- Runtime behavior contracts: `.github/workflows/digest.yml`, `src/main.py`
- Architecture rationale: `architecture.md`
- Product scope and requirement status: `.planning/REQUIREMENTS.md`

---
*Last updated: 2026-03-28 after truth-alignment refresh*
