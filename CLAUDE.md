# tldr-bot

Serverless Telegram URL digest pipeline. Receives URLs via Telegram bot, summarizes
articles (OpenRouter / Gemini Flash) and YouTube videos (NotebookLM), assembles a daily
Markdown digest, delivers it back to Telegram. Runs on GitHub Actions — no server.

**Stack:** Python · uv · GitHub Actions · Telegram Bot API · OpenRouter · NotebookLM
**State:** `state.json` (Telegram offset) · `data/` (digests, sources, failures)

## Rules

- Non-trivial work goes through GSD (`/gsd-*` commands).
- Module-specific guidance lives in child `CLAUDE.md` files, not here.
- The routing manifest below is an exception: it must live in this file because
  `scripts/validate_claude_sync.py` parses it from here.
- Resolve children via the routing manifest below (longest-prefix match).
- Paths not covered by any route below have no required child doc; still follow GSD for
  non-trivial work.
- If staged changes touch a routed path, the matched child `CLAUDE.md` must be edited in
  the same commit with updated review headers (`Last-Reviewed-Date`,
  `Last-Reviewed-Commit` as lowercase hex SHA 7-40 chars, `Review-Note`).
  Pre-commit hook enforces this.

## GSD References (lazy-load)

1. This file
2. `.planning/GSD-REFERENCE.md` when orchestration detail is needed
3. `.opencode/get-shit-done/workflows/<slug>.md` or `references/<name>.md` for procedures

## Routing Manifest

<!-- CLAUDE_ROUTING_MANIFEST_START -->
```yaml
routing_manifest:
  version: 1
  routes:
    - path: "src/summarization/"
      claude: "src/summarization/CLAUDE.md"
    - path: "src/telemetry/"
      claude: "src/telemetry/CLAUDE.md"
    - path: "src/"
      claude: "src/CLAUDE.md"
    - path: "scripts/"
      claude: ".github/CLAUDE.md"
    - path: ".github/workflows/"
      claude: ".github/CLAUDE.md"
    - path: "tests/"
      claude: "tests/CLAUDE.md"
```
<!-- CLAUDE_ROUTING_MANIFEST_END -->

## Setup

```bash
git config core.hooksPath .githooks
```
