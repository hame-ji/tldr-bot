# Phase 1: Infrastructure & Bot Setup - Research

**Researched:** 2026-03-15
**Status:** Ready for planning

## Objective

Answer: "What do I need to know to plan Phase 1 well?"

Phase 1 must establish a runnable, push-capable GitHub Actions environment and verify Telegram polling preconditions (valid token + no webhook).

## Stack and Dependency Notes

- Runtime target is Python on GitHub Actions (`ubuntu-latest`) with no persistent service.
- Pin exact package versions in `requirements.txt` to make runs reproducible and avoid SDK drift.
- Use `google-genai` only (do not use deprecated `google-generativeai`).
- Keep initial structure minimal: `src/`, `data/`, `prompts/` plus placeholder files where needed to keep directories in git.

## Infrastructure Requirements Mapping

- **INFRA-01**: Create repository scaffold (`data/`, `prompts/`, `src/`) and verify paths exist in CI.
- **INFRA-02**: Pin exact versions for `pyTelegramBotAPI`, `google-genai`, `trafilatura`, `requests`, `python-slugify`.
- **INFRA-03**: Use repository secrets `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `GEMINI_API_KEY`.
- **INFRA-04**: Define `.github/workflows/digest.yml` with cron at `0 7 * * *` and `workflow_dispatch`.
- **INFRA-05**: Explicit `permissions: contents: write` is required for pushes with `GITHUB_TOKEN`.
- **INFRA-06**: `actions/checkout` must use `fetch-depth: 0` for amend-based history operations in later phases.
- **INFRA-07**: `concurrency.cancel-in-progress: false` so scheduled runs queue rather than cancel.

## Telegram Setup Notes

- **BOT-01**: Bot must be created in BotFather and token validated via API (`getMe`).
- **BOT-02**: Polling and webhooks are mutually exclusive; run `deleteWebhook` before polling validation.
- **BOT-03**: Capture and persist `ALLOWED_CHAT_ID` from a known user message (`getUpdates`) and wire into secrets/env.

## Validation Architecture

Phase 1 is infrastructure-heavy, so validation should use fast smoke commands with one focused live API check.

### Fast Feedback Commands

- `python -m compileall src`
- `python -m pip install -r requirements.txt`
- `python - <<'PY'\nimport yaml, pathlib\npathlib.Path('.github/workflows/digest.yml').read_text()\nprint('workflow-readable')\nPY`

### API Validation Pattern

- Validate bot token: `https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getMe`
- Clear webhook: `https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/deleteWebhook?drop_pending_updates=true`
- Verify polling unlocked: `https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getUpdates`

### Nyquist Sampling Guidance

- Every implementation task should include an automated command.
- Manual setup tasks (BotFather, creating secrets) should be isolated as explicit checkpoint tasks.
- Keep no more than two implementation tasks per plan for low-context, high-certainty execution.

## Pitfalls to Prevent

1. Missing `permissions: contents: write` causes silent push failures in GitHub Actions.
2. `fetch-depth: 1` breaks amend strategy in later phases.
3. Forgetting `deleteWebhook` yields empty/blocked `getUpdates` behavior.
4. Using `google-generativeai` introduces dead dependency risk.
5. Relying on manual memory for secrets/chat ID instead of explicit setup checklist causes flaky onboarding.

## Planning Implications

- Split into 2-3 plans:
  - Repo scaffold and pinned dependencies.
  - Workflow authoring + CI self-check script.
  - Credential/bot validation checkpoints with reproducible commands.
- Include one checklist artifact (`docs/setup-checklist.md` or phase summary instructions) to reduce setup errors.

---

*Phase: 01-infrastructure-bot-setup*
*Research complete: 2026-03-15*
