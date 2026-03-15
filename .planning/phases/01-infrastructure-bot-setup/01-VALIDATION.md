---
phase: 1
slug: infrastructure-bot-setup
status: draft
nyquist_compliant: false
wave_0_complete: true
created: 2026-03-15
---

# Phase 1 - Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Python built-in checks + workflow smoke validation |
| **Config file** | none |
| **Quick run command** | `python -m compileall src` |
| **Full suite command** | `python -m pip install -r requirements.txt && python -m compileall src` |
| **Estimated runtime** | ~20 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m compileall src`
- **After every plan wave:** Run `python -m pip install -r requirements.txt && python -m compileall src`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 01-01-01 | 01 | 1 | INFRA-01 | smoke | `test -d data && test -d prompts && test -d src` | ✅ | ⬜ pending |
| 01-01-02 | 01 | 1 | INFRA-02 | dependency | `python -m pip install -r requirements.txt` | ✅ | ⬜ pending |
| 01-02-01 | 02 | 1 | INFRA-04 | config | `python - <<'PY'\nimport pathlib\npathlib.Path('.github/workflows/digest.yml').read_text()\nprint('ok')\nPY` | ✅ | ⬜ pending |
| 01-02-02 | 02 | 1 | INFRA-05, INFRA-06, INFRA-07 | lint/smoke | `python - <<'PY'\nimport pathlib\ny = pathlib.Path('.github/workflows/digest.yml').read_text()\nchecks = ['contents: write', 'fetch-depth: 0', 'cancel-in-progress: false']\nmissing = [c for c in checks if c not in y]\nassert not missing, f'missing: {missing}'\nprint('workflow-checks-ok')\nPY` | ✅ | ⬜ pending |
| 01-03-01 | 03 | 2 | BOT-01, BOT-02 | API smoke | `curl -fsS "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getMe" >/dev/null && curl -fsS "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/deleteWebhook?drop_pending_updates=true" >/dev/null` | ✅ | ⬜ pending |
| 01-03-02 | 03 | 2 | BOT-03, INFRA-03 | API/config | `curl -fsS "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getUpdates" >/dev/null` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Bot created in BotFather with intended name | BOT-01 | Bot creation only possible in Telegram client | Create bot in BotFather, copy token to GitHub Secret, then run automated `getMe` check |
| Secrets present in repository settings | INFRA-03 | Secret provisioning requires repository admin UI access | Add required secrets in GitHub UI, then run workflow dispatch and bot API checks |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
