# Stack Research

> Historical note (2026-03-15): This file contains pre-pivot stack research.
> Current runtime stack is OpenRouter + article-only summarization (YouTube ignored in v1).

**Domain:** Serverless Telegram bot + AI summarization pipeline (Python + GitHub Actions + Gemini)
**Researched:** 2026-03-15
**Confidence:** HIGH — all recommendations verified against current PyPI releases

---

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.12 | Pipeline language | LTS-adjacent, supported by all libraries below; 3.13 available but some ecosystem lag; 3.11/3.12 are the sweet spot for stability + speed |
| `pyTelegramBotAPI` (telebot) | 4.32.0 (Mar 2026) | Telegram API client — polling + message send | **Use this, not python-telegram-bot.** telebot uses synchronous `requests` natively, has a direct `get_updates(offset, limit, timeout)` method that maps exactly to the polling model. python-telegram-bot v22 is async-only (asyncio) — that's great for a long-running bot server but adds unnecessary complexity for a batch script that runs once and exits. telebot is simpler for this use case. |
| `google-genai` | 1.67.0 (Mar 2026) | Gemini 2.0 Flash summarization + YouTube processing | **This is the current SDK.** `google-generativeai` is deprecated (Status: 7 - Inactive, support ended Nov 30 2025). `google-genai` is the unified Google Gen AI SDK, actively developed by Google LLC. Use `from google import genai`. |
| `trafilatura` | 2.0.0 (Dec 2024) | Article text extraction from URLs | Best-in-class open-source web content extractor. Benchmarks show it outperforms BeautifulSoup + custom parsers, newspaper3k, and readability in precision/recall. Used by HuggingFace, IBM, Microsoft Research. Handles boilerplate removal, metadata extraction, Markdown output natively. Single function call for most use cases. |
| `requests` | 2.32.5 (Aug 2025) | HTTP client for article fetching + Telegram API fallback | pyTelegramBotAPI uses requests internally; having it as an explicit dependency is good practice. Synchronous, battle-tested, zero setup. For a script that runs once/day with 1-10 URLs, async HTTP adds no benefit. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `python-slugify` | 8.0.x | Generate filesystem-safe slugs from URLs/titles | For `data/sources/YYYY-MM-DD/slug.md` filenames — converts arbitrary URLs/titles to safe, consistent filenames |
| `python-dateutil` | 2.9.x | Date parsing and formatting | For consistent date handling across digest file naming and frontmatter generation |
| `pathlib` (stdlib) | 3.4+ | Filesystem path handling | Built into Python; use over `os.path` for all file operations — cleaner, less error-prone |
| `json` (stdlib) | — | state.json read/write | Built in; sufficient for the single-field polling cursor file |
| `re` (stdlib) | — | URL extraction from Telegram messages | Built in; regex extraction of URLs from message text is sufficient, no need for an HTML parser at this step |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| `actions/setup-python@v6` | GitHub Actions Python setup | Current version (v6.2.0, node24 runtime). Use `python-version: '3.12'` + `cache: 'pip'` for fast runs. Requires runner v2.327.1+. |
| `actions/checkout@v4` | Checkout repo in Actions | Required for both reading state.json and committing results back |
| GitHub Secrets | `TELEGRAM_BOT_TOKEN`, `GEMINI_API_KEY`, `ALLOWED_CHAT_ID` | Store in repo Settings → Secrets → Actions. Access via `${{ secrets.NAME }}` in workflow, `os.environ['NAME']` in Python. Never hardcode. |
| `requirements.txt` | Dependency pinning | Use exact versions (`==`) for reproducible Actions runs. Do NOT use `>=` ranges — unpinned deps cause silent failures when a library releases a breaking change between runs. |

---

## Installation

```bash
# Core dependencies (requirements.txt)
pyTelegramBotAPI==4.32.0
google-genai==1.67.0
trafilatura==2.0.0
requests==2.32.5
python-slugify==8.0.4
python-dateutil==2.9.0
```

```yaml
# GitHub Actions workflow snippet
- uses: actions/checkout@v4
  with:
    token: ${{ secrets.GITHUB_TOKEN }}
    fetch-depth: 0  # needed for --amend commit strategy

- uses: actions/setup-python@v6
  with:
    python-version: '3.12'
    cache: 'pip'

- run: pip install -r requirements.txt

- name: Run pipeline
  env:
    TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
    GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
    ALLOWED_CHAT_ID: ${{ secrets.ALLOWED_CHAT_ID }}
  run: python pipeline.py
```

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| `pyTelegramBotAPI` (telebot) | `python-telegram-bot` (PTB) v22 | Use PTB if building a long-running async bot server with conversation handlers, job queues, and webhook support. PTB is overkill and adds async complexity for a batch script. |
| `pyTelegramBotAPI` (telebot) | Raw Telegram Bot API via `requests` | Only if you want zero dependencies — adds ~50 lines of boilerplate. Not worth it when telebot's overhead is negligible and the API coverage is complete. |
| `google-genai` | `google-generativeai` | **Never.** Deprecated, inactive, support ended Nov 30 2025. The PyPI classifier says "7 - Inactive". All Gemini API docs have been updated to use `google-genai`. |
| `trafilatura` | `newspaper3k` | Use newspaper3k only if you specifically need its NLP features (keyword extraction, summary) — but its extraction quality is lower than trafilatura, and it has heavier dependencies (NLTK). Not worth the trade-off. |
| `trafilatura` | `BeautifulSoup4` + custom parsing | Use BeautifulSoup when you need fine-grained control over specific site structures. For generic article extraction across arbitrary URLs, trafilatura's ML-based boilerplate detection outperforms manual CSS selectors. |
| `trafilatura` | `readability-lxml` | trafilatura uses readability as one of its backends AND applies additional heuristics on top of it. Using readability directly is strictly a downgrade — you get less accuracy with the same dependency weight. |
| `requests` | `httpx` | Use httpx if you need async HTTP (e.g., concurrent URL fetching). For a sequential batch pipeline, the requests API is simpler and httpx adds no benefit. httpx is the right choice if you ever parallelize URL processing. |
| `requests` | `aiohttp` | Use aiohttp only in async contexts. This pipeline is synchronous. |
| `python-slugify` | Manual URL hashing (e.g., `hashlib.md5`) | Use hash-based filenames if slug collisions are a concern at scale. For 1-10 URLs/day, slugified titles are more human-readable in the Git log — which matters for this project's "Git as history" philosophy. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `google-generativeai` | **Deprecated. Status "7 - Inactive" on PyPI. Support officially ended Nov 30, 2025.** Google explicitly says "Please be advised that this repository is now considered legacy." Last release: 0.8.6 (Dec 2025) with no new features. Will break as Gemini API evolves. | `google-genai` |
| `python-telegram-bot` v20+ for this use case | Fully async (asyncio-based since v20). Running `asyncio.run()` in a script that doesn't need concurrency adds complexity and has subtle interaction issues with some environments. Designed for long-running bot servers, not batch scripts. | `pyTelegramBotAPI` (telebot) |
| `yt-dlp` + `Whisper` for YouTube | Eliminates Gemini's native YouTube URL processing advantage, adds massive dependency weight (yt-dlp, ffmpeg, torch/whisper model), GitHub Actions storage/time cost. Architecture doc explicitly excludes this. | Pass YouTube URLs directly to `google-genai` — Gemini 2.0 Flash processes them natively |
| `newspaper3k` (newspaper4k) | Slow, NLP-heavy dependencies (NLTK), outdated extraction algorithms, lower accuracy than trafilatura on benchmarks. Last meaningful update years ago. | `trafilatura` |
| `dotenv` / `python-decouple` in Actions | Secrets should come from GitHub Secrets via environment variables, not `.env` files. `.env` files in repos are a security anti-pattern. | `os.environ` + GitHub Secrets |
| `APScheduler` or any in-process scheduler | This pipeline is serverless; scheduling is GitHub Actions' job via `on: schedule: cron:`. In-process schedulers require a persistent process. | GitHub Actions `on: schedule` |

---

## Stack Patterns by Variant

**For Telegram polling (batch script model):**
- Use `telebot.TeleBot(token).get_updates(offset=state['offset'], limit=100, timeout=0)`
- `timeout=0` for immediate return (don't long-poll — the script exits when done)
- Filter by `update.message.chat.id == int(ALLOWED_CHAT_ID)` immediately after fetching
- Advance offset to `max(update_id) + 1` after processing all updates

**For Gemini article summarization:**
```python
from google import genai
client = genai.Client(api_key=os.environ['GEMINI_API_KEY'])
response = client.models.generate_content(
    model='gemini-2.0-flash',
    contents=[prompt_text, article_text]
)
```

**For Gemini native YouTube processing:**
```python
# Pass URL directly — no transcript needed
response = client.models.generate_content(
    model='gemini-2.0-flash',
    contents=[prompt_text, youtube_url]  # Gemini fetches and processes natively
)
```

**For article extraction:**
```python
import trafilatura
downloaded = trafilatura.fetch_url(url)
text = trafilatura.extract(downloaded, output_format='markdown', include_comments=False)
# text is None if extraction fails (paywall, bot block, etc.) — handle gracefully
```

**For GitHub Actions commit (one-per-day amend strategy):**
```yaml
- name: Commit digest
  run: |
    git config user.name "github-actions[bot]"
    git config user.email "github-actions[bot]@users.noreply.github.com"
    git add data/ state.json
    TODAY=$(date +%Y-%m-%d)
    if git log --oneline -1 | grep -q "digest: $TODAY"; then
      git commit --amend --no-edit
      git push --force-with-lease
    else
      git commit -m "digest: $TODAY"
      git push
    fi
```

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| `pyTelegramBotAPI==4.32.0` | Python 3.9–3.14 | Uses `requests` internally; compatible with `requests==2.32.5` |
| `google-genai==1.67.0` | Python 3.10–3.14 | Uses `httpx` internally for sync client; no conflict with `requests` |
| `trafilatura==2.0.0` | Python 3.8–3.13 | Requires `lxml`, `certifi`, `chardet` — all pulled in automatically |
| `actions/setup-python@v6` | GitHub Actions runner v2.327.1+ | Upgrade from v5 required if using node24 features; v5 still works on older runners |
| Python 3.12 on `ubuntu-latest` | All above packages | `ubuntu-latest` = Ubuntu 24.04 as of 2026; Python 3.12 is pre-installed, `setup-python` caches it |

---

## Sources

- `pyTelegramBotAPI` — https://pypi.org/project/pyTelegramBotAPI/ — version 4.32.0, released Mar 9, 2026. **HIGH confidence.**
- `python-telegram-bot` — https://pypi.org/project/python-telegram-bot/ — version 22.6, released Jan 24, 2026. Async-only since v20. **HIGH confidence.**
- `google-genai` — https://pypi.org/project/google-genai/ — version 1.67.0, released Mar 12, 2026. Active Google-maintained SDK. **HIGH confidence.**
- `google-generativeai` DEPRECATED — https://pypi.org/project/google-generativeai/ — PyPI classifier "7 - Inactive", support ended Nov 30 2025. **HIGH confidence (verified from official PyPI page).**
- `trafilatura` — https://pypi.org/project/trafilatura/ — version 2.0.0, released Dec 3, 2024. Benchmark winner for web content extraction. **HIGH confidence.**
- `requests` — https://pypi.org/project/requests/ — version 2.32.5, released Aug 18, 2025. **HIGH confidence.**
- `httpx` — https://pypi.org/project/httpx/ — version 0.28.1, released Dec 6, 2024 (1.0.dev3 pre-release Sep 2025). Stable but noted as "4 - Beta" classifier. **HIGH confidence.**
- `actions/setup-python` — https://github.com/marketplace/actions/setup-python — v6.2.0, node24, requires runner v2.327.1+. **HIGH confidence (official GitHub action).**

---
*Stack research for: Serverless Telegram digest bot — Python + GitHub Actions + Gemini 2.0 Flash*
*Researched: 2026-03-15*
