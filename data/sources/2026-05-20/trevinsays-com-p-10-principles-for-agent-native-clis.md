Title: 10 Principles for Agent-Native CLIs

TL;DR: CLI design must shift from human-first to agent-first, with both defensive measures (non-interactive, structured output, safe retries) and compounding features (cross-CLI vocabulary, async wait, profiles, two-way I/O) to make agents efficient and failures rare.

Key points:
- **Non-interactive by default**: Commands must run without prompts (e.g., `--force`, `--no-input`) and detect non-TTY to avoid silent hangs.
- **Structured, parseable output**: Always `--json`, stdout for data, stderr for diagnostics, consistent exit codes; no ANSI when not a terminal.
- **Errors that teach**: Include valid enumerations in error messages so agents self-correct in one retry (e.g., "must be one of: public, private, unlisted").
- **Safe retries and explicit mutations**: Idempotent creates (with natural keys or tokens), `--dry-run` for destructive ops, and persistent job ledgers for async workflows.
- **Async-aware execution with `--wait`**: Collapse submit-poll-collect into one command, backed by a durable job ledger that survives disconnects.
- **Persistent identity through profiles**: Named bundles saved once (e.g., `profile save my-podcast`) and reused, with precedence: flag > env > profile > default.

Why it matters:
- Agents now drive the majority of CLI calls; these principles eliminate token waste, retry loops, and silent failures that human-centric CLIs tolerate.

Evidence:
- Cloudflare rebuilt Wrangler around a TypeScript schema that enforces naming rules (`get` not `info`, `--force` not `--skip-confirmations`) and serves ~3,000 operations in under 1,000 tokens via their Code Mode MCP.
- HeyGen’s CLI consistently applies technique with `--deliver` routing (stdout/file/webhook) and a feedback command to report friction upstream.

Caveat:
- The author notes these principles evolved from an earlier set and will likely continue to change; they are based on personal work plus Cloudflare and HeyGen experiences.
