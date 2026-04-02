from __future__ import annotations

from typing import TypedDict


class FetchResult(TypedDict, total=False):
    status: str  # "ok" | "failed" | "ignored"
    kind: str  # "article" | "youtube" | "unknown"
    url: str
    content: str  # present when status="ok" and kind="article"
    error: str  # present when status="failed"
    reason: str  # present when status="failed"
    failure_path: str  # present when status="failed"


class SummaryResult(TypedDict, total=False):
    status: str  # "ok" | "failed" | "ignored"
    kind: str
    url: str
    summary_path: str  # present when status="ok"
    error: str  # present when status="failed"
    failure_path: str  # present when status="failed"
    reason: str  # present when status="failed"


class DigestResult(TypedDict):
    digest_path: str
    digest_text: str


class PollResult(TypedDict):
    urls: list[str]
    update_count: int
    previous_offset: int | None
    next_offset: int | None


class PipelineOutcome(TypedDict):
    processed_urls: int
    summary_ok_count: int
    summary_failed_count: int
    youtube_auth_failure_count: int
    notebooklm_auth_failure_count: int
    notebooklm_work_item_count: int
    notebooklm_preflight_status: str
    notebooklm_circuit_breaker_skipped_count: int
    replay_queued_count: int
    digest_created: bool
    digest_path: str
    digest_sent_chunks: int
