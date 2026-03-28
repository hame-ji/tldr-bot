# Drift Register (Truth Alignment)

Date: 2026-03-28
Status: Closed for tracked high-risk contract items

| Claim Area | Drifted Statement | Runtime Truth Source | Resolution |
|---|---|---|---|
| Summarization backend | Planning docs referenced Gemini-only flow | `src/summarizer.py`, `src/summarization/`, `architecture.md` | Updated planning docs to OpenRouter + NotebookLM routed model |
| YouTube scope | Requirements/state claimed YouTube excluded in v1 | `src/content_fetcher.py`, `src/summarizer.py`, tests for YouTube paths | Updated requirements/state/roadmap to reflect live YouTube support via NotebookLM |
| Commit strategy | Roadmap/state/phase validation described amend + force-with-lease | `.github/workflows/digest.yml` commit step | Updated docs to create-only commit behavior with skip gates |
| Checkout depth | Requirements expected `fetch-depth: 0` | `.github/workflows/digest.yml` uses `fetch-depth: 1` | Updated requirement text to match explicit live checkout depth |
| Chat filter env name | Planning docs used `ALLOWED_CHAT_ID` | `src/_config.py` uses `TELEGRAM_CHAT_ID` | Updated planning docs to `TELEGRAM_CHAT_ID` |
| Dependency source of truth | Planning docs referenced `requirements.txt` pinning | `pyproject.toml`, `uv.lock` | Updated docs to uv/pyproject lock model |
| Requirement status table | Traceability marked all requirements pending | Existing implemented modules/tests/workflow | Updated traceability status to completed |

## Scope of this register

- Covers behavior contracts that materially affect architecture understanding and operations.
- Does not track historical plan wording preserved for context in archived artifacts.
