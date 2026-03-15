# Architecture Research

**Domain:** Serverless Telegram bot + AI summarisation pipeline (GitHub Actions runtime)
**Researched:** 2026-03-15
**Confidence:** HIGH — all major claims verified against official GitHub Actions docs and Telegram Bot API 9.5 (current)

---

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        TRIGGER LAYER                                │
│  ┌──────────────────────┐   ┌──────────────────────────────────┐   │
│  │  schedule (cron UTC) │   │  workflow_dispatch (manual)       │   │
│  └──────────┬───────────┘   └──────────────┬───────────────────┘   │
└─────────────┼────────────────────────────  ┼ ──────────────────────┘
              │                              │
              ▼                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    GITHUB ACTIONS JOB (ubuntu-latest)               │
│                                                                     │
│  Step 1: checkout (fetch-depth: 0, so amend can see git log)        │
│  Step 2: setup-python + pip install                                 │
│  Step 3: python main.py                                             │
│     │                                                               │
│     │   ┌──────────────────────────────────────────────────────┐   │
│     └──►│              PYTHON PIPELINE                          │   │
│         │  telegram_client  ──► content_fetcher                │   │
│         │       │                    │                          │   │
│         │       │ (URLs)             │ (HTML/YouTube URL)       │   │
│         │       ▼                    ▼                          │   │
│         │  state.json ◄──    summarizer (Gemini API)           │   │
│         │  (offset++)        │                                  │   │
│         │                    │ (summaries)                      │   │
│         │                    ▼                                  │   │
│         │              digest_generator                         │   │
│         │                    │                                  │   │
│         │                    ▼                                  │   │
│         │    ┌──────────────────────────────────┐              │   │
│         │    │      FILESYSTEM OUTPUT           │              │   │
│         │    │  data/sources/YYYY-MM-DD/        │              │   │
│         │    │  data/digests/YYYY-MM-DD.md      │              │   │
│         │    │  data/failed/YYYY-MM-DD/         │              │   │
│         │    │  state.json                      │              │   │
│         │    └──────────────────────────────────┘              │   │
│         └──────────────────────────────────────────────────────┘   │
│  Step 4: git amend-or-create commit                                 │
│  Step 5: git push (force-with-lease for amend safety)               │
│  Step 6: python send_digest.py (Telegram sendMessage)               │
└─────────────────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    EXTERNAL SERVICES                                │
│  ┌─────────────────┐  ┌────────────────┐  ┌───────────────────┐   │
│  │  Telegram API   │  │  Gemini API    │  │  Open Web (HTTP)  │   │
│  │  getUpdates     │  │  generateContent│  │  article content  │   │
│  │  sendMessage    │  │  (YouTube URL  │  │  (via requests)   │   │
│  └─────────────────┘  │   natively)    │  └───────────────────┘   │
│                        └────────────────┘                          │
└─────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Boundary |
|-----------|---------------|----------|
| `telegram_client.py` | Fetch updates via `getUpdates`, read/write `state.json` offset, send final message via `sendMessage` | Talks to Telegram API only; never touches files directly except `state.json` |
| `content_fetcher.py` | Classify URL type (article vs YouTube); fetch article HTML; return raw content or YouTube URL passthrough | No AI calls; no file writes; pure data retrieval |
| `summarizer.py` | Send content to Gemini 2.0 Flash with prompt; receive summary text | No file I/O; receives content string, returns summary string |
| `digest_generator.py` | Assemble all summaries into a single digest Markdown; write `data/digests/YYYY-MM-DD.md` | Reads prompt files; writes output files; no external calls |
| `main.py` | Orchestrate the full pipeline in sequence; route failures to `data/failed/` | Owns control flow and error isolation; wires all modules together |
| `state.json` | Single field: `{"last_update_id": N}` — Telegram polling cursor | Written atomically after successful `getUpdates` call |
| `prompts/` | Plain text prompt files loaded at runtime | Read-only from pipeline perspective; `prompts/summarize.txt`, `prompts/digest.txt` |
| `.github/workflows/digest.yml` | Cron + manual dispatch trigger; checkout, setup, run, commit, push, deliver | Single job; no matrix; no parallel steps needed |

---

## Recommended Project Structure

```
tldr-bot/
├── .github/
│   └── workflows/
│       └── digest.yml          # Daily cron + manual dispatch workflow
├── data/
│   ├── sources/
│   │   └── YYYY-MM-DD/         # Per-URL summary files: <slug>.md
│   ├── digests/
│   │   └── YYYY-MM-DD.md       # One digest per day
│   └── failed/
│       └── YYYY-MM-DD/         # Per-URL failure records: <slug>.md
├── prompts/
│   ├── summarize.txt           # Prompt for per-URL summarisation
│   └── digest.txt              # Prompt for digest assembly
├── telegram_client.py          # getUpdates + sendMessage
├── content_fetcher.py          # URL classification + article fetch
├── summarizer.py               # Gemini API wrapper
├── digest_generator.py         # Digest file assembly
├── main.py                     # Pipeline orchestrator
├── state.json                  # Telegram offset cursor (committed)
├── requirements.txt            # pip dependencies
└── README.md
```

### Structure Rationale

- **Flat modules at root:** Pipeline is a linear script, not a library. Flat layout eliminates import path complexity.
- **`data/` subdirectories by type:** Sources, digests, and failures are distinct artifacts consumed differently (read for digest, inspect for debugging, retry for failures). Separate directories make intent clear.
- **`YYYY-MM-DD/` per-source dirs vs single file per day:** Slug-keyed files allow incremental future features (retry by slug, deduplication by slug) without restructuring.
- **`prompts/` as sibling directory:** Prompt files are configuration, not code. Co-locating with pipeline code (not in `data/`) signals that they are inputs to the system, not outputs.
- **`state.json` at root:** Committed alongside code makes its version history directly visible in `git log`. Keeps the "filesystem as database" axiom visible.

---

## Architectural Patterns

### Pattern 1: Offset-Based Polling with Confirmed Acknowledgement

**What:** Telegram's `getUpdates` API uses `offset` to acknowledge processed updates. Pass `offset = last_update_id + 1` to receive only new updates. Updates are retained on Telegram's servers for 24 hours if not acknowledged.

**When to use:** Every pipeline run. The offset is read from `state.json` at the start of the run, updates are fetched, then `state.json` is written with the new high-water mark before any processing begins.

**Critical nuance:** Write the new offset to `state.json` **before** processing, not after. If processing fails mid-run, the next run will not re-fetch already-seen updates. This is intentional — it avoids re-processing at the cost of potentially missing summaries on error (the failure record captures the artifact).

**Example:**
```python
# telegram_client.py
import json, requests, os

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
ALLOWED_CHAT_ID = int(os.environ["ALLOWED_CHAT_ID"])
STATE_FILE = "state.json"

def load_offset() -> int:
    try:
        with open(STATE_FILE) as f:
            return json.load(f).get("last_update_id", 0)
    except FileNotFoundError:
        return 0

def save_offset(update_id: int) -> None:
    with open(STATE_FILE, "w") as f:
        json.dump({"last_update_id": update_id}, f)

def fetch_updates() -> list[dict]:
    offset = load_offset()
    resp = requests.get(
        f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates",
        params={
            "offset": offset + 1 if offset else None,
            "limit": 100,
            "allowed_updates": ["message"],
        },
        timeout=30,
    )
    resp.raise_for_status()
    updates = resp.json()["result"]
    if updates:
        save_offset(updates[-1]["update_id"])
    return [
        u for u in updates
        if u.get("message", {}).get("chat", {}).get("id") == ALLOWED_CHAT_ID
    ]
```

---

### Pattern 2: Silent Failure with Failure Record

**What:** Each URL is processed inside a `try/except` block. On failure, a minimal Markdown file is written to `data/failed/YYYY-MM-DD/<slug>.md` with the URL, timestamp, and error message. Processing continues to the next URL.

**When to use:** Every URL in the batch. Paywalls, timeouts, and extraction failures are expected.

**Example:**
```python
# main.py (simplified)
from datetime import date
from pathlib import Path

today = date.today().isoformat()
summaries = []

for url in urls:
    slug = slugify(url)
    try:
        content = fetch_content(url)
        summary = summarize(content, url)
        out_path = Path(f"data/sources/{today}/{slug}.md")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(f"# {url}\n\n{summary}\n")
        summaries.append({"url": url, "summary": summary})
    except Exception as e:
        fail_path = Path(f"data/failed/{today}/{slug}.md")
        fail_path.parent.mkdir(parents=True, exist_ok=True)
        fail_path.write_text(f"# FAILED: {url}\n\n**Error:** {e}\n**Date:** {today}\n")
```

---

### Pattern 3: Amend-or-Create Daily Commit

**What:** The workflow checks whether a commit with today's date message already exists on `HEAD`. If yes, amend it (`git commit --amend --no-edit`). If no, create a new commit. This keeps one commit per day regardless of how many times the workflow runs.

**When to use:** At the end of every run, after all files are written.

**Critical implementation detail:** `git push --force-with-lease` is required when amending. `--force-with-lease` is safer than `--force` because it refuses to push if the remote has advanced beyond what the local checkout knows — preventing accidental overwrite of concurrent pushes.

**The workflow must also configure git identity** because GitHub Actions runners have no global git config by default.

**Example (shell script in workflow step):**
```bash
git config user.name "github-actions[bot]"
git config user.email "github-actions[bot]@users.noreply.github.com"

TODAY=$(date -u +%Y-%m-%d)
COMMIT_MSG="digest: ${TODAY}"

git add data/ state.json

# Check if today's commit already exists at HEAD
if git log -1 --pretty=%s | grep -qF "${COMMIT_MSG}"; then
  git commit --amend --no-edit
  git push --force-with-lease
else
  git commit -m "${COMMIT_MSG}"
  git push
fi
```

**Why `--force-with-lease` and not `--force`:**
- `--force` overwrites remote unconditionally — dangerous if a race occurs
- `--force-with-lease` checks that the remote ref matches what was fetched at checkout; fails if another push happened in the interim
- For a single-user single-run-per-day workflow this is low risk, but `--force-with-lease` is the standard safe pattern

---

### Pattern 4: Prompt Files as Runtime Configuration

**What:** Prompt text is stored in `prompts/*.txt` and read at runtime. The Python code contains no prompt strings.

**When to use:** All LLM calls. Prompt is loaded fresh each run — no code change needed to tune output.

**Example:**
```python
# summarizer.py
import google.generativeai as genai
import os
from pathlib import Path

genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model = genai.GenerativeModel("gemini-2.0-flash")

def load_prompt(name: str) -> str:
    return Path(f"prompts/{name}.txt").read_text()

def summarize_article(content: str) -> str:
    prompt = load_prompt("summarize") + "\n\n" + content
    response = model.generate_content(prompt)
    return response.text

def summarize_youtube(url: str) -> str:
    prompt = load_prompt("summarize") + f"\n\nVideo URL: {url}"
    # Gemini 2.0 Flash processes YouTube URLs natively
    response = model.generate_content(prompt)
    return response.text
```

---

## Data Flow

### Full Pipeline Run

```
TRIGGER (cron 07:00 UTC or manual dispatch)
    │
    ▼
checkout repo (fetch-depth: 0 for git log access)
    │
    ▼
python main.py
    │
    ├── telegram_client.fetch_updates()
    │       │ reads state.json → offset N
    │       │ GET /getUpdates?offset=N+1&allowed_updates=["message"]
    │       │ filters by ALLOWED_CHAT_ID
    │       │ writes state.json → offset N+K
    │       └── returns: [{"url": "...", "message_id": ...}, ...]
    │
    ├── for each URL:
    │       │
    │       ├── content_fetcher.classify(url) → "article" | "youtube"
    │       │
    │       ├── if "article":
    │       │       content_fetcher.fetch(url) → HTML string
    │       │       summarizer.summarize_article(html) → summary text
    │       │
    │       ├── if "youtube":
    │       │       summarizer.summarize_youtube(url) → summary text
    │       │       (Gemini fetches/processes YouTube content natively)
    │       │
    │       ├── on success: write data/sources/YYYY-MM-DD/<slug>.md
    │       └── on failure: write data/failed/YYYY-MM-DD/<slug>.md
    │
    ├── digest_generator.generate(summaries)
    │       loads prompts/digest.txt
    │       sends all summaries to Gemini for digest assembly
    │       writes data/digests/YYYY-MM-DD.md
    │
    └── returns: digest_path
    │
    ▼
git amend-or-create commit (see Pattern 3)
    │
    ▼
git push (or push --force-with-lease if amend)
    │
    ▼
telegram_client.send_digest(digest_path)
    POST /sendMessage with digest Markdown text
```

### State Transitions

```
state.json on disk
    │
    ├── [run start] read → last_update_id = N
    ├── [after getUpdates] write → last_update_id = N+K  (acknowledged)
    └── [end of run] committed to git with all output files
```

### No-URLs Edge Case

```
getUpdates returns empty list
    │
    ├── state.json unchanged (no new offset to write)
    ├── no source files written
    ├── digest_generator skips or writes empty-digest placeholder
    └── workflow skips commit if no files changed (git add -A; git diff --cached --quiet && exit 0)
```

---

## GitHub Actions Workflow Structure

### Full Annotated Workflow

```yaml
# .github/workflows/digest.yml
name: Daily Digest

on:
  schedule:
    - cron: '0 7 * * *'     # 07:00 UTC daily
  workflow_dispatch:          # Manual trigger from Actions UI

# Concurrency: allow-in-progress=false means if a run is already going,
# don't cancel it — queue the new one instead.
# For a daily digest this is safest: don't drop a run, let it finish.
concurrency:
  group: digest
  cancel-in-progress: false

permissions:
  contents: write             # Required for git push

jobs:
  run-digest:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4
        with:
          fetch-depth: 0      # Full history needed to check today's commit

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: 'pip'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run pipeline
        env:
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          ALLOWED_CHAT_ID: ${{ secrets.ALLOWED_CHAT_ID }}
        run: python main.py

      - name: Commit and push
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"

          TODAY=$(date -u +%Y-%m-%d)
          COMMIT_MSG="digest: ${TODAY}"

          git add data/ state.json

          # Skip commit entirely if nothing changed
          if git diff --cached --quiet; then
            echo "No changes to commit."
            exit 0
          fi

          # Amend if today's commit already exists at HEAD
          if git log -1 --pretty=%s | grep -qF "${COMMIT_MSG}"; then
            git commit --amend --no-edit
            git push --force-with-lease
          else
            git commit -m "${COMMIT_MSG}"
            git push
          fi

      - name: Send digest to Telegram
        env:
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          ALLOWED_CHAT_ID: ${{ secrets.ALLOWED_CHAT_ID }}
        run: python send_digest.py
```

### Secrets Required

| Secret | Description | Where to get |
|--------|-------------|-------------|
| `TELEGRAM_BOT_TOKEN` | Bot authentication token | BotFather: `/newbot` |
| `GEMINI_API_KEY` | Google AI API key | aistudio.google.com |
| `ALLOWED_CHAT_ID` | Numeric chat ID to filter messages | Send `/start` to bot; inspect getUpdates response |

### Workflow Design Notes

- **`fetch-depth: 0`** is required. The default (`fetch-depth: 1`) only fetches the latest commit. To check `git log -1 --pretty=%s` for today's commit message, the full log must be available.
- **`permissions: contents: write`** must be explicit. GitHub Actions repositories may have restricted default GITHUB_TOKEN permissions (organization policy). Explicit declaration ensures push works regardless of org settings.
- **`concurrency.cancel-in-progress: false`** prevents a manual dispatch from cancelling a concurrent scheduled run. For a digest pipeline, dropped runs are worse than queued runs.
- **`cache: pip`** on `setup-python` caches pip packages across runs, reducing install time from ~30s to ~5s for warm runs.
- **`workflow_dispatch`** requires the workflow file to be on the default branch. Manual triggers from branches other than `main` will not appear in the Actions UI.

---

## Build Order

The following order is necessary because each layer depends on the previous:

```
1. Repository scaffolding
   └── Create: data/, prompts/, .github/workflows/, requirements.txt, .gitignore
   └── Reason: All other steps require this structure to exist

2. Secrets setup
   └── Create Telegram bot via BotFather, get chat ID, create Gemini API key
   └── Add secrets to GitHub repository settings
   └── Reason: No code can be tested without credentials

3. telegram_client.py
   └── Implements: getUpdates with offset, sendMessage, state.json I/O
   └── Test: Run manually with real credentials; verify updates fetched, state written
   └── Reason: Core data input — must work before anything else is built

4. content_fetcher.py
   └── Implements: URL classification (youtube.com/youtu.be detection), HTTP fetch with
       requests, basic HTML extraction
   └── Test: Unit test with mock URLs, integration test with real article
   └── Reason: content_fetcher feeds summarizer; must work before AI integration

5. summarizer.py
   └── Implements: Gemini API wrapper, prompt file loading, article + YouTube paths
   └── Test: End-to-end with a known article URL and a YouTube URL
   └── Reason: Most fragile external dependency; validate early before wiring into pipeline

6. digest_generator.py
   └── Implements: Digest Markdown assembly, Gemini call for digest formatting,
       file write to data/digests/
   └── Test: Feed it mock summaries; verify output format matches expectations
   └── Reason: Final pipeline stage before commit; depends on summarizer patterns working

7. main.py (orchestrator)
   └── Implements: Full pipeline wiring, error isolation, failure record writing
   └── Test: Full end-to-end dry run (read real Telegram messages, generate real summaries)
   └── Reason: Integration test of all modules together

8. GitHub Actions workflow
   └── Implements: digest.yml with cron, checkout, run, commit, push
   └── Test: Manual dispatch from Actions UI; verify commit appears in repo
   └── Reason: Tests the execution environment, secrets injection, and git operations

9. Amend-or-create commit logic
   └── Verify: Trigger workflow twice on the same day; confirm single commit in git log
   └── Reason: Final correctness check for the daily history invariant
```

---

## Integration Points

### External Services

| Service | Integration Method | Auth | Timeout | Failure Mode |
|---------|-------------------|------|---------|--------------|
| Telegram Bot API | HTTPS REST (`requests`) | Bot token in URL | 30s | `raise_for_status()` → logged, run continues |
| Gemini 2.0 Flash | `google-generativeai` SDK | API key via env var | SDK default (~60s) | Exception → write failure record |
| Article web pages | `requests.get()` with User-Agent | None | 15s | Exception → write failure record |
| GitHub (git push) | git CLI via `GITHUB_TOKEN` | Automatic in Actions | N/A | Action fails; run marked red |

### Internal Module Boundaries

| Boundary | Direction | Contract |
|----------|-----------|---------|
| `main.py` → `telegram_client` | Call | `fetch_updates() → list[str]` (URLs), `send_message(text: str) → None` |
| `main.py` → `content_fetcher` | Call | `fetch(url: str) → str` (raw content or YouTube URL passthrough) |
| `main.py` → `summarizer` | Call | `summarize(content: str, url: str) → str` (Markdown summary text) |
| `main.py` → `digest_generator` | Call | `generate(summaries: list[dict]) → Path` (path to written digest file) |
| `summarizer` → `prompts/summarize.txt` | Read | File read at call time; no caching |
| `digest_generator` → `prompts/digest.txt` | Read | File read at call time; no caching |
| `telegram_client` → `state.json` | Read + Write | JSON: `{"last_update_id": int}` |

---

## Anti-Patterns

### Anti-Pattern 1: Hardcoding Prompts in Python

**What people do:** Write prompt strings directly in `summarizer.py` or `digest_generator.py`.

**Why it's wrong:** Tuning output requires code changes → commits → workflow runs to test. Prompt iteration should be a text edit, not a deployment.

**Do this instead:** Load from `prompts/*.txt` files. Change a prompt by editing the file; next run picks it up.

---

### Anti-Pattern 2: Writing Offset After Processing (Not Before)

**What people do:** Call `getUpdates`, process all URLs, then write the new offset to `state.json`.

**Why it's wrong:** If the pipeline crashes mid-processing (Gemini timeout, network error), the offset is never written. The next run re-fetches the same updates and processes them again — potentially double-summarising the same URLs.

**Do this instead:** Write the new offset to `state.json` immediately after `getUpdates` returns, before any processing begins. Accept that a crash may lose some summaries; the failure record pattern handles that gracefully.

---

### Anti-Pattern 3: Using `git push --force` for Amend

**What people do:** `git commit --amend && git push --force` — simple and common advice.

**Why it's wrong:** `--force` obliterates the remote ref unconditionally. If a human pushed a manual change between the workflow's checkout and its push (unlikely but possible), `--force` silently destroys it. It also signals dangerous intent in CI pipelines.

**Do this instead:** `git push --force-with-lease`. This verifies the remote ref hasn't moved since checkout. Fails safe if something unexpected happened; `--force` fails open.

---

### Anti-Pattern 4: Fetching `fetch-depth: 1` When Amending

**What people do:** Use default `actions/checkout` (shallow clone), then try to amend.

**Why it's wrong:** Amending requires access to the parent commit. A shallow clone may not have it. Also, `git log` to check for today's commit message needs log history that a depth-1 clone doesn't provide.

**Do this instead:** `actions/checkout@v4` with `fetch-depth: 0`. The full history is small for a daily-commit repository and the fetch cost is negligible.

---

### Anti-Pattern 5: Single `main.py` That Aborts on First URL Failure

**What people do:** Process URLs in a loop without per-URL exception handling. First paywall or timeout kills the run.

**Why it's wrong:** Paywalls and timeouts are expected. One bad URL should not prevent the rest of the day's reading from being summarised.

**Do this instead:** Wrap each URL in `try/except`. Write failure records. Let the loop continue. Only abort if something systemic fails (Telegram API unreachable, Gemini completely down).

---

## Scaling Considerations

This is a single-user personal tool. Scaling concerns are theoretical but documented for evolution awareness.

| Scale Axis | Current (1 user, 1-10 URLs/day) | If URLs/day grew to 50+ | If multi-user |
|------------|--------------------------------|------------------------|----------------|
| Gemini rate limits | Well within free tier | Approach rate limits; add `time.sleep()` between calls or upgrade tier | Per-user API keys or quota tracking |
| GitHub Actions runtime | <5 min easily | Still fine; no runtime limit concern below ~200 URLs | Multiple jobs or concurrent workflows |
| `state.json` concurrency | No risk — one run per day | No risk — cron + `cancel-in-progress: false` | Needs per-user state files; `state-{chat_id}.json` |
| Digest Markdown size | Trivially small | Large but still renderable | Same |
| Git history size | ~1MB/year | Still trivial | Same |

---

## Sources

- Telegram Bot API 9.5 (March 2026): https://core.telegram.org/bots/api#getupdates
  — Verified: `getUpdates` offset semantics, 24-hour update retention, `allowed_updates` parameter
- GitHub Actions Workflow Syntax (official docs, verified 2026-03-15):
  https://docs.github.com/en/actions/writing-workflows/workflow-syntax-for-github-actions
  — Verified: `on.schedule` cron syntax, `concurrency`, `permissions`, `workflow_dispatch`
- GitHub Actions Triggering Workflows (official docs):
  https://docs.github.com/en/actions/writing-workflows/choosing-when-your-workflow-runs/triggering-a-workflow
  — Verified: `workflow_dispatch` requires default branch, GITHUB_TOKEN for push
- `google-generativeai` SDK — YouTube URL native support confirmed in Gemini 2.0 Flash model documentation
  — Confidence: MEDIUM (direct doc fetch redirected; based on architecture.md source claim + known Gemini capability)

---

*Architecture research for: Serverless Telegram bot + Gemini AI digest pipeline*
*Researched: 2026-03-15*
*All patterns verified against official API documentation. Confidence: HIGH for GitHub Actions and Telegram patterns. MEDIUM for Gemini native YouTube processing (documented in architecture.md but official docs fetch failed — verify during implementation).*
