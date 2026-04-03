# src/telemetry/

Last-Reviewed-Date: 2026-04-01
Last-Reviewed-Commit: 680150e
Review-Note: Parser/output contract now includes NotebookLM preflight incident signals and replay/circuit-breaker counters with fail-soft defaults.

- `run_metrics.py`: frozen `RunMetrics` dataclass emitted as `run_metrics:` JSON log line. `metrics_version=1`.
- `pipeline_log_parser.py`: extracts `run_outcome:` and `run_metrics:` from pipeline stdout. Tolerant on missing metrics (fills "unknown"). Used by CI to set workflow outputs.
- `run_history/`: fetches past workflow run logs via GitHub API, parses metrics from zipped logs, renders Markdown performance summary table.
- Metric keys are the contract. Renaming or removing a key breaks CI parsing. Add new keys, don't rename old ones.
- Parser must handle malformed/missing data gracefully (return "unknown", not crash).
- Keep `report.py` rendering pure (no network). Network stays in `github_client.py`.
- Test metrics parsing, fallback defaults, and table rendering when contracts change.
