# GSD Framework Reference

> Compact reference for agent sessions. GSD (Get Shit Done) v1.22.4.
> Framework installed at: `.opencode/get-shit-done/`
> Full workflow files: `.opencode/get-shit-done/workflows/<command>.md`
> Full reference files: `.opencode/get-shit-done/references/<name>.md`

---

## §1 — Command Routing

### Project initialization

| Command | When to use |
|---------|-------------|
| `/gsd-new-project` | Starting a brand-new project (questioning → research → requirements → roadmap) |
| `/gsd-map-codebase` | Brownfield: map existing codebase before initializing |
| `/gsd-new-milestone <name>` | Starting the next milestone on an existing project |

### Phase planning

| Command | When to use |
|---------|-------------|
| `/gsd-discuss-phase <N>` | Capture your vision for a phase before planning (creates CONTEXT.md) |
| `/gsd-research-phase <N>` | Deep domain research for niche/complex phases (3D, ML, audio, etc.) |
| `/gsd-list-phase-assumptions <N>` | Preview Claude's intended approach before planning starts |
| `/gsd-plan-phase <N>` | Create executable PLAN.md files for a phase (spawns researcher + planner + checker) |
| `/gsd-plan-phase <N> --prd file.md` | PRD express path — skip discuss-phase, PRD becomes locked decisions |

### Execution

| Command | When to use |
|---------|-------------|
| `/gsd-execute-phase <N>` | Execute all plans in a phase (wave-based, parallel, verifies goal after) |
| `/gsd-execute-phase <N> --gaps-only` | Re-execute only gap-closure plans after verification found gaps |

### Quick mode (small tasks, no full ceremony)

| Command | When to use |
|---------|-------------|
| `/gsd-quick` | Small, well-defined task — spawns planner + executor, skips researcher/checker/verifier |
| `/gsd-quick --discuss` | Quick task with lightweight discussion first |
| `/gsd-quick --full` | Quick task with plan-checking + verification (no researcher) |

### Roadmap management

| Command | When to use |
|---------|-------------|
| `/gsd-add-phase <description>` | Add new phase to end of current milestone |
| `/gsd-insert-phase <after> <description>` | Insert urgent work as decimal phase (e.g. 7.1 between 7 and 8) |
| `/gsd-remove-phase <N>` | Remove a future unstarted phase and renumber |

### Milestone management

| Command | When to use |
|---------|-------------|
| `/gsd-complete-milestone <version>` | Archive milestone, create git tag, prepare for next version |
| `/gsd-audit-milestone` | Audit completion against original intent, find gaps and tech debt |
| `/gsd-plan-milestone-gaps` | Create phases to close gaps found by audit |

### Progress & session management

| Command | When to use |
|---------|-------------|
| `/gsd-progress` | Check status, see what's next, route to action — use at session start |
| `/gsd-resume-work` | Restore full context after a break (reads STATE.md, shows options) |
| `/gsd-pause-work` | Create context handoff when stopping mid-phase |

### Debugging

| Command | When to use |
|---------|-------------|
| `/gsd-debug "description"` | Start systematic debug session (scientific method, persists across `/clear`) |
| `/gsd-debug` | Resume active debug session after `/clear` |

### Todos

| Command | When to use |
|---------|-------------|
| `/gsd-add-todo` | Capture idea from current conversation context |
| `/gsd-add-todo <description>` | Capture explicit todo |
| `/gsd-check-todos [area]` | Review pending todos, select one to work on |

### UAT & verification

| Command | When to use |
|---------|-------------|
| `/gsd-verify-work [phase]` | Conversational UAT — present tests, diagnose failures, create fix plans |

### Configuration

| Command | When to use |
|---------|-------------|
| `/gsd-settings` | Toggle researcher/checker/verifier agents, select model profile |
| `/gsd-set-profile <profile>` | Quick switch: `quality` / `balanced` / `budget` |
| `/gsd-help` | Show full command reference |
| `/gsd-update` | Update GSD to latest version |

---

## §2 — Core Workflow Sequence

```
New project:
  /gsd-new-project → /clear → /gsd-plan-phase 1 → /clear → /gsd-execute-phase 1 → repeat

Resuming after a break:
  /gsd-progress   (routes to next action automatically)

Adding urgent work mid-milestone:
  /gsd-insert-phase 5 "Critical fix" → /gsd-plan-phase 5.1 → /gsd-execute-phase 5.1

Completing a milestone:
  /gsd-complete-milestone 1.0.0 → /clear → /gsd-new-milestone "v2 Features"
```

**Always `/clear` before invoking a new `/gsd-*` command.** Each command needs a fresh
context window. The GSD tools CLI (`gsd-tools.cjs`) and STATE.md provide continuity.

---

## §3 — Checkpoint Protocol

Checkpoints are formalized human-in-the-loop points. **They are for verification and
decisions, not manual work.** If Claude can automate it with CLI/API, Claude must automate it.

### Three checkpoint types

**`checkpoint:human-verify`** (90% of cases)
- Claude automated everything; human confirms it works visually/functionally
- Claude starts dev servers, seeds databases, runs builds BEFORE the checkpoint
- Never ask the human to run CLI commands — only to visit URLs or verify UX

**`checkpoint:decision`** (9% of cases)
- Human makes an architectural or technology choice
- Present options with pros/cons; human selects

**`checkpoint:human-action`** (1% of cases — rare)
- Truly unavoidable manual step with no CLI/API (email verification link, SMS 2FA)
- Or: Claude tried automation and hit an auth gate — ask for credentials, then retry

### Execution protocol

When encountering `type="checkpoint:*"`:
1. Stop immediately — do not proceed to next task
2. Display the checkpoint clearly with progress, what was built, how to verify
3. Wait for user response
4. Verify if possible (run tests, curl URLs)
5. Resume only after confirmation

### Automation rule

> If it has a CLI or API, Claude runs it. Never ask the human to perform automatable work.

| Automatable (Claude does it) | Not automatable (human does it) |
|------------------------------|----------------------------------|
| Deploy (`vercel`, `fly`, etc.) | Click email verification link |
| Create webhooks via API | Enter credit card with 3DS |
| Write `.env` files | Complete OAuth in browser |
| Run tests and builds | Visually verify UI looks correct |
| Start dev servers | Test interactive user flows |

---

## §4 — Git Commit Format

GSD uses per-task atomic commits. Each completed task gets its own commit immediately.

### Task commit format

```
{type}({phase}-{plan}): {task-name}

- Key change 1
- Key change 2
- Key change 3
```

**Commit types:** `feat` · `fix` · `test` · `refactor` · `perf` · `chore`

Examples:
```
feat(03-02): add webhook signature verification
test(02-01): add failing test for JWT generation
fix(04-01): handle empty response from content fetcher
chore(01-01): install trafilatura dependency
```

### Plan completion commit (after all tasks done)

```
docs({phase}-{plan}): complete {plan-name} plan

Tasks completed: N/N
- Task 1 name
- Task 2 name
```

Note: code files are NOT included in this commit — already committed per-task.

### Key principle

> Commit outcomes, not process. The git log should read like a changelog of what shipped.

Do NOT commit: PLAN.md creation, RESEARCH.md (intermediate artifacts).
DO commit: each task completion, plan metadata, project initialization.

---

## §5 — TDD Heuristic

**Use TDD when:** you can write `expect(fn(input)).toBe(output)` before writing `fn`.

TDD candidates: business logic, API endpoints, data transforms, validation rules,
algorithms, state machines, utility functions with clear specs.

**Skip TDD for:** UI/styling, config changes, glue code, one-off scripts, simple CRUD,
exploratory prototyping.

### Red-Green-Refactor cycle (2-3 commits per feature)

```
RED:     Write failing test → run test (must fail) → commit: test(phase-plan): add failing test
GREEN:   Implement minimally to pass → run test (must pass) → commit: feat(phase-plan): implement feature
REFACTOR: Clean up if obvious → run tests (must still pass) → commit: refactor(phase-plan): clean up (optional)
```

TDD plans target ~40% context usage (lower than standard ~50%) due to the iterative cycle.

---

## §6 — Session Management Rules

- **Always `/clear` before a new `/gsd-*` command** — each command needs a fresh 200k context
- **Start of session:** run `/gsd-progress` or `/gsd-resume-work` to restore context
- **Mid-work capture:** use `/gsd-add-todo` to capture ideas without derailing execution
- **Stopping mid-phase:** run `/gsd-pause-work` to create a context handoff file

### Key files for project state

| File | Purpose |
|------|---------|
| `.planning/STATE.md` | Authoritative project state — current position, decisions, blockers |
| `.planning/ROADMAP.md` | Phase breakdown with progress and completion status |
| `.planning/config.json` | Workflow mode (`interactive`/`yolo`), agents enabled, model profile |
| `.planning/REQUIREMENTS.md` | All requirements with REQ-IDs and traceability |

---

## §7 — Continuation Format

At the end of every command output, present next steps using this format:

```
---

## ▶ Next Up

**Phase N: Name** — one-line description from ROADMAP.md

`/gsd-execute-phase N`

<sub>`/clear` first → fresh context window</sub>

---

**Also available:**
- `/gsd-plan-phase N --research` — re-research first
- `cat .planning/phases/NN-name/*-PLAN.md` — review plans

---
```

Rules:
- Always show what it is (name + description), never just a command
- Command in inline backticks (renders as clickable link)
- Always include the `/clear` explanation
- Use "Also available:" not "Other options:"

---

## §8 — Finding Full Protocol Detail

When you need the complete workflow for a command you're about to orchestrate, read:

```
.opencode/get-shit-done/workflows/<command-slug>.md
```

For example, before orchestrating `execute-phase`:
```bash
# Read the full workflow
cat .opencode/get-shit-done/workflows/execute-phase.md
```

Available workflows (34 files):
`new-project` · `plan-phase` · `execute-phase` · `execute-plan` · `discuss-phase` ·
`research-phase` · `verify-phase` · `verify-work` · `quick` · `progress` ·
`resume-project` · `pause-work` · `debug` · `add-todo` · `check-todos` ·
`new-milestone` · `complete-milestone` · `audit-milestone` · `plan-milestone-gaps` ·
`add-phase` · `insert-phase` · `remove-phase` · `map-codebase` · `transition` ·
`add-tests` · `cleanup` · `health` · `help` · `settings` · `set-profile` ·
`list-phase-assumptions` · `validate-phase` · `update` · `discovery-phase`

When you need a specific behavioral reference, read:

```
.opencode/get-shit-done/references/<name>.md
```

Available references:
- `checkpoints.md` — Full checkpoint protocol with all examples and anti-patterns
- `tdd.md` — Full TDD cycle, test quality rules, framework setup
- `git-integration.md` — Full git commit format with examples and rationale
- `continuation-format.md` — Full continuation format with all variants
- `model-profiles.md` — Model profile definitions (quality/balanced/budget)
- `verification-patterns.md` — Verification and UAT patterns
- `planning-config.md` — Config schema reference
- `questioning.md` — Deep questioning techniques for project initialization
