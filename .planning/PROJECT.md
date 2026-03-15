# Telegram Research Digest Bot

## What This Is

A serverless personal knowledge pipeline that turns effortless URL capture into a daily AI-generated digest. Send URLs to a Telegram bot throughout the day; each morning a summarized digest is delivered back to Telegram. No server to maintain, no app to open — just paste and receive.

## Core Value

A daily digest of everything you saved, summarized and delivered automatically, so nothing you save goes unread.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] User can send URLs to a Telegram bot with no friction (paste only)
- [ ] Pipeline fetches Telegram updates via polling at run time (no webhook)
- [ ] Pipeline extracts and normalizes URLs from Telegram messages
- [ ] Articles are fetched and summarized via Gemini 2.0 Flash
- [ ] YouTube URLs are processed natively by Gemini (no transcript extraction)
- [ ] Failed URLs are written to data/failed/ and processing continues (no abort)
- [ ] Daily digest is generated as a Markdown file in data/digests/
- [ ] Digest is delivered to Telegram at the end of each run
- [ ] Pipeline runs on a daily cron via GitHub Actions (no server required)
- [ ] Telegram polling offset is persisted in state.json (committed to repo)
- [ ] All summaries and digests are stored as Markdown files in the repository
- [ ] LLM output format is controlled by prompt files in prompts/ (not hardcoded)
- [ ] Pipeline can also be triggered manually via GitHub Actions workflow dispatch

### Out of Scope

- Multi-user / team mode — single-user personal tool, no plans to expand
- Real-time / on-demand processing — batch model is intentional; incompatible with serverless constraint
- Telegram bot commands (/queue, /retry) — additive future feature, not v1
- Weekly digest — additive future feature, not v1
- Cross-day URL deduplication — rare enough to defer; additive when needed
- RSS ingestion — future ingestion source, not v1
- Search / indexing — git grep is sufficient for personal use

## Context

- Architecture is fully designed and documented in `architecture.md` — this is a greenfield implementation of that design
- No credentials are set up yet: Telegram bot token and Gemini API key both need to be created as part of this work
- GitHub repository already exists (this repo) and will serve as both execution environment and filesystem knowledge base
- Gemini 2.0 Flash chosen for 1M context window, free tier, and native YouTube URL processing — no yt-dlp or transcript infrastructure
- One commit per day strategy: if a commit already exists for that day, amend it (clean history)

## Constraints

- **Runtime**: GitHub Actions only — no persistent server, no VPS, no webhook endpoint
- **Storage**: Repository filesystem only — no database, no external state stores
- **LLM**: Gemini 2.0 Flash — 1M context window, free tier sufficient for 1-10 URLs/day
- **Users**: Single user — ALLOWED_CHAT_ID filters to one Telegram chat
- **Language**: Python — pipeline implementation language per architecture doc

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Polling over webhooks | Serverless constraint makes webhooks impossible — no persistent endpoint | — Pending |
| state.json as committed file | Eliminates external state dependency; visible in Git log; no concurrency risk for daily runs | — Pending |
| Filesystem as knowledge base | Human-readable, git-diffable, searchable without tooling | — Pending |
| Prompt files as config surface | Tunable behavior without code changes | — Pending |
| Silent failure with failure records | One bad URL shouldn't kill the digest; paywalls are expected | — Pending |
| Gemini native YouTube processing | Eliminates yt-dlp + Whisper infrastructure layer | — Pending |

---
*Last updated: 2026-03-15 after initialization*
