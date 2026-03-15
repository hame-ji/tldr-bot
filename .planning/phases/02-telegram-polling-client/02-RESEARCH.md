# Phase 2: Telegram Polling Client - Research

**Researched:** 2026-03-15
**Status:** Ready for execution

## Objective

Build a deterministic polling client that fetches updates once per run, advances offset correctly (`last_update_id + 1`), filters by allowed chat, and extracts URLs from message text.

## Requirement Mapping

- **POLL-01**: Poll `getUpdates` at pipeline start.
- **POLL-02**: Persist offset as `max(update_id) + 1`.
- **POLL-03**: Read/write offset in repo-root `state.json`.
- **POLL-04**: Ensure offset persistence happens before downstream URL processing.
- **POLL-05**: Extract URLs with regex from free-form text.
- **POLL-06**: Ignore messages from other chats.

## Design Notes

- Keep polling logic in `src/telegram_client.py` with clear pure helpers (`extract_urls`, offset read/write).
- Make network call isolated in one function for straightforward mocking in tests.
- Keep state schema minimal and explicit: `{ "telegram_offset": <int> }`.
- Treat missing `state.json` as first-run state (no offset).

## Test Strategy

- Unit-test URL extraction edge cases (embedded URLs + trailing punctuation).
- Unit-test offset write semantics with mocked update payloads.
- Unit-test chat filtering behavior with mixed chat IDs.
- Run `compileall` + `unittest` in CI workflow to keep fast feedback.

## Risks and Mitigations

1. Off-by-one offset regression -> lock with explicit unit test expecting `max + 1`.
2. Empty updates could reset offset incorrectly -> keep prior offset when no updates.
3. Regex over-capture of punctuation -> trim common trailing punctuation after match.

---

*Phase: 02-telegram-polling-client*
*Research complete: 2026-03-15*
