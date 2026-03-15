# Feature Research

**Domain:** Personal read-later / URL digest bot (Telegram + AI summarization + serverless)
**Researched:** 2026-03-15
**Confidence:** HIGH — grounded in Telegram Bot API docs, architecture.md, competitor analysis (Readwise Reader, Instapaper), and trafilatura/extraction library evaluation

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features the tool is useless without. Missing any of these = broken product.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| URL capture via paste | Zero-friction capture is the whole point; any friction breaks the habit | LOW | Bot receives any message containing a URL; no command prefix needed |
| URL extraction from raw text | Users paste URLs mid-sentence or with surrounding text | LOW | Regex extraction from message `.text` field; handle `t.me` previews too |
| Article content fetching | Summaries require source text | MEDIUM | Must handle redirects, JS-light sites; trafilatura is the go-to (HIGH confidence — benchmarked as best Python OSS extractor) |
| AI summarization per article | Core value delivery; without it, user just has a list of links | MEDIUM | Gemini 2.0 Flash via prompt files; content passed in request body |
| YouTube URL support | YT links are ~30% of what engineers share | LOW | Pass URL directly to Gemini — native support eliminates yt-dlp + Whisper infrastructure (HIGH confidence — documented Gemini 2.0 capability) |
| Daily digest delivery to Telegram | The "read" half of read-later; if it never arrives, nothing was saved | MEDIUM | `sendMessage` with Markdown parse_mode; 4096-char limit per message (HIGH confidence — official Telegram Bot API) |
| Polling offset persistence | Without it, URLs are reprocessed on every run | LOW | `state.json` committed to repo; single integer value |
| Graceful failure on bad URLs | Paywalled / dead links are expected; one failure must not kill the digest | LOW | Write to `data/failed/YYYY-MM-DD/slug.md` and continue |
| Scheduled execution | Daily cron is the delivery promise | LOW | GitHub Actions `schedule` trigger; 0 cost for single-user cadence |

---

### Differentiators (Competitive Advantage)

What sets this apart from Pocket/Instapaper/Readwise and makes it worth building.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Zero-friction Telegram ingestion | No app to open, no tab to manage — the phone you already have is the interface | LOW | Competitive gap: Pocket/Instapaper require browser extension or dedicated app; Telegram is always open |
| AI digest, not just a reading list | You receive synthesized content, not a queue of unread items — the digest is the product | HIGH | Readwise has Ghostreader (on-demand Q&A); this bot pushes a synthesized daily brief without any user action |
| Git-as-archive | Every digest is a commit; knowledge base is fully diffable, browsable, portable | LOW | No competitor stores your reading history as a git log; searchable with `git grep` |
| Native YouTube summarization | Competitors require a transcript step; this bot handles YT natively | LOW | Implementation cost is near-zero given Gemini's native support; strong differentiator vs. self-hosted alternatives |
| Serverless / zero ongoing cost | No VPS, no database, no monthly bill | LOW | Appeal to engineers who want to own their stack without ops burden; Pocket shut down (2025), Instapaper is acquisition-dependent |
| Prompt-file tunable output | Change digest format, summary depth, or language without touching code | LOW | Text-file config surface; meaningful for a power user running their own instance |
| Failure artifacts as first-class output | Failed URLs are stored, inspectable, retryable — not silently dropped | LOW | No competitor surfaces failure state this way; enables future `/retry` command cleanly |

---

### Anti-Features (Commonly Requested, Often Problematic)

Things that seem like good ideas but contradict the design axioms or add disproportionate complexity.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Real-time / on-demand summarization | "I want to see the summary now, not tomorrow" | Requires a persistent process or webhook endpoint — fundamentally incompatible with serverless constraint; doubles infrastructure complexity | Telegram manual dispatch from GitHub UI for immediate runs; design around the batch model being a feature |
| Telegram bot commands (/queue, /status, /retry) | Feels interactive and responsive | Requires stateful command parsing in the pipeline; `/retry` needs cross-day state; all commands require the bot to receive updates in real-time, which conflicts with daily-batch polling model | Defer to v1.x; the failure record in `data/failed/` is already the data layer for `/retry` |
| Read-it-later confirmation message | "Acknowledge my URL was saved" | Creates per-URL API round-trip during the day from a pipeline that only runs once; would require always-on listener or a separate acknowledgement mechanism | Accept the silence; user can verify in GitHub commits |
| Cross-day URL deduplication | "I shared the same link twice this week" | Requires a URL index file or database lookup; adds write-then-check complexity to the happy path | Defer; two summaries of the same article is a minor annoyance, not a broken feature |
| Tagging / categorization at ingest | "I want to organize my saves" | Requires user input at save time, which adds friction; the zero-friction capture is the core value proposition | Use Markdown frontmatter structure that supports tags additively later |
| Weekly digest | "A weekly recap would be valuable" | Additive scope in v1; requires a second workflow and aggregation logic | Implement as a second workflow reading existing daily digest files — no architectural change needed, pure addition in v1.x |
| RSS / feed ingestion | "Automate more of my reading sources" | Different ingestion model (pull vs. push); adds feed state management; separate concern from URL capture | Design the URL extraction stage to be source-agnostic; RSS is a drop-in later with its own module |
| Multi-user support | "My team wants this too" | `ALLOWED_CHAT_ID` is single-value by design; multi-user requires per-user state scoping, separate digest generation, potentially separate repos | Out of scope permanently for this tool; fork the repo for another user |
| Search / semantic search | "Find all my articles about X" | Requires an index or embeddings store; adds a dependency and maintenance burden | `git grep` is sufficient for personal use; if needed, a JSON URL manifest is an additive step |
| Telegram message formatting beyond Markdown | Rich cards, inline keyboards for each article | Added bot complexity; Telegram's `MarkdownV2` already supports headers, bold, links — sufficient for digest rendering | Stick with `parse_mode=MarkdownV2`; avoid inline keyboards in v1 |

---

## Feature Dependencies

```
[Daily cron trigger]
    └──requires──> [Polling offset persistence (state.json)]
                       └──requires──> [URL extraction from messages]
                                          └──requires──> [Bot receives Telegram messages]

[Daily digest delivery]
    └──requires──> [AI summarization per article]
                       └──requires──> [Article content fetching OR YouTube native pass-through]
                                          └──requires──> [URL type detection (article vs. YouTube)]

[Telegram message delivery]
    └──requires──> [Message chunking / length handling]
                       (4096 char hard limit per sendMessage call)

[Graceful failure handling]
    └──enhances──> [Daily digest delivery]
                   (digest sends even when some URLs failed)

[Prompt-file tunable output]
    └──enhances──> [AI summarization per article]
    └──enhances──> [Daily digest delivery]

[Failure artifacts]
    └──enables──> [/retry command (v1.x)]
    └──enables──> [Failure visibility in digest]

[Git-as-archive]
    └──requires──> [All outputs as Markdown files]
    └──enhances──> [One commit per day strategy]

[Weekly digest (v1.x)]
    └──requires──> [Daily digest files in data/digests/]
    └──requires──> [Second workflow trigger]

[Bot commands /retry (v1.x)]
    └──requires──> [Failure artifacts in data/failed/]
    └──requires──> [Command parser in telegram_client.py]
```

### Dependency Notes

- **Daily digest delivery requires message chunking:** The 4096-character limit per Telegram `sendMessage` call (HIGH confidence — official Bot API docs) means a digest covering 5–10 articles with summaries will routinely exceed one message. The pipeline must split the digest into chunks and send sequentially, or use a `sendDocument` approach to deliver the Markdown file directly.
- **YouTube support requires no extra infrastructure:** Gemini 2.0 Flash accepts YouTube URLs natively in the `contents` field — no transcript extraction step needed. This makes YouTube and article handling symmetrical in the pipeline: both are "give Gemini the source, get summary back."
- **Failure handling enhances digest quality:** Because failures are caught per-URL and execution continues, the digest always delivers something. A partial digest with a "failed URLs" section is better than no digest.
- **Prompt files enhance both summarization and digest shape:** The summary prompt controls per-article output format; a separate digest prompt controls how summaries are assembled into the final message. Both are tunable without code changes.
- **Weekly digest enhances but doesn't require daily changes:** It reads existing daily digest files. No changes to the core pipeline are needed.

---

## MVP Definition

### Launch With (v1)

Minimum viable product — what's needed to prove the concept delivers value.

- [x] **Polling offset persistence** — pipeline must not reprocess old messages every run
- [x] **URL extraction from raw Telegram message text** — handles pasted URLs with surrounding text
- [x] **URL type detection (article vs. YouTube)** — routes to correct fetch/pass strategy
- [x] **Article content fetching via trafilatura** — robust extraction with paywall/failure detection
- [x] **YouTube URL passed natively to Gemini** — no yt-dlp infrastructure
- [x] **Per-article AI summarization via Gemini 2.0 Flash** — controlled by prompt file
- [x] **Daily digest generation as Markdown file** — date-keyed, stored in `data/digests/`
- [x] **Digest delivery to Telegram with chunking** — handles 4096-char message limit
- [x] **Graceful failure with failure record** — one bad URL doesn't kill the digest
- [x] **GitHub Actions daily cron + manual dispatch** — zero-server execution

### Add After Validation (v1.x)

Features to add once the core pipeline is reliably delivering value.

- [ ] **Ingest acknowledgement message** — Trigger: user wants confirmation a URL was queued (requires always-on listener or separate lightweight mechanism; evaluate feasibility)
- [ ] **Telegram bot commands (/queue, /retry)** — Trigger: user wants interactive control; `/retry` is the highest-value first command given failure records already exist
- [ ] **Cross-day URL deduplication** — Trigger: same URL appearing in digest multiple times becomes noticeable annoyance
- [ ] **Weekly digest** — Trigger: daily digests are reliably delivered and valued; weekly summary is additive reading

### Future Consideration (v2+)

Features to defer until the tool has proven its daily value loop.

- [ ] **RSS / feed ingestion** — Defer: separate ingestion model; implement as a new module once core pipeline is stable
- [ ] **Tag/category support** — Defer: Markdown frontmatter structure supports this additively; wait for a real tagging need
- [ ] **Semantic search / knowledge base indexing** — Defer: `git grep` is sufficient; only valuable after significant archive accumulates
- [ ] **Multi-user support** — Defer: out of scope by design; architectural change required

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| URL capture (paste to Telegram) | HIGH | LOW | P1 |
| Polling offset persistence | HIGH | LOW | P1 |
| URL extraction from message text | HIGH | LOW | P1 |
| Article content fetching (trafilatura) | HIGH | LOW | P1 |
| YouTube native pass-through (Gemini) | HIGH | LOW | P1 |
| Per-article AI summarization | HIGH | MEDIUM | P1 |
| Daily digest generation as Markdown | HIGH | LOW | P1 |
| Telegram digest delivery with chunking | HIGH | LOW | P1 |
| Graceful failure + failure record | HIGH | LOW | P1 |
| GitHub Actions cron + manual dispatch | HIGH | LOW | P1 |
| Prompt-file tunable output | MEDIUM | LOW | P2 |
| Failure section in digest | MEDIUM | LOW | P2 |
| Git-as-archive (one commit per day) | MEDIUM | LOW | P2 |
| Bot commands (/retry) | MEDIUM | MEDIUM | P2 |
| Cross-day URL deduplication | LOW | LOW | P3 |
| Weekly digest | MEDIUM | LOW | P3 |
| RSS ingestion | MEDIUM | HIGH | P3 |
| Semantic search | LOW | HIGH | P3 |

**Priority key:**
- P1: Must have for launch — without these, the tool delivers no value
- P2: Should have — add after v1 is stable; meaningfully improves the experience
- P3: Nice to have — future consideration once the core loop is proven

---

## Competitor Feature Analysis

| Feature | Readwise Reader | Instapaper | This Bot |
|---------|----------------|------------|----------|
| Ingestion mechanism | Browser extension, email, API | Browser extension, bookmarklet | Telegram paste (zero-friction, mobile-first) |
| Summarization | Ghostreader (on-demand AI Q&A) | None | Auto-generated daily; delivered without user action |
| Digest / review delivery | Daily Review email (spaced repetition) | None | Telegram message, daily push |
| YouTube support | Transcript highlighting in app | No | Native Gemini pass-through (no transcript step) |
| Storage | Hosted, proprietary | Hosted, proprietary | Git repo (user-owned, portable, diffable) |
| Offline access | Yes (app) | Yes (app) | Git clone |
| Cost | Paid subscription | Free / paid | Free (GitHub Actions + Gemini free tier) |
| Operational burden | Zero (SaaS) | Zero (SaaS) | Zero (serverless) |
| Failure handling | Transparent (SaaS) | Transparent (SaaS) | Explicit failure records, inspectable |
| Batch model | Near-real-time | Near-real-time | Intentional batch (daily cron) |
| Customization | Limited | Limited | Full (prompt files, code) |

**Key insight:** Pocket shut down in 2025. Instapaper is SaaS-dependent. Readwise Reader is the strongest competitor but costs money and is a full reading app with UI — this bot differentiates by being push-first (digest comes to you), zero-infrastructure, and owning your data in git.

---

## Telegram-Specific Constraints

These constraints are hard limits that shape feature implementation, confirmed from official Bot API documentation (HIGH confidence):

| Constraint | Limit | Implication |
|------------|-------|-------------|
| `sendMessage` text length | 4096 characters | Digest must be split across multiple messages; implement chunking on message boundaries (not mid-word) |
| `getUpdates` storage window | 24 hours | URLs sent >24h before pipeline runs are lost; daily cron must run reliably every day |
| `getUpdates` offset | Must advance past each processed update | Polling offset in `state.json` must be saved and committed after every run — critical for correctness |
| Markdown parse mode | MarkdownV2 requires escaping of special chars | Digest template and prompt must avoid unescaped `_`, `*`, `[`, `]`, `(`, `)`, etc., or pipeline must escape them |
| Message send rate | No hard limit for private bots, ~30 msg/min suggested | Not a concern at 1–10 URLs/day; multi-message digest (chunked) safe to send sequentially |

---

## Sources

- **Telegram Bot API** — `sendMessage`, `getUpdates`, `Message` object: https://core.telegram.org/bots/api (accessed 2026-03-15, Bot API 9.5)
- **Trafilatura** — web content extraction library: https://trafilatura.readthedocs.io (accessed 2026-03-15, v2.0.0)
- **Readwise Reader** — feature set analysis: https://readwise.io/reader (accessed 2026-03-15)
- **Instapaper** — feature set analysis: https://instapaper.com (accessed 2026-03-15)
- **Pocket shutdown** — https://getpocket.com (accessed 2026-03-15 — site confirms shutdown)
- **Project context** — `/Users/jonas/dev/hameji/tldr-bot/.planning/PROJECT.md` and `architecture.md` (read as mandatory initial context)

---
*Feature research for: Personal Telegram URL Digest Bot*
*Researched: 2026-03-15*
