# tests/

Last-Reviewed-Date: 2026-03-22
Last-Reviewed-Commit: 1644459
Review-Note: Added direct subprocess coverage for extract_processed_urls helper output on empty and non-empty runs.

- Framework: `unittest` with `unittest.mock`. No pytest.
- Mock at I/O boundaries: network, filesystem, environment. Never hit real APIs.
- Tests are behavior-focused: assert on status dicts, counts, routing decisions — not formatting.
- Thread safety matters: `test_summarizer.py` verifies spacing locks, cache init races, and failure isolation under concurrency. Preserve these.
- Each module has a dedicated test file. New logic needs regression coverage in the matching file; CI entrypoints include subprocess tests for module invocation, helper extraction, and empty-day commit policy.
- Don't couple tests to unstable formatting unless formatting IS the contract (e.g. digest template).
