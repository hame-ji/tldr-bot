# Phase 5: Digest Generation & Delivery - Research

**Researched:** 2026-03-15
**Status:** Ready for execution

## Objective

Generate a daily digest file from per-URL summaries, include failed URLs, and deliver the digest to Telegram with safe chunking and an empty-day no-send guard.

## Requirement Mapping

- **DGST-01**: Build and write daily digest file to `data/digests/YYYY-MM-DD.md`.
- **DGST-02**: Load digest format instructions from `prompts/digest.txt`.
- **DGST-03**: Include failed URLs in a dedicated digest section.
- **DGST-04**: Send digest content to configured Telegram chat.
- **DGST-05**: Chunk Telegram delivery at paragraph boundaries under 4096 chars.
- **DGST-06**: Skip digest generation and Telegram delivery when no URLs were processed.

## Design Notes

- Add `src/digest_generator.py` as a pure formatting + file-output module.
- Keep digest prompt file based (`prompts/digest.txt`) so output shape is tuneable without code changes.
- Build digest from pipeline result objects (successful summaries + failure records) so the failed section is explicit and deterministic.
- Choose Telegram `parse_mode="HTML"` for v1 to avoid Markdown escaping fragility; escape dynamic text before send.
- Implement chunking by paragraph (`\n\n`) with sequential send order and a fallback split for oversized single paragraphs.
- Add a hard no-op path when the run has zero processed URLs (return early before digest write/send).

## Risks and Mitigations

1. Telegram `400 Bad Request: message is too long` -> enforce <=4096 char chunking with tests.
2. Digest formatting drift -> keep formatter behavior behind `prompts/digest.txt` + snapshot-style tests.
3. Empty-day accidental sends -> guard in `main.py` before digest generation and delivery calls.

---

*Phase: 05-digest-generation-delivery*
*Research complete: 2026-03-15*
