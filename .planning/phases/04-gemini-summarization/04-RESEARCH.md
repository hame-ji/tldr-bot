# Phase 4: Gemini Summarization - Research

**Researched:** 2026-03-15
**Status:** Ready for execution

## Objective

Add Gemini summarization for article text and YouTube URLs with prompt-file control, basic request spacing, and retry handling for rate limits.

## Requirement Mapping

- **SUM-01**: Summarize article content via `google-genai`.
- **SUM-02**: Summarize YouTube URLs natively via Gemini.
- **SUM-03**: Prompt behavior loaded from `prompts/summarize.txt`.
- **SUM-04**: Write summaries to `data/sources/YYYY-MM-DD/slug.md`.
- **SUM-05**: Apply inter-request spacing and retry on 429 failures.

## Design Notes

- Keep Gemini API wrapper in `src/summarizer.py`.
- Build one reusable generator path with retry policy.
- Keep output writing explicit and deterministic via URL slug + run date.
- Convert summarize failures into failure records using existing failure writer.

## Risks and Mitigations

1. Prompt file missing -> explicit runtime error before API call.
2. 429 bursts -> 60s backoff retry with capped attempts.
3. Empty/blocked API responses -> treat as failure and write to `data/failed/`.

---

*Phase: 04-gemini-summarization*
*Research complete: 2026-03-15*
