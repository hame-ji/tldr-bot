from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class RunMetrics:
    metrics_version: int
    digest_date: str
    processed_urls: int
    summary_ok_count: int
    summary_failed_count: int
    fetch_ok_article_count: int
    fetch_ok_youtube_count: int
    fetch_failed_count: int
    pipeline_seconds: float
    seconds_per_processed_url: Optional[float]


def build_run_metrics(
    digest_date: str,
    fetch_results: list[dict[str, Any]],
    outcome: dict[str, Any],
    pipeline_seconds: float,
) -> RunMetrics:
    fetch_ok_article_count = sum(
        1 for item in fetch_results if item.get("status") == "ok" and item.get("kind") == "article"
    )
    fetch_ok_youtube_count = sum(
        1 for item in fetch_results if item.get("status") == "ok" and item.get("kind") == "youtube"
    )
    fetch_failed_count = sum(1 for item in fetch_results if item.get("status") == "failed")

    processed_urls = int(outcome.get("processed_urls", 0))
    summary_ok_count = int(outcome.get("summary_ok_count", 0))
    summary_failed_count = int(outcome.get("summary_failed_count", 0))

    seconds_per_processed_url: Optional[float]
    if processed_urls > 0:
        seconds_per_processed_url = pipeline_seconds / processed_urls
    else:
        seconds_per_processed_url = None

    return RunMetrics(
        metrics_version=1,
        digest_date=digest_date,
        processed_urls=processed_urls,
        summary_ok_count=summary_ok_count,
        summary_failed_count=summary_failed_count,
        fetch_ok_article_count=fetch_ok_article_count,
        fetch_ok_youtube_count=fetch_ok_youtube_count,
        fetch_failed_count=fetch_failed_count,
        pipeline_seconds=pipeline_seconds,
        seconds_per_processed_url=seconds_per_processed_url,
    )


def to_log_line(metrics: RunMetrics) -> str:
    return "run_metrics:" + json.dumps(asdict(metrics), sort_keys=True)
