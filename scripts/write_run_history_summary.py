from __future__ import annotations

import os

from src.telemetry.run_history.github_client import GitHubActionsClient
from src.telemetry.run_history.report import (
    build_current_snapshot,
    fetch_history_snapshots,
    render_performance_summary,
)


def main() -> None:
    window_size = 7
    summary_path = os.environ["GITHUB_STEP_SUMMARY"]
    current_snapshot = build_current_snapshot(
        run_id=os.environ["GITHUB_RUN_ID"],
        run_number=os.environ["GITHUB_RUN_NUMBER"],
        digest_date=os.environ.get("DIGEST_DATE", "unknown"),
        status=os.environ.get("PIPELINE_RESULT", "unknown"),
        processed_urls=os.environ.get("PROCESSED_URLS", "unknown"),
        pipeline_seconds=os.environ.get("PIPELINE_SECONDS", "unknown"),
        seconds_per_processed_url=os.environ.get("SECONDS_PER_PROCESSED_URL", "unknown"),
        fetch_failed_count=os.environ.get("FETCH_FAILED_COUNT", "unknown"),
    )

    history = []
    warning = None
    try:
        client = GitHubActionsClient(
            repo=os.environ["GITHUB_REPOSITORY"],
            token=os.environ.get("GITHUB_TOKEN"),
        )
        history = fetch_history_snapshots(
            client=client,
            workflow_file="digest.yml",
            current_run_id=current_snapshot.run_id,
            limit=max(0, window_size - 1),
        )
    except Exception as exc:  # noqa: BLE001
        warning = f"_Run history unavailable ({exc.__class__.__name__}): {exc}_"

    report = render_performance_summary(
        snapshots=[current_snapshot, *history][:window_size],
        window_size=window_size,
    )
    with open(summary_path, "a", encoding="utf-8") as file:
        file.write("\n")
        file.write(report)
        if warning is not None:
            file.write("\n")
            file.write(warning + "\n")


if __name__ == "__main__":
    main()
