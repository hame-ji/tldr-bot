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

