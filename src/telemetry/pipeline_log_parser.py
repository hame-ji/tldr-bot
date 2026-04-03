from __future__ import annotations

import json
from typing import Any


def _extract_payload(log_text: str, prefix: str) -> dict[str, Any] | None:
    payload_line = None
    for line in log_text.splitlines():
        if line.startswith(prefix):
            payload_line = line

    if payload_line is None:
        return None

    raw_payload = payload_line.split(prefix, 1)[1].strip()
    try:
        return json.loads(raw_payload)
    except json.JSONDecodeError:
        return None


def _as_output_float(value: Any) -> str:
    try:
        return f"{float(value):.3f}"
    except (TypeError, ValueError):
        return "unknown"


def _as_output_int(value: Any) -> str:
    try:
        return str(int(value))
    except (TypeError, ValueError):
        return "unknown"


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def extract_pipeline_outputs(log_text: str) -> dict[str, str]:
    outcome_payload = _extract_payload(log_text, "run_outcome:")
    if outcome_payload is None:
        raise RuntimeError("pipeline did not emit run_outcome")

    metrics_payload = _extract_payload(log_text, "run_metrics:")

    processed_urls = int(
        (metrics_payload or {}).get(
            "processed_urls", outcome_payload.get("processed_urls", 0)
        )
    )
    digest_created = bool(outcome_payload.get("digest_created", False))

    outputs: dict[str, str] = {
        "processed_urls": str(processed_urls),
        "digest_created": str(digest_created).lower(),
        "digest_date": "unknown",
    }

    if metrics_payload is None:
        outputs.update(
            {
                "pipeline_seconds": "unknown",
                "seconds_per_processed_url": "unknown",
                "fetch_ok_article_count": "unknown",
                "fetch_ok_youtube_count": "unknown",
                "fetch_failed_count": "unknown",
                "notebooklm_preflight_status": "unknown",
                "notebooklm_auth_failure_count": "unknown",
                "notebooklm_auth_incident": "unknown",
                "notebooklm_circuit_breaker_skipped_count": "unknown",
                "replay_queued_count": "unknown",
            }
        )
        return outputs

    outputs["digest_date"] = str(metrics_payload.get("digest_date", "unknown"))
    outputs["pipeline_seconds"] = _as_output_float(
        metrics_payload.get("pipeline_seconds")
    )
    seconds_per_processed = metrics_payload.get("seconds_per_processed_url")
    outputs["seconds_per_processed_url"] = (
        "n/a"
        if seconds_per_processed is None
        else _as_output_float(seconds_per_processed)
    )
    outputs["fetch_ok_article_count"] = _as_output_int(
        metrics_payload.get("fetch_ok_article_count")
    )
    outputs["fetch_ok_youtube_count"] = _as_output_int(
        metrics_payload.get("fetch_ok_youtube_count")
    )
    outputs["fetch_failed_count"] = _as_output_int(
        metrics_payload.get("fetch_failed_count")
    )
    notebooklm_preflight_status = str(
        metrics_payload.get("notebooklm_preflight_status", "unknown")
    )
    notebooklm_auth_failure_count = _as_int(
        metrics_payload.get("notebooklm_auth_failure_count"),
        default=0,
    )
    outputs["notebooklm_preflight_status"] = notebooklm_preflight_status
    outputs["notebooklm_auth_failure_count"] = str(notebooklm_auth_failure_count)
    outputs["notebooklm_circuit_breaker_skipped_count"] = _as_output_int(
        metrics_payload.get("notebooklm_circuit_breaker_skipped_count")
    )
    outputs["replay_queued_count"] = _as_output_int(
        metrics_payload.get("replay_queued_count")
    )
    notebooklm_auth_incident = (
        notebooklm_preflight_status
        in {
            "auth_expired",
            "misconfigured",
        }
        or notebooklm_auth_failure_count > 0
    )
    outputs["notebooklm_auth_incident"] = str(notebooklm_auth_incident).lower()
    return outputs
