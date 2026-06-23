from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RunHistorySnapshot:
    run_id: int
    run_number: int
    digest_date: str
    status: str
    processed_urls: int | None
    pipeline_seconds: float | None
    seconds_per_processed_url: float | None
    fetch_failed_count: int | None
    metrics_available: bool


@dataclass(frozen=True)
class PerformanceSummaryRow:
    snapshot: RunHistorySnapshot
    delta_sec_per_url: float | None


@dataclass(frozen=True)
class PerformanceSummary:
    window_size: int
    rows: list[PerformanceSummaryRow]
    skipped_missing_metrics_count: int
    skipped_zero_processed_count: int
    skipped_missing_sec_per_url_count: int

    @property
    def skipped_run_count(self) -> int:
        return (
            self.skipped_missing_metrics_count
            + self.skipped_zero_processed_count
            + self.skipped_missing_sec_per_url_count
        )
