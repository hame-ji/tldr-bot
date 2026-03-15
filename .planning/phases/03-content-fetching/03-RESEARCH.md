# Phase 3: Content Fetching - Research

**Researched:** 2026-03-15
**Status:** Ready for execution

## Objective

Implement robust URL classification and article extraction with strict timeouts and failure records so one bad URL never aborts a run.

## Requirement Mapping

- **FETCH-01**: Classify URL as `article` or `youtube`.
- **FETCH-02**: Extract article text with `trafilatura`.
- **FETCH-03**: Use hard timeout on HTTP requests (`timeout=(10, 30)`).
- **FETCH-04**: Persist failures to `data/failed/YYYY-MM-DD/slug.md` and continue.

## Design Notes

- Keep content logic in `src/content_fetcher.py`.
- Use hostname classification for YouTube detection.
- Use `requests.get(..., timeout=(10, 30))` + `raise_for_status()` for deterministic HTTP behavior.
- Use trafilatura extraction output length guard to treat empty/noisy pages as failures.
- Keep failure record writing in a dedicated helper for testability.

## Risks and Mitigations

1. Timeout missing on a path -> unit test asserts request call includes timeout tuple.
2. Extraction returns unusable text -> enforce minimum length and write failure record.
3. One URL error aborts run -> per-URL exception handling with structured failure result.

---

*Phase: 03-content-fetching*
*Research complete: 2026-03-15*
