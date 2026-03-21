# tests/

Last-Reviewed-Date: 2026-03-21
Last-Reviewed-Commit: 1ee4e95
Review-Note: Polish: headers refreshed with parent CLAUDE.md amend.

- Framework: `unittest` with `unittest.mock`. No pytest.
- Mock at I/O boundaries: network, filesystem, environment. Never hit real APIs.
- Tests are behavior-focused: assert on status dicts, counts, routing decisions — not formatting.
- Thread safety matters: `test_summarizer.py` verifies spacing locks, cache init races, and failure isolation under concurrency. Preserve these.
- Each module has a dedicated test file. New logic needs regression coverage in the matching file.
- Don't couple tests to unstable formatting unless formatting IS the contract (e.g. digest template).
