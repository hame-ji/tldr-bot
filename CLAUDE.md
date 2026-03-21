# tldr-bot - Parent Instructions

This is the parent instruction file. Read this first, then route into child `CLAUDE.md`
files based on the module paths you touch.

## Global Rules

- All non-trivial work must use the GSD framework (`/gsd-*` commands).
- Keep module-specific instructions in child `CLAUDE.md` files, not here.
- Parent `CLAUDE.md` is the single source of truth for routing.
- Update child docs alongside code changes so module guidance stays current.

## Child Discovery Guidance

- Start with this parent file.
- Resolve child files with the routing manifest below.
- Use longest-prefix route matching when multiple routes match a file path.
- If no route matches, only parent rules apply.

## Commit-Time Child Sync Policy

Strict policy applies:

- If staged changes touch a routed path, the matched child `CLAUDE.md` must be edited in
  the same commit.
- Child docs must include these required review headers:
  - `Last-Reviewed-Date`
  - `Last-Reviewed-Commit`
  - `Review-Note`
- Pre-commit validation blocks commits that violate this policy.

## GSD References

Use lazy loading for GSD internals:

1. This `CLAUDE.md`
2. `.planning/GSD-REFERENCE.md` when additional orchestration detail is needed
3. `.opencode/get-shit-done/workflows/<command-slug>.md` or
   `.opencode/get-shit-done/references/<name>.md` for exact procedures

## Routing Manifest (Machine Readable)

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

## One-Time Local Hook Setup

Configure repo hooks once per clone:

```bash
git config core.hooksPath .githooks
```
