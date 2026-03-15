# Project Research Summary

**Project:** tldr-bot — Personal Telegram URL Digest Bot
**Domain:** Serverless Telegram bot + AI summarization pipeline (Python + GitHub Actions + Gemini)
**Researched:** 2026-03-15
**Confidence:** HIGH

## Executive Summary

This is a personal read-later tool built as a serverless batch pipeline: URLs are captured via Telegram throughout the day, then once daily a GitHub Actions cron job polls the bot's message history, fetches/extracts article content, summarizes everything via Gemini 2.0 Flash, and delivers a single digest back to Telegram. The entire system runs on free-tier infrastructure with zero persistent servers — GitHub Actions handles execution, Git handles storage, Telegram handles ingestion and delivery. The architecture is deliberately simple: five flat Python modules, a state file, prompt files, and one workflow YAML. No database, no VPS, no always-on process.

The recommended implementation uses `pyTelegramBotAPI` (not `python-telegram-bot` v22+ — which is async-only and overengineered for a batch script), `google-genai` (not the deprecated `google-generativeai`), and `trafilatura` for content extraction. Gemini 2.0 Flash processes YouTube URLs natively, eliminating the yt-dlp/Whisper dependency entirely. All state is committed to Git as Markdown files, creating a fully diffable, searchable knowledge archive — the strongest differentiator versus SaaS alternatives like Instapaper (acquisition-dependent) or Pocket (shut down 2025).

The key risks are operational, not architectural: Telegram's `getUpdates` offset semantics require an `+1` increment that is easy to get wrong (causing infinite duplicate processing), the `GITHUB_TOKEN` needs an explicit `contents: write` permission grant, messages over 4096 chars must be chunked before sending, and `requests.get()` calls without timeouts can hang the entire GitHub Actions job for hours. All of these have clear prevention strategies documented in PITFALLS.md and must be addressed in the first two phases of implementation.

---

## Key Findings

### Recommended Stack

The stack is locked to synchronous Python 3.12 throughout — no async needed for a script that runs once per day and exits. The two most critical dependency decisions are: (1) use `google-genai` not `google-generativeai` (the latter has been archived/inactive since Nov 2025 and will break as the Gemini API evolves), and (2) use `pyTelegramBotAPI` (telebot) not `python-telegram-bot` (PTB v22+ is async-only, adding unnecessary complexity for a batch context). `trafilatura` is the consensus-best article extractor in Python — benchmarked above BeautifulSoup, newspaper3k, and readability — and handles boilerplate removal, paywall detection, and Markdown output natively. The "one commit per day, amend if same date" strategy for git history requires `fetch-depth: 0` on checkout and `--force-with-lease` on push.

**Core technologies:**
- `pyTelegramBotAPI 4.32.0`: Telegram polling + message delivery — synchronous, direct `get_updates()` API, no async overhead
- `google-genai 1.67.0`: Gemini 2.0 Flash summarization + native YouTube URL processing — the only current SDK (generativeai is deprecated)
- `trafilatura 2.0.0`: Article content extraction — best-in-class open-source extractor, single function call, Markdown output
- `requests 2.32.5`: HTTP client — synchronous, sufficient for sequential 1-10 URL/day batch
- `python-slugify 8.0.4`: Filesystem-safe filenames from URLs/titles
- `actions/setup-python@v6` + `actions/checkout@v4`: GitHub Actions toolchain for Python 3.12 + pip caching

### Expected Features

The v1 MVP is well-defined and tightly scoped. Every table-stakes feature has LOW-to-MEDIUM complexity with the chosen stack. The differentiators (zero-friction Telegram ingestion, AI push digest, Git-as-archive, native YouTube support, serverless zero-cost) are achievable at LOW complexity because they fall out naturally from the architecture rather than requiring extra engineering. The strongest anti-features to resist are: real-time acknowledgement (requires always-on process, breaks serverless axiom), Telegram bot commands (adds stateful parsing that conflicts with batch model), and multi-user support (out of scope permanently — fork the repo).

**Must have (table stakes):**
- URL capture via Telegram paste — zero-friction ingestion, no command prefix needed
- Polling offset persistence (`state.json`) — without this, every run reprocesses all history
- URL extraction from raw message text — regex handles surrounding text, not just bare URLs
- Article content fetching via trafilatura — robust extraction with paywall/failure graceful handling
- YouTube URL native pass-through to Gemini — no yt-dlp/Whisper infrastructure needed
- Per-article AI summarization via Gemini 2.0 Flash with prompt files
- Daily digest delivery to Telegram with message chunking (4096-char hard limit)
- Graceful failure with failure records in `data/failed/` — one bad URL must not kill the digest
- GitHub Actions daily cron + manual dispatch — scheduled execution with zero server

**Should have (competitive differentiators):**
- Prompt-file tunable output — change digest format without touching code
- Git-as-archive commit strategy — one commit per day, fully diffable knowledge base
- Failure section in digest — surface failed URLs to user rather than silently dropping
- No-URLs edge case handling — skip commit/delivery if nothing was processed

**Defer (v1.x / v2+):**
- Ingest acknowledgement message (requires always-on listener)
- Bot commands `/queue`, `/retry` (conflict with batch model; failure records are the data layer)
- Cross-day URL deduplication (minor annoyance, not critical failure)
- Weekly digest (additive workflow, no architectural change needed)
- RSS/feed ingestion, semantic search, multi-user support

### Architecture Approach

The architecture is a linear 5-module Python pipeline orchestrated by `main.py` and executed by a single GitHub Actions job. Modules have strict boundaries: `telegram_client.py` talks only to the Telegram API and `state.json`; `content_fetcher.py` does HTTP fetching with no AI calls; `summarizer.py` wraps Gemini with no file I/O; `digest_generator.py` assembles outputs with no external calls; `main.py` owns all control flow and error isolation. All outputs are Markdown files in a `data/` tree committed to Git. The "filesystem as database" and "Git as history" axioms drive every structural decision.

**Major components:**
1. `telegram_client.py` — Telegram `getUpdates` polling with offset management + `sendMessage` with chunking
2. `content_fetcher.py` — URL type classification (article vs. YouTube) + article HTML extraction via trafilatura
3. `summarizer.py` — Gemini 2.0 Flash wrapper; reads prompt files; handles article and YouTube paths
4. `digest_generator.py` — Assembles summaries into dated Markdown digest file using digest prompt
5. `main.py` — Pipeline orchestrator; per-URL try/except failure isolation; failure record writing
6. `.github/workflows/digest.yml` — Cron (07:00 UTC) + manual dispatch; amend-or-create commit strategy

### Critical Pitfalls

1. **Telegram offset off-by-one** — Store `max(update_id) + 1`, not `max(update_id)`. Getting this wrong causes infinite duplicate processing across every subsequent run. Address in Phase 2 (Telegram polling client).

2. **`state.json` offset not committed on partial failure** — Write and commit `state.json` immediately after `getUpdates`, before any URL processing begins. If digest generation fails, the offset must still be persisted. Bundling state with the digest commit causes re-processing on next run. Address in Phase 3 (pipeline orchestration).

3. **`GITHUB_TOKEN` missing `contents: write`** — Must explicitly declare `permissions: contents: write` in the workflow job. Default permissions are read-only on many repos. Without this, `git push` silently fails (403) and `state.json` is never committed. Address in Phase 1 (infrastructure scaffolding).

4. **`requests.get()` without timeout** — A single slow URL hangs the GitHub Actions job for up to 6 hours. Always use `timeout=(10, 30)`. Combine with the silent-failure model so timeouts write to `data/failed/` and continue. Address in Phase 4 (content fetching).

5. **Telegram 4096-char message limit** — `sendMessage` returns `400 Bad Request` silently for messages exceeding this limit. A digest covering 5+ verbose articles will routinely exceed it. Implement paragraph-boundary chunking before sending. Address in Phase 5 (digest delivery).

6. **Webhook blocking `getUpdates`** — An active webhook (from any previous experiment with the bot token) causes `getUpdates` to return empty arrays indefinitely. Run `deleteWebhook` during initial setup and add a startup assertion. Address in Phase 1 (bot setup).

7. **`google-generativeai` vs `google-genai` import confusion** — AI assistants and online examples use the deprecated `google.generativeai` import. Use only `google-genai` (`from google import genai`). Comment `requirements.txt` explicitly. Address in Phase 1 (dependency declaration).

---

## Implications for Roadmap

Based on research, the architecture has a clear 5-phase dependency chain. Each phase delivers something testable before the next begins. The build order from ARCHITECTURE.md is authoritative here — it's driven by external dependency verification (test Telegram before building AI, test AI before wiring pipeline).

### Phase 1: Infrastructure & Bot Setup
**Rationale:** All subsequent work requires credentials, repo structure, and a verified bot token. No code can be tested without this foundation, and two pitfalls (GITHUB_TOKEN permissions, webhook blocking polling) must be neutralized before writing any polling logic.
**Delivers:** Working repo scaffold, configured GitHub Secrets, verified bot token with no active webhook, `requirements.txt` with pinned dependencies, and a functioning `digest.yml` workflow that can push commits.
**Addresses:** Scheduling (GitHub Actions cron), serverless execution, zero-server architecture
**Avoids:** Pitfall 3 (GITHUB_TOKEN `contents: write`), Pitfall 4 (webhook blocking `getUpdates`), Pitfall 8 (SDK confusion — pin `google-genai`, never `google-generativeai`)

### Phase 2: Telegram Polling Client
**Rationale:** The bot's data input layer must work correctly and be verified in isolation before connecting to any AI or extraction logic. The offset off-by-one pitfall is the most catastrophic and easiest to get wrong — validate this first, independently.
**Delivers:** `telegram_client.py` with correct `getUpdates` offset handling, `ALLOWED_CHAT_ID` filtering, `state.json` read/write, and a verifiable test (run manually, send a URL, confirm it appears with correct offset in `state.json`).
**Implements:** Pattern 1 (Offset-Based Polling with Confirmed Acknowledgement)
**Avoids:** Pitfall 1 (offset off-by-one — `last_id + 1` not `last_id`), Pitfall 9 (state.json not committed on failure — write offset before processing begins)

### Phase 3: Content Fetching & URL Classification
**Rationale:** Content fetching is independent of AI and can be tested with real URLs without Gemini API calls. JS-rendered page failures and timeout hangs must be verified before the pipeline is wired together — catching them here prevents silent data loss in the full pipeline.
**Delivers:** `content_fetcher.py` with URL type detection (article vs. YouTube), trafilatura extraction, `timeout=(10, 30)` on all requests, content-length guard (< 200 chars → write to `data/failed/`), and HTTP status fast-fail (403/401 → failure record immediately).
**Uses:** `trafilatura 2.0.0`, `requests 2.32.5`
**Avoids:** Pitfall 6 (requests without timeout → workflow hangs), Pitfall 10 (JS-rendered pages producing empty summaries)

### Phase 4: Gemini Summarization
**Rationale:** External AI dependency is the most fragile integration point. Validate the Gemini client, prompt file loading, YouTube native processing, and rate limit handling in isolation before wiring into the full pipeline. This is where SDK import errors and 429 rate limits surface.
**Delivers:** `summarizer.py` with `google-genai` client, article and YouTube summarization paths, prompt file loading from `prompts/summarize.txt`, `time.sleep(1)` inter-request spacing, 429 retry logic, and safety block detection (`finish_reason == SAFETY` → failure record).
**Uses:** `google-genai 1.67.0`, `prompts/summarize.txt`
**Avoids:** Pitfall 7 (Gemini 429 rate limits — add sleep + retry), Pitfall 8 (SDK confusion — only `from google import genai`), Gemini safety block silently failing

### Phase 5: Digest Generation & Delivery
**Rationale:** Digest assembly and Telegram delivery are the final pipeline stages and depend on all previous phases working. The 4096-char chunking must be implemented here; this is also where empty-digest handling (no URLs today) must be accounted for.
**Delivers:** `digest_generator.py` assembling dated Markdown digest, `prompts/digest.txt` for formatting, `data/digests/YYYY-MM-DD.md` output; `send_digest.py` (or integrated into `telegram_client.py`) with paragraph-boundary chunking at 4096 chars, `parse_mode="Markdown"` explicit setting, no-send guard when digest is empty.
**Uses:** `google-genai` (digest assembly prompt), `pyTelegramBotAPI` (sendMessage)
**Avoids:** Pitfall 5 (Telegram 4096-char limit → chunk on paragraph boundaries)

### Phase 6: Pipeline Orchestration & GitHub Actions Integration
**Rationale:** Wire all modules together through `main.py` and verify the complete end-to-end flow in the GitHub Actions environment. The amend-or-create commit logic, concurrency group, and `fetch-depth: 0` requirements are only testable here.
**Delivers:** `main.py` orchestrating the full pipeline with per-URL try/except isolation and failure record writing; `digest.yml` with amend-or-create commit logic, `concurrency.cancel-in-progress: false`, `permissions: contents: write`, `fetch-depth: 0`; verified two-run-same-day amend test.
**Implements:** Pattern 2 (Silent Failure with Failure Record), Pattern 3 (Amend-or-Create Daily Commit)
**Avoids:** Pitfall 2 (git amend push conflict — fixed concurrency group, `--force-with-lease`), Pitfall 9 (state.json offset committed before processing), Pitfall 11 (GitHub cron dormancy — daily commits prevent it)

### Phase Ordering Rationale

- **Infrastructure before code:** GITHUB_TOKEN permissions and webhook state must be correct before any polling or pushing logic is written — these are invisible failures that waste debugging time if discovered later.
- **Telegram before AI:** The polling cursor (state.json offset) is the pipeline's most critical stateful element. Verifying it independently prevents the off-by-one pitfall from contaminating the AI integration phase.
- **Fetching before summarization:** Content fetching is synchronous and independently testable with real URLs. Isolating it prevents Gemini API call costs during debugging of extraction logic.
- **Summarization before orchestration:** Gemini is the most fragile external dependency. Verifying YouTube native support, rate limit handling, and safety blocks before wiring the full pipeline avoids mid-pipeline failures that are harder to isolate.
- **Delivery before orchestration:** Testing chunking with a synthetic >4096-char digest before wiring to the real pipeline catches the most common delivery failure without needing a full pipeline run.

### Research Flags

Phases likely needing `/gsd-research-phase` during planning:
- **Phase 4 (Gemini Summarization):** Gemini native YouTube processing was marked MEDIUM confidence in ARCHITECTURE.md — official docs fetch failed during research. Verify `contents=[youtube_url]` API usage before finalizing implementation. Also verify current free-tier RPM limits for Gemini 2.0 Flash.

Phases with well-documented patterns (skip deeper research):
- **Phase 1 (Infrastructure):** GitHub Actions permissions, secrets setup, and BotFather flow are all well-documented official processes.
- **Phase 2 (Telegram Polling):** Telegram `getUpdates` offset semantics are fully specified in Bot API 9.5 docs (HIGH confidence).
- **Phase 3 (Content Fetching):** trafilatura 2.0.0 is well-documented; requests timeout patterns are standard.
- **Phase 5 (Digest Delivery):** Telegram sendMessage chunking is a standard pattern; limit is officially documented.
- **Phase 6 (Pipeline + Actions):** GitHub Actions amend commit strategy is fully documented in ARCHITECTURE.md with verified patterns.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All packages verified against current PyPI releases (March 2026). google-genai deprecation of google-generativeai confirmed from official PyPI classifier. pyTelegramBotAPI vs PTB async distinction verified from package docs. |
| Features | HIGH | Grounded in Telegram Bot API 9.5 docs (official), trafilatura benchmarks, and competitor analysis (Readwise, Instapaper, Pocket shutdown confirmed). 4096-char limit verified from official Bot API. |
| Architecture | HIGH | GitHub Actions workflow patterns verified against official docs. Telegram `getUpdates` offset semantics verified from Bot API 9.5 spec. MEDIUM on Gemini native YouTube URL processing (see gaps below). |
| Pitfalls | HIGH | All critical pitfalls sourced from official Telegram Bot API, GitHub Actions docs, and google-genai SDK source. Offset off-by-one is a documented API behavior, not inference. |

**Overall confidence:** HIGH

### Gaps to Address

- **Gemini native YouTube URL processing:** ARCHITECTURE.md notes this was MEDIUM confidence because the official Gemini docs fetch redirected during research. The claim (pass YouTube URL directly in `contents` field; Gemini processes natively) is well-known and consistent with published Gemini 2.0 capabilities, but should be verified with a live test in Phase 4 before building the full YouTube path. Fallback: if native processing doesn't work as expected, fall back to writing the YouTube URL to `data/failed/` in v1 and researching yt-dlp integration for v1.x.
- **Gemini free-tier RPM limits for 2.0 Flash:** The pitfall (Pitfall 7) recommends `time.sleep(1)` between calls and 60-second backoff on 429. The exact current free-tier limits were not verified from a live API dashboard during research. The `sleep(1)` + retry pattern is safe regardless of exact limit. Verify limits during Phase 4 if running batches of 10+ URLs.
- **MarkdownV2 escaping:** FEATURES.md flags that Telegram's MarkdownV2 requires escaping of `_`, `*`, `[`, `]`, `(`, `)`, etc. The research recommends `parse_mode="Markdown"` (v1, not v2) or using HTML parse mode to avoid escaping complexity. The prompt files should be written to produce output compatible with the chosen parse mode. Decide and document which parse mode to use during Phase 5 implementation.

---

## Sources

### Primary (HIGH confidence)
- Telegram Bot API 9.5 (March 2026): https://core.telegram.org/bots/api — `getUpdates` offset semantics, `sendMessage` limits, `allowed_updates`, webhook exclusivity
- GitHub Actions official docs (2026-03-15): https://docs.github.com/en/actions — `permissions: contents: write`, cron syntax, `concurrency`, `workflow_dispatch`, `GITHUB_TOKEN`
- PyPI — `pyTelegramBotAPI 4.32.0`: https://pypi.org/project/pyTelegramBotAPI/
- PyPI — `google-genai 1.67.0`: https://pypi.org/project/google-genai/ (active SDK)
- PyPI — `google-generativeai` DEPRECATED: https://pypi.org/project/google-generativeai/ (classifier "7 - Inactive", support ended Nov 30 2025)
- PyPI — `trafilatura 2.0.0`: https://pypi.org/project/trafilatura/
- PyPI — `requests 2.32.5`: https://pypi.org/project/requests/
- `actions/setup-python@v6`: https://github.com/marketplace/actions/setup-python
- Google Gen AI Python SDK: https://github.com/googleapis/python-genai
- `google-generativeai` archive notice: https://github.com/google-gemini/deprecated-generative-ai-python

### Secondary (MEDIUM confidence)
- Gemini 2.0 Flash native YouTube URL processing — consistent with published Gemini 2.0 capabilities; official docs fetch redirected during research. Verify during Phase 4 implementation.
- Gemini free-tier rate limits — `time.sleep(1)` + 429 retry pattern based on documented free-tier constraints; exact current RPM limits not verified from live dashboard.

### Tertiary (Reference)
- Readwise Reader feature analysis: https://readwise.io/reader (competitor comparison)
- Pocket shutdown: https://getpocket.com (confirmed shutdown 2025)
- Instapaper: https://instapaper.com (competitor comparison)

---
*Research completed: 2026-03-15*
*Ready for roadmap: yes*
