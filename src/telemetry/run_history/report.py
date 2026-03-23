from __future__ import annotations

from typing import Any, Optional

from .github_client import GitHubActionsClient
from .models import PerformanceSummary, PerformanceSummaryRow, RunHistorySnapshot
from .parser import extract_run_metrics_from_logs_zip


def _parse_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_optional_int(value: Optional[int]) -> str:
    return "-" if value is None else str(value)


def _format_optional_float(value: Optional[float]) -> str:
    return "-" if value is None else f"{value:.2f}"


def _format_optional_delta(value: Optional[float]) -> str:
    if value is None:
        return "-"
    return f"{value:+.2f}"


def _snapshot_from_metrics(
    run_id: int,
    run_number: int,
    status: str,
    fallback_date: str,
    metrics: Optional[dict[str, Any]],
) -> RunHistorySnapshot:
    if metrics is None:
        return RunHistorySnapshot(
            run_id=run_id,
            run_number=run_number,
            digest_date=fallback_date,
            status=status,
            processed_urls=None,
            pipeline_seconds=None,
            seconds_per_processed_url=None,
            fetch_failed_count=None,
            metrics_available=False,
        )

    return RunHistorySnapshot(
        run_id=run_id,
        run_number=run_number,
        digest_date=str(metrics.get("digest_date", fallback_date)),
        status=status,
        processed_urls=_parse_int(metrics.get("processed_urls")),
        pipeline_seconds=_parse_float(metrics.get("pipeline_seconds")),
        seconds_per_processed_url=_parse_float(metrics.get("seconds_per_processed_url")),
        fetch_failed_count=_parse_int(metrics.get("fetch_failed_count")),
        metrics_available=True,
    )


def build_current_snapshot(
    run_id: str,
    run_number: str,
    digest_date: str,
    status: str,
    processed_urls: str,
    pipeline_seconds: str,
    seconds_per_processed_url: str,
    fetch_failed_count: str,
) -> RunHistorySnapshot:
    return RunHistorySnapshot(
        run_id=int(run_id),
        run_number=int(run_number),
        digest_date=digest_date,
        status=status,
        processed_urls=_parse_int(processed_urls),
        pipeline_seconds=_parse_float(pipeline_seconds),
        seconds_per_processed_url=_parse_float(seconds_per_processed_url),
        fetch_failed_count=_parse_int(fetch_failed_count),
        metrics_available=True,
    )


def fetch_history_snapshots(
    client: GitHubActionsClient,
    workflow_file: str,
    current_run_id: int,
    limit: int,
) -> list[RunHistorySnapshot]:
    if limit <= 0:
        return []

    runs = client.list_workflow_runs(workflow_file=workflow_file, per_page=max(30, limit * 6))
    snapshots: list[RunHistorySnapshot] = []
    for run in runs:
        run_id = int(run.get("id", 0))
        if run_id == current_run_id:
            continue
        if run.get("status") != "completed":
            continue

        run_number = int(run.get("run_number", 0))
        created_at = str(run.get("created_at", ""))
        fallback_date = created_at[:10] if len(created_at) >= 10 else "unknown"
        conclusion = str(run.get("conclusion", "completed"))

        metrics: Optional[dict[str, Any]]
        try:
            logs_zip = client.download_run_logs_zip(run_id=run_id)
            metrics = extract_run_metrics_from_logs_zip(logs_zip)
        except Exception:  # noqa: BLE001
            metrics = None

        snapshots.append(
            _snapshot_from_metrics(
                run_id=run_id,
                run_number=run_number,
                status=conclusion,
                fallback_date=fallback_date,
                metrics=metrics,
            )
        )
        if len(snapshots) >= limit:
            break
    return snapshots


def build_performance_summary(
    snapshots: list[RunHistorySnapshot],
    window_size: int,
) -> PerformanceSummary:
    comparable_snapshots: list[RunHistorySnapshot] = []
    skipped_missing_metrics_count = 0
    skipped_zero_processed_count = 0
    skipped_missing_sec_per_url_count = 0

    for snapshot in snapshots:
        if len(comparable_snapshots) >= window_size:
            break
        if not snapshot.metrics_available:
            skipped_missing_metrics_count += 1
            continue
        if snapshot.processed_urls is None or snapshot.processed_urls <= 0:
            skipped_zero_processed_count += 1
            continue
        if snapshot.seconds_per_processed_url is None:
            skipped_missing_sec_per_url_count += 1
            continue

        comparable_snapshots.append(snapshot)

    rows = [
        PerformanceSummaryRow(
            snapshot=snapshot,
            delta_sec_per_url=(
                None
                if index + 1 >= len(comparable_snapshots)
                else snapshot.seconds_per_processed_url
                - comparable_snapshots[index + 1].seconds_per_processed_url
            ),
        )
        for index, snapshot in enumerate(comparable_snapshots)
    ]

    return PerformanceSummary(
        window_size=window_size,
        rows=rows,
        skipped_missing_metrics_count=skipped_missing_metrics_count,
        skipped_zero_processed_count=skipped_zero_processed_count,
        skipped_missing_sec_per_url_count=skipped_missing_sec_per_url_count,
    )


def render_performance_summary(summary: PerformanceSummary) -> str:
    lines = [
        f"## Performance Summary (Last {summary.window_size} Comparable Runs)",
        "",
        "| Run | Date | Status | Processed | Pipeline (s) | Sec/URL | Fetch failed | Delta Sec/URL |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]

    for row in summary.rows:
        snapshot = row.snapshot
        lines.append(
            "| "
            + f"#{snapshot.run_number} "
            + f"| {snapshot.digest_date} "
            + f"| {snapshot.status} "
            + f"| {_format_optional_int(snapshot.processed_urls)} "
            + f"| {_format_optional_float(snapshot.pipeline_seconds)} "
            + f"| {_format_optional_float(snapshot.seconds_per_processed_url)} "
            + f"| {_format_optional_int(snapshot.fetch_failed_count)} "
            + f"| {_format_optional_delta(row.delta_sec_per_url)} |"
        )

    lines.append("")
    if summary.skipped_run_count > 0:
        lines.append(
            "_Skipped recent runs: "
            + f"{summary.skipped_run_count} total"
            + f" ({summary.skipped_missing_metrics_count} missing metrics,"
            + f" {summary.skipped_zero_processed_count} without processed_urls > 0,"
            + f" {summary.skipped_missing_sec_per_url_count} missing sec/URL)._"
        )
    else:
        lines.append("_All recent runs were comparable._")
    return "\n".join(lines) + "\n"
