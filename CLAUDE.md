# tldr-bot — Project Instructions

## Project

Serverless Telegram URL digest pipeline. Receives URLs via Telegram bot, fetches and
summarizes article content via OpenRouter (Gemini 2.0 Flash), assembles a daily Markdown
digest, and delivers it back to Telegram. Runs entirely on GitHub Actions — no persistent
server. State stored in git (`state.json`, `data/`).

**Stack:** Python · uv · GitHub Actions · Telegram Bot API · OpenRouter
**Source:** `src/` · **Tests:** `tests/` · **Prompts:** `prompts/`

---

## Development: GSD Framework Required

All non-trivial work — new features, bug fixes, refactors, performance work — **must go
through the GSD (Get Shit Done) framework.** Do not make ad-hoc edits to `src/` without
a GSD plan.

GSD is installed at `.opencode/get-shit-done/` (v1.22.4).
Commands are invoked as `/gsd-*` slash commands in opencode or Claude Code.

### Routing: which command to use

| Situation | Command |
|-----------|---------|
| New feature set / milestone | `/gsd-new-milestone "name"` |
| Plan next phase of work | `/gsd-plan-phase <N>` |
| Execute a planned phase | `/gsd-execute-phase <N>` |
| Small isolated task | `/gsd-quick` |
| Bug investigation | `/gsd-debug "description"` |
| Start of session / resume after break | `/gsd-progress` or `/gsd-resume-work` |
| Capture idea mid-work | `/gsd-add-todo` |
| Urgent unplanned work | `/gsd-insert-phase <after> "description"` then plan + execute |
| Check what's available | `/gsd-help` |

### Full GSD reference

Use **lazy loading** to avoid context bloat:
- Do **not** load `.planning/GSD-REFERENCE.md` for every task by default.
- Load it only when the task requires GSD orchestration details you cannot infer from this file.
- If the task is simple and already mapped by the routing table above, proceed without loading it.

Read `.planning/GSD-REFERENCE.md` when you need:
- Complete command listing with descriptions (all 32+ commands)
- Checkpoint protocol (when to stop, what to automate vs. delegate to human)
- Git commit format for per-task atomic commits
- TDD heuristic and red-green-refactor cycle
- Session management rules (always `/clear` before a new GSD command)
- Continuation format for end-of-command output
- How to fetch full workflow or reference details for any command

Escalation order for additional docs:
1. This `CLAUDE.md` (default)
2. `.planning/GSD-REFERENCE.md` (only if needed, for summarized guidance)
3. `.opencode/get-shit-done/workflows/<command-slug>.md` or `.opencode/get-shit-done/references/<name>.md` (only when exact procedural details are still missing)

When you need the **complete workflow** for a specific command:
```
.opencode/get-shit-done/workflows/<command-slug>.md
```

When you need a **specific behavioral reference** (checkpoints, TDD, git, etc.):
```
.opencode/get-shit-done/references/<name>.md
```

---

## Project State

| File | Purpose |
|------|---------|
| `.planning/STATE.md` | Current position, recent decisions, blockers — read this first |
| `.planning/ROADMAP.md` | Phase breakdown with progress |
| `.planning/REQUIREMENTS.md` | All requirements with REQ-IDs |
| `.planning/config.json` | Workflow mode, agents enabled, model profile |
