from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class RunHistorySnapshot:
    run_id: int
    run_number: int
    digest_date: str
    status: str
    processed_urls: Optional[int]
    pipeline_seconds: Optional[float]
    seconds_per_processed_url: Optional[float]
    fetch_failed_count: Optional[int]
    metrics_available: bool


@dataclass(frozen=True)
class PerformanceSummaryRow:
    snapshot: RunHistorySnapshot
    delta_sec_per_url: Optional[float]


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
