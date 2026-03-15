# Phase 1: User Setup Required

**Generated:** 2026-03-15
**Phase:** 01-infrastructure-bot-setup
**Status:** Incomplete

Complete these items for Phase 1 verification to pass. Claude automated everything possible; these items require human access to external dashboards/accounts.

## Environment Variables

| Status | Variable | Source | Add to |
|--------|----------|--------|--------|
| [ ] | `TELEGRAM_BOT_TOKEN` | Telegram BotFather -> `/newbot` -> token value | GitHub repository secrets |
| [ ] | `TELEGRAM_CHAT_ID` | Telegram `getUpdates` response -> `message.chat.id` from your target chat | GitHub repository secrets |
| [ ] | `GEMINI_API_KEY` | Google AI Studio -> API keys -> Create API key | GitHub repository secrets |

## Account Setup

- [ ] **Create Telegram bot via BotFather**
  - URL: https://t.me/BotFather
  - Skip if: You already created a dedicated bot for this repo

- [ ] **Create Gemini API key**
  - URL: https://aistudio.google.com/app/apikey
  - Skip if: You already have an active key intended for this project

## Dashboard Configuration

- [ ] **Add three required repository secrets**
  - Location: GitHub -> Repository -> Settings -> Secrets and variables -> Actions
  - Set to: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `GEMINI_API_KEY`

## Telegram Prep

- [ ] Send at least one message to your bot from the intended private chat.
- [ ] Confirm `deleteWebhook` is successful in workflow output (already automated by workflow).

## Verification

After completing setup, verify with:

```bash
gh workflow run digest.yml --ref main -f test_push=true
```

Then inspect the run and confirm these steps are green:
- `Validate required secrets`
- `Validate Telegram bot token and clear webhook`
- `Validate polling endpoint`
- `Optional push smoke test`

---

**Once all items complete:** Mark status as "Complete" at top of file.
