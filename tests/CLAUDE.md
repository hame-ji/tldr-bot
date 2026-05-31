# tests/

Last-Reviewed-Date: 2026-05-31
Last-Reviewed-Commit: d2177d2
Review-Note: Added test_pipeline_integration.py verifying end-to-end pipeline dict contracts with mocks at HTTP boundary only.

- Framework: `unittest` with `unittest.mock`. No pytest.
- Mock at I/O boundaries: network, filesystem, environment. Never hit real APIs.
- Tests are behavior-focused: assert on status dicts, counts, routing decisions — not formatting.
- Thread safety matters: `test_summarizer.py` verifies spacing locks, cache init races, and failure isolation under concurrency. Preserve these.
- Each module has a dedicated test file. New logic needs regression coverage in the matching file; CI entrypoints include subprocess tests for module invocation, helper extraction, empty-day commit policy, helper failure diagnostics, and malformed run_metrics tolerance.
- Don't couple tests to unstable formatting unless formatting IS the contract (e.g. digest template).
