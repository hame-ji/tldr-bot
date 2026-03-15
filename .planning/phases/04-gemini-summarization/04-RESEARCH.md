# Phase 4: OpenRouter Summarization - Research

**Researched:** 2026-03-15
**Status:** Ready for execution

## Objective

Add OpenRouter summarization for article text and transcript-grounded YouTube content with prompt-file control, cached free-model discovery, request spacing, and retry handling.

## Requirement Mapping

- **SUM-01**: Summarize article content via OpenRouter free models.
- **SUM-02**: Summarize YouTube content from fetched transcript text.
- **SUM-03**: Prompt behavior loaded from `prompts/summarize.txt`.
- **SUM-04**: Write summaries to `data/sources/YYYY-MM-DD/slug.md`.
- **SUM-05**: Apply inter-request spacing and retry on 429 failures.

## Design Notes

- Keep OpenRouter API wrapper in `src/summarizer.py`.
- Build one reusable generator path with retry policy + free-model fallback ordering.
- Add transcript retrieval with `youtube-transcript-api` and strict failure when unavailable.
- Keep output writing explicit and deterministic via URL slug + run date.
- Convert summarize failures into failure records using existing failure writer.

## Risks and Mitigations

1. Prompt file missing -> explicit runtime error before API call.
2. No free model available -> fail closed and write failure record.
3. Missing transcript -> fail closed and write failure record.
4. Rate-limit bursts -> backoff retry with capped attempts.

---

*Phase: 04-gemini-summarization*
*Research complete: 2026-03-15*
