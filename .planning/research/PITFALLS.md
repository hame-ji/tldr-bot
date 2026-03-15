# Pitfalls Research

> Historical note (2026-03-15): This research includes Gemini-era pitfalls.
> Current runtime scope is OpenRouter article-only summarization.

**Domain:** Serverless Telegram bot + GitHub Actions + Gemini AI pipeline
**Researched:** 2026-03-15
**Confidence:** HIGH (based on official Telegram Bot API docs, GitHub Actions docs, google-genai SDK source, and domain-specific patterns)

---

## Critical Pitfalls

### Pitfall 1: Telegram Offset Off-By-One — Infinite Duplicate Processing

**What goes wrong:**
The `getUpdates` offset must be set to `last_update_id + 1`, not `last_update_id`. If the offset is written as the raw `update_id` of the last processed update, Telegram re-delivers that update on every subsequent call. For a daily-run pipeline reading state.json at startup, this means the same URL is re-summarized and re-committed every single day until state.json is manually corrected.

**Why it happens:**
Telegram's API says: "Must be greater by one than the highest among the identifiers of previously received updates." This is easy to misread. Developers often store the `update_id` directly ("the last thing I saw") and pass it back unchanged, rather than incrementing by 1.

**How to avoid:**
Always persist and pass `max(update_id) + 1`. In Python:
```python
# Correct
next_offset = max(u["update_id"] for u in updates) + 1
state["offset"] = next_offset

# Wrong — this re-delivers the last update forever
state["offset"] = max(u["update_id"] for u in updates)
```

**Warning signs:**
- Same URL appearing in two consecutive day's digests
- `data/sources/` accumulating duplicate entries with the same slug on different dates
- Git log showing the same URL committed on multiple days

**Phase to address:** Telegram polling implementation (first phase to write the polling client)

---

### Pitfall 2: Git Amend Push Fails When Remote Has Moved On

**What goes wrong:**
The "one commit per day, amend if today's commit exists" strategy uses `git commit --amend` followed by `git push --force-with-lease`. If the remote has diverged since the last fetch (e.g., a manual dispatch ran and committed while an earlier run was still in progress — even with `cancel-in-progress: false`, both could start before either commits), the force-with-lease push will fail with a non-zero exit code and the run exits without committing today's data.

**Why it happens:**
`--force-with-lease` checks that the remote ref matches what you fetched. If two runs overlap at the "check if today's commit exists" step before either has pushed, the second one's amend will conflict with the first one's push.

**How to avoid:**
The guard is `cancel-in-progress: false` + the workflow's concurrency group. Make the concurrency group key date-based so only one run per day is ever active:
```yaml
concurrency:
  group: digest-${{ github.run_id }}  # Wrong — allows parallel runs
  
concurrency:
  group: daily-digest  # Correct — serializes all runs globally
  cancel-in-progress: false
```
Also: always `git pull --rebase` before the amend-or-new-commit logic, so the local branch is current before checking today's commit.

**Warning signs:**
- GitHub Actions logs showing "rejected (stale info)" on push step
- `state.json` in repo diverging from what was processed (offset not updated)
- Two digest files for the same day appearing in git log

**Phase to address:** GitHub Actions workflow implementation; git commit strategy

---

### Pitfall 3: GITHUB_TOKEN Lacks `contents: write` — Push Silently Fails

**What goes wrong:**
By default, repositories with "Read and write permissions" disabled in Actions settings, or workflows using the default `permissions:` block, have `GITHUB_TOKEN` with `contents: read`. Attempting `git push` using this token gets a 403. The step fails but if error handling is loose, the pipeline completes successfully (digest generated, Telegram message sent) with no data committed — state.json offset is also not persisted, meaning the same updates are re-fetched tomorrow.

**Why it happens:**
GitHub changed the default Actions permission to "Read repository contents and packages permissions" in late 2022 for new repositories. Developers assume git push will work because they've seen it work in other projects without explicit permission grants.

**How to avoid:**
Explicitly declare `contents: write` in the workflow job permissions:
```yaml
jobs:
  digest:
    runs-on: ubuntu-latest
    permissions:
      contents: write   # Required for git push
```
And configure git identity before committing:
```bash
git config user.email "actions@github.com"
git config user.name "GitHub Actions"
git remote set-url origin https://x-access-token:${{ secrets.GITHUB_TOKEN }}@github.com/${{ github.repository }}
```

**Warning signs:**
- Actions run succeeds but no new commits appear in the repo
- `git push` step shows exit code 128 or "remote: Permission to ... denied"
- `state.json` unchanged between runs despite URLs being processed

**Phase to address:** GitHub Actions workflow setup (before any commit logic is written)

---

### Pitfall 4: Webhook Active → getUpdates Returns Nothing

**What goes wrong:**
If a Telegram webhook was ever set on the bot token (e.g., from a previous experiment or a BotFather test), `getUpdates` returns empty arrays indefinitely. The pipeline runs, processes zero URLs, generates an empty digest, and commits. No error is raised. This is one of the most confusing silent failures in Telegram bot development.

**Why it happens:**
Telegram's API enforces mutual exclusivity: "This method will not work if an outgoing webhook is set up." New token = clean state, but re-used tokens from experimentation often have a lingering webhook.

**How to avoid:**
As part of initial setup, explicitly call `deleteWebhook`:
```bash
curl "https://api.telegram.org/bot$TOKEN/deleteWebhook?drop_pending_updates=false"
```
Then verify with `getWebhookInfo` — the `url` field should be empty. Add a startup assertion in the pipeline:
```python
webhook_info = telegram.get_webhook_info()
if webhook_info.get("url"):
    raise RuntimeError(f"Webhook is set: {webhook_info['url']} — deleteWebhook first")
```

**Warning signs:**
- `getUpdates` consistently returns `{"ok": true, "result": []}`
- No URLs processed across multiple runs even though messages were sent
- Empty digests every day

**Phase to address:** Initial bot setup; also add defensive check in polling client

---

### Pitfall 5: Telegram Message 4096-Char Limit Truncates Digest

**What goes wrong:**
Telegram's `sendMessage` silently rejects messages over 4096 characters with a `400 Bad Request: message is too long` error. A digest summarizing 5+ articles with verbose prompts easily exceeds this. The pipeline errors at the delivery step, which happens after all summaries and commits are done — so the data is safe but the delivery fails.

**Why it happens:**
Developers test with 1-2 short articles and never hit the limit. The limit is per-message, not per-send-call. Long digests accumulate invisibly until they exceed the cap.

**How to avoid:**
Split the digest into chunks of ≤4096 chars before sending, splitting on paragraph boundaries (not mid-sentence):
```python
MAX_TG_LEN = 4096

def send_digest(bot_token, chat_id, text):
    if len(text) <= MAX_TG_LEN:
        _send(bot_token, chat_id, text)
        return
    
    chunks = []
    current = ""
    for paragraph in text.split("\n\n"):
        if len(current) + len(paragraph) + 2 > MAX_TG_LEN:
            chunks.append(current)
            current = paragraph
        else:
            current += "\n\n" + paragraph if current else paragraph
    if current:
        chunks.append(current)
    
    for i, chunk in enumerate(chunks):
        _send(bot_token, chat_id, f"*({i+1}/{len(chunks)})*\n\n{chunk}")
```

**Warning signs:**
- `sendMessage` returns 400 error in logs
- Digests with many articles fail but short ones work
- Telegram showing no message on days with heavy reading

**Phase to address:** Telegram delivery implementation

---

### Pitfall 6: Content Fetching Hangs — No Timeout → Workflow Timeout

**What goes wrong:**
`requests.get(url)` without a `timeout=` parameter can hang indefinitely on a slow or malicious server. If even one URL in the batch hangs, the GitHub Actions job runs until it hits the 6-hour workflow timeout, consuming the daily Actions budget and blocking the next scheduled run. With `cancel-in-progress: false`, the next cron trigger queues but doesn't run until the hung job finishes.

**Why it happens:**
Python's `requests` library has no default timeout. Developers omit it during development (fast local network) and it never surfaces until a slow URL appears in production.

**How to avoid:**
Always set both connect and read timeouts:
```python
response = requests.get(url, timeout=(10, 30))  # (connect_timeout, read_timeout)
```
Wrap in the silent-failure model:
```python
try:
    response = requests.get(url, timeout=(10, 30))
    response.raise_for_status()
except (requests.Timeout, requests.RequestException) as e:
    write_failure_record(url, str(e))
    continue
```

**Warning signs:**
- GitHub Actions job running for hours
- Single URL in the batch from an obscure domain
- `data/failed/` not being written (timeout kills before failure handler)

**Phase to address:** URL fetching / content extraction implementation

---

### Pitfall 7: Gemini API Rate Limit on Free Tier — Hard 429s Kill the Batch

**What goes wrong:**
Gemini 2.0 Flash free tier has rate limits (requests per minute). If 5+ URLs arrive in one day's batch and the pipeline calls `generate_content` in rapid succession without any delay, the API returns `429 Resource Exhausted`. If this exception isn't caught and wrapped in the silent-failure model, the pipeline aborts mid-batch, leaving a partial digest with no indication of which URLs were dropped.

**Why it happens:**
Rate limits are per-minute, not per-day. At 1-10 URLs/day the total volume is fine, but if they all arrive in one run with no sleep between calls, the burst triggers the per-minute cap.

**How to avoid:**
Add a small sleep between Gemini calls (1-2 seconds is enough for free tier RPM limits):
```python
import time

for url in urls:
    try:
        summary = gemini_summarize(url)
    except Exception as e:
        if "429" in str(e) or "Resource Exhausted" in str(e):
            time.sleep(60)  # Back off a full minute and retry once
            try:
                summary = gemini_summarize(url)
            except Exception as retry_e:
                write_failure_record(url, str(retry_e))
                continue
        else:
            write_failure_record(url, str(e))
            continue
    time.sleep(1)  # Polite inter-request spacing
```

**Warning signs:**
- `data/failed/` entries with "429" or "Resource Exhausted" in error field
- Partial digests with fewer summaries than URLs sent
- Consistent failures on days with 5+ URLs

**Phase to address:** Gemini integration / summarization implementation

---

### Pitfall 8: google-generativeai vs google-genai Import Confusion

**What goes wrong:**
There are two Google Gemini Python packages: `google-generativeai` (deprecated, archived Dec 2025) and `google-genai` (current). Code examples online, Stack Overflow answers, and AI coding assistants frequently generate code using the old `import google.generativeai as genai` pattern. If mixed with the new SDK, the imports conflict or use incompatible APIs, producing cryptic errors.

**Why it happens:**
The old package was the primary SDK for 2+ years. Most tutorials, blog posts, and training data for AI assistants use it. The new `google-genai` package was not the default until late 2024.

**How to avoid:**
Use only `google-genai` (package) with `from google import genai` imports. Never install `google-generativeai`. Add to `requirements.txt`:
```
google-genai>=1.0.0
```
Add a CI check or comment in requirements.txt:
```
# NOTE: This is google-genai (new SDK), NOT google-generativeai (deprecated)
# See: https://github.com/googleapis/python-genai
```

**Warning signs:**
- `import google.generativeai` anywhere in the codebase
- Both packages installed in the same environment
- `AttributeError: module 'google.generativeai' has no attribute 'Client'` errors

**Phase to address:** Project setup / dependency declaration

---

### Pitfall 9: state.json Offset Not Committed on Partial Failure

**What goes wrong:**
The pipeline processes URLs, writes summaries, but then hits an error in digest generation or Telegram delivery. If the git commit step is only reached after all steps succeed, `state.json` (with the updated offset) is never committed. On the next run, the pipeline re-fetches the same updates, re-processes the same URLs, and creates duplicate `data/sources/` entries.

**Why it happens:**
Developers treat the commit as a "success checkpoint" at the end of a happy path. The offset update is bundled with the digest commit. If the digest step fails, both the digest and the offset are lost.

**How to avoid:**
Commit `state.json` separately and early — immediately after Telegram polling completes, before any fetching or summarization:
```python
# Step 1: Poll Telegram, write new offset to state.json
updates = poll_telegram()
write_state({"offset": new_offset})
git_commit("chore: update telegram offset")

# Step 2: Process URLs (can fail silently)
# Step 3: Generate digest (can fail silently)
# Step 4: Amend or create today's data commit
# Step 5: Send to Telegram
```
This guarantees that even if the pipeline dies mid-run, updates are not re-processed.

**Warning signs:**
- Same URL appearing in `data/sources/` on consecutive days
- `state.json` in the repo showing the same offset across multiple date ranges
- `data/failed/` entries with the same URL on multiple dates

**Phase to address:** Pipeline orchestration; git commit strategy

---

### Pitfall 10: JS-Rendered Pages Return Empty Content

**What goes wrong:**
A significant portion of modern web content is rendered client-side by JavaScript (SPAs, React apps, Next.js static shells). A standard `requests.get()` fetch returns the empty HTML shell with `<div id="root"></div>` — no article content. The pipeline passes this empty string to Gemini, which summarizes "this appears to be an empty page" or similar non-content, or Gemini returns a safety block for minimal input.

**Why it happens:**
`requests` performs an HTTP request only — it doesn't execute JavaScript. Most developer testing uses news sites that serve HTML directly, so JS-rendered content is not caught until production use.

**How to avoid:**
Implement a content extraction fallback chain:
1. `requests` + BeautifulSoup for static HTML (primary, fast)
2. Check response content length — if body text < 200 chars after extraction, write to `data/failed/` with reason "JS-rendered page, insufficient content"
3. Do NOT add Playwright/Puppeteer to v1 — this adds infrastructure complexity incompatible with the serverless philosophy

For articles behind JS rendering, the silent-failure model (write to `data/failed/`) is the right v1 response. The failure record captures the URL for manual review.

**Warning signs:**
- Gemini summaries saying "the page appears empty" or summarizing only navigation text
- Very short `data/sources/` files (< 100 chars)
- Consistent failures for specific domains (Medium, Substack variants, custom apps)

**Phase to address:** URL fetching / content extraction implementation

---

### Pitfall 11: GitHub Actions Cron Skipping on Inactive Repos

**What goes wrong:**
GitHub automatically disables scheduled workflows (`schedule:` triggers) on repositories with no activity for 60 days. The bot silently stops running. Since the digest delivery also stops, there's no signal to the user that anything is wrong — the failure is invisible.

**Why it happens:**
GitHub's policy is designed to conserve resources on abandoned repos. Personal tools that work "in the background" are exactly the use case that triggers this — the user is consuming the output (Telegram messages) without making commits or other repo activity.

**How to avoid:**
The commit-per-day strategy is itself the best defense — daily commits are repo activity that prevents dormancy. However, if the pipeline fails to commit for any reason (including this pitfall), add a note in the README to periodically check the Actions tab.

Alternative: Re-enable from the Actions UI when it gets disabled (GitHub sends an email notification). The workflow can also include a `workflow_dispatch:` trigger so it can always be manually triggered to "wake up" the schedule.

**Warning signs:**
- Telegram digest stops arriving
- Actions tab shows "This scheduled workflow is disabled"
- GitHub sends "Your scheduled workflow has been disabled" email

**Phase to address:** GitHub Actions workflow setup; operational documentation

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Hardcoding Gemini model name (`gemini-2.0-flash`) in code | Fast to write | Model names change; update requires code edit not config change | Never — put in env var or config |
| No content-length check before Gemini call | Simpler code | Empty/JS-rendered pages consume API quota and produce useless summaries | Never — 5-line guard is trivial |
| Using `except Exception: pass` on all errors | No crashes | Silent data loss; impossible to debug; failures invisible in logs | Never — always write failure record |
| No `timeout=` on `requests.get()` | Less code | Single slow URL hangs the workflow for hours | Never — always set timeout |
| Committing state.json only at end of run | Single commit | If pipeline fails mid-run, offset is not persisted; same URLs re-processed | Never — commit offset before processing |
| Comparing `ALLOWED_CHAT_ID` as string to int | Works if both str | Type mismatch if Telegram returns int; silently filters valid messages | Never — always `int()` cast both sides |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Telegram `getUpdates` | Pass `offset=last_update_id` | Pass `offset=last_update_id + 1` |
| Telegram `getUpdates` | Forget `allowed_updates=["message"]` filter | Filter to `["message"]` only — avoids processing edited messages, reactions, etc. |
| Telegram `sendMessage` | Send full digest as single message | Chunk at 4096 chars; split on paragraph boundaries |
| Telegram `sendMessage` | Don't specify `parse_mode` | Use `parse_mode="Markdown"` or `"HTML"` explicitly; default has no formatting |
| GitHub Actions push | Use `GITHUB_TOKEN` without `contents: write` permission | Declare `permissions: contents: write` in job |
| GitHub Actions git | No `git config user.email/name` before commit | Set identity; Actions runners have no global git config |
| GitHub Actions git | Amend without pull first | Always `git pull --rebase` before amend check |
| Gemini API | Use `google-generativeai` package | Use `google-genai` package (`from google import genai`) |
| Gemini API | No handling for `HARM_CATEGORY` blocks | Check `response.candidates[0].finish_reason` for `SAFETY`; write to failed/ |
| Gemini API | Assume `response.text` always exists | Guard: `response.text` raises if generation was blocked; use `try/except` or check `finish_reason` first |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| No inter-request sleep on Gemini API | 429 errors mid-batch | `time.sleep(1)` between calls | 5+ URLs in one batch |
| Fetching full page HTML before deciding if extractable | Slow runs on paywalled sites | Check HTTP status code first; 403/401 = write to failed/ immediately | Any day with a paywall URL |
| Requests without timeout | Workflow hangs for hours | `timeout=(10, 30)` on all requests | First time a slow server appears |
| Loading entire content into memory for large articles | Memory error on long pages | Truncate fetched content at ~100KB before passing to Gemini | Long PDFs, very long articles |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Printing `TELEGRAM_BOT_TOKEN` in logs | Token exposure in public repo Actions logs | Never log secrets; use `::add-mask::$TOKEN` in Actions if needed |
| Committing `.env` file with secrets | Token/API key in git history forever | `.env` in `.gitignore`; use GitHub Secrets only |
| Not filtering by `ALLOWED_CHAT_ID` | Any Telegram user who discovers the bot can queue URLs | Always check `message.chat.id == ALLOWED_CHAT_ID` before processing |
| Storing `GEMINI_API_KEY` in `state.json` | Key in git history | Secrets only via GitHub Actions secrets; never in committed files |
| Fetching arbitrary URLs from Telegram messages | SSRF risk (fetching internal URLs) | Low risk for personal tool, but validate URL scheme is `http/https` |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| No acknowledgement when URL is sent to bot | User doesn't know if message was received | Send `"✓ Queued"` reply on receipt (requires separate webhook or polling bot — acceptable as v2 add-on) |
| Empty digest delivered to Telegram | Confusing "today's digest" with no content | Don't send Telegram message if no URLs were processed; or send "No URLs to process today" |
| Digest sent with raw Markdown that Telegram doesn't render | Asterisks and underscores visible in text | Test `parse_mode="Markdown"` or use `parse_mode="HTML"` with escaped content |
| No indication which URLs failed | User doesn't know content is missing | Include failed URL list at end of digest: "⚠️ Could not fetch: [url]" |

---

## "Looks Done But Isn't" Checklist

- [ ] **Telegram polling:** Verify `offset = last_id + 1` in state.json after a run — not `last_id`
- [ ] **Webhook clean:** Run `getWebhookInfo` after setup — `url` field must be empty string
- [ ] **GITHUB_TOKEN permissions:** Check Actions job has `permissions: contents: write` — not just repo-level setting
- [ ] **Git identity:** Confirm `git config user.email` and `user.name` are set in workflow before any commit step
- [ ] **Concurrency group:** Verify `concurrency.group` is a fixed string (not `github.run_id`) to serialize runs
- [ ] **Timeout on requests:** `grep -r "requests.get" --include="*.py"` — every call must have `timeout=`
- [ ] **Gemini SDK version:** `pip list | grep genai` — only `google-genai` should appear, not `google-generativeai`
- [ ] **Message chunking:** Send a test digest > 4096 chars and verify it arrives as multiple Telegram messages
- [ ] **Content type check:** Verify that a JS-rendered URL writes to `data/failed/` instead of crashing or producing empty summary
- [ ] **state.json committed early:** Verify git log shows offset update even when URL processing fails mid-run

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Wrong offset in state.json (duplicate processing) | LOW | Edit `state.json` manually to correct offset; `git commit -m "fix: correct telegram offset"`; delete duplicate `data/sources/` entries |
| Push failed, state.json not committed | LOW | Manually set `state.json` offset to the last processed update_id + 1; push |
| Webhook active, zero updates fetched | LOW | Run `deleteWebhook` curl command; verify with `getWebhookInfo`; re-run pipeline |
| GITHUB_TOKEN push denied | LOW | Add `permissions: contents: write` to workflow YAML; re-run |
| Partial digest due to 429 | LOW | Failed URLs are in `data/failed/`; re-run manually via workflow_dispatch |
| Daily digest > 4096 chars, delivery failed | LOW | Add chunking logic; commit was successful so data is safe; re-run delivery only |
| google-generativeai mixed with google-genai | MEDIUM | `pip uninstall google-generativeai`; audit all imports; run tests |
| Workflow disabled by GitHub (60-day dormancy) | LOW | Re-enable from Actions UI; daily commits prevent recurrence |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Offset off-by-one | Telegram polling client implementation | `state.json` shows `last_seen_id + 1` after test run |
| Git amend push conflict | GitHub Actions workflow + concurrency config | Two manual dispatches in quick succession; second queues, doesn't conflict |
| GITHUB_TOKEN lacks contents:write | Workflow setup | First test commit succeeds from Actions runner |
| Webhook active blocks polling | Initial setup / bot creation | `getWebhookInfo` returns empty `url` |
| Telegram 4096-char limit | Delivery implementation | Send test digest > 4096 chars; verify multiple messages received |
| Requests timeout | URL fetching implementation | Pipeline completes within 10 min even with a slow URL |
| Gemini 429 rate limit | Gemini integration | 5+ URL batch completes without abort; slow URLs go to failed/ |
| SDK confusion (google-generativeai) | Dependency declaration | `pip list` shows only `google-genai` |
| state.json not committed on partial failure | Pipeline orchestration | Kill pipeline mid-run; verify offset is persisted in repo |
| JS-rendered pages | Content extraction | Test with a known SPA URL; writes to data/failed/ not empty summary |
| GitHub cron dormancy | Operational awareness | Documented in README; daily commit pattern prevents it |

---

## Sources

- Telegram Bot API `getUpdates` spec: https://core.telegram.org/bots/api#getupdates (official, March 2026)
- GitHub `GITHUB_TOKEN` permissions: https://docs.github.com/en/actions/concepts/security/github_token (official)
- GitHub Actions `contents: write` requirement: https://docs.github.com/en/actions/writing-workflows/choosing-what-your-workflow-does/controlling-permissions-for-github_token (official)
- Google Gen AI Python SDK (google-genai): https://github.com/googleapis/python-genai (official, active)
- `google-generativeai` archived Dec 2025: https://github.com/google-gemini/deprecated-generative-ai-python (official archive notice)
- GitHub cron dormancy policy: documented in GitHub Actions billing/limits docs (60-day inactivity)

---
*Pitfalls research for: Serverless Telegram bot + GitHub Actions + Gemini AI pipeline*
*Researched: 2026-03-15*
