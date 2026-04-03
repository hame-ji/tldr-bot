from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any

from src._types import PipelineOutcome
from src.content_fetcher import fetch_urls
from src.digest_generator import generate_digest
from src.summarizer import summarize_items
from src.telegram_client import poll_urls_from_env, send_digest_from_env
from src.telemetry.run_metrics import build_run_metrics, to_log_line

_SUMMARIZABLE_KINDS = {"article", "youtube"}


def _empty_outcome(**overrides: Any) -> PipelineOutcome:
    base: PipelineOutcome = {
        "processed_urls": 0,
        "summary_ok_count": 0,
        "summary_failed_count": 0,
        "youtube_auth_failure_count": 0,
        "notebooklm_auth_failure_count": 0,
        "notebooklm_work_item_count": 0,
        "notebooklm_preflight_status": "skipped",
        "notebooklm_circuit_breaker_skipped_count": 0,
        "replay_queued_count": 0,
        "digest_created": False,
        "digest_path": "",
        "digest_sent_chunks": 0,
    }
    base.update(overrides)  # type: ignore[typeddict-item]
    return base


def _run_pipeline_with_context(
    now: datetime | None = None,
) -> tuple[PipelineOutcome, list[dict[str, Any]], float, str]:
    pipeline_start = time.monotonic()
    now_utc = now or datetime.now(timezone.utc)
    run_date = now_utc.date()
    timestamp = now_utc.isoformat()
    fetch_results: list[dict[str, Any]] = []

    result = poll_urls_from_env()
    print(f"tldr-bot polling run at {timestamp}")
    print(
        f"updates={result['update_count']} previous_offset={result['previous_offset']} next_offset={result['next_offset']}"
    )

    if len(result["urls"]) == 0:
        print("no_urls_processed; skipping digest generation and delivery")
        return (
            _empty_outcome(),
            fetch_results,
            time.monotonic() - pipeline_start,
            run_date.isoformat(),
        )

    fetch_results = fetch_urls(result["urls"])
    for item in fetch_results:
        if item["status"] == "ok":
            print(f"ok:{item['kind']}:{item['url']}")
        elif item["status"] == "ignored":
            print(f"ignored:{item['kind']}:{item['url']}")
        else:
            print(f"failed:{item['url']} -> {item['failure_path']}")

    processable_items = [
        item for item in fetch_results if item.get("kind") in _SUMMARIZABLE_KINDS
    ]
    if len(processable_items) == 0:
        print("no_summarizable_urls_processed; skipping digest generation and delivery")
        return (
            _empty_outcome(),
            fetch_results,
            time.monotonic() - pipeline_start,
            run_date.isoformat(),
        )

    summarizer_diagnostics: dict[str, Any] = {}
    summarized = summarize_items(
        fetch_results,
        run_date=run_date,
        diagnostics=summarizer_diagnostics,
    )
    for item in summarized:
        if item["status"] == "ok":
            print(f"summary:{item['kind']}:{item['url']} -> {item['summary_path']}")
        elif item["status"] == "ignored":
            print(f"summary_ignored:{item['kind']}:{item['url']}")
        else:
            error = item.get("error", "unknown")
            print(
                f"summary_failed:{item['kind']}:{item['url']} -> {item['failure_path']} ({error})"
            )

    digest = generate_digest(summarized, run_date=run_date)
    print(f"digest:{digest['digest_path']}")

    send_responses = send_digest_from_env(digest["digest_text"])
    print(f"digest_sent_chunks:{len(send_responses)}")

    summary_ok_count = int(summarizer_diagnostics.get("summary_ok_count", 0))
    summary_failed_count = int(summarizer_diagnostics.get("summary_failed_count", 0))
    youtube_auth_failure_count = int(
        summarizer_diagnostics.get("youtube_auth_failure_count", 0)
    )
    notebooklm_auth_failure_count = int(
        summarizer_diagnostics.get("notebooklm_auth_failure_count", 0)
    )
    notebooklm_work_item_count = int(
        summarizer_diagnostics.get("notebooklm_work_item_count", 0)
    )
    notebooklm_preflight_status = str(
        summarizer_diagnostics.get("notebooklm_preflight_status", "skipped")
    )
    notebooklm_circuit_breaker_skipped_count = int(
        summarizer_diagnostics.get("notebooklm_circuit_breaker_skipped_count", 0)
    )
    replay_queued_count = int(summarizer_diagnostics.get("replay_queued_count", 0))
    outcome = _empty_outcome(
        processed_urls=summary_ok_count + summary_failed_count,
        summary_ok_count=summary_ok_count,
        summary_failed_count=summary_failed_count,
        youtube_auth_failure_count=youtube_auth_failure_count,
        notebooklm_auth_failure_count=notebooklm_auth_failure_count,
        notebooklm_work_item_count=notebooklm_work_item_count,
        notebooklm_preflight_status=notebooklm_preflight_status,
        notebooklm_circuit_breaker_skipped_count=notebooklm_circuit_breaker_skipped_count,
        replay_queued_count=replay_queued_count,
        digest_created=True,
        digest_path=digest["digest_path"],
        digest_sent_chunks=len(send_responses),
    )
    return (
        outcome,
        fetch_results,
        time.monotonic() - pipeline_start,
        run_date.isoformat(),
    )


def run_pipeline(now: datetime | None = None) -> PipelineOutcome:
    outcome, _, _, _ = _run_pipeline_with_context(now=now)
    return outcome


def main() -> None:
    outcome, fetch_results, pipeline_seconds, digest_date = _run_pipeline_with_context()
    metrics = build_run_metrics(
        digest_date=digest_date,
        fetch_results=fetch_results,
        outcome=outcome,
        pipeline_seconds=pipeline_seconds,
    )
    print("run_outcome:" + json.dumps(outcome, sort_keys=True))
    print(to_log_line(metrics))


if __name__ == "__main__":
    main()
