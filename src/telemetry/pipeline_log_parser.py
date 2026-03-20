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


def extract_pipeline_outputs(log_text: str) -> dict[str, str]:
    outcome_payload = _extract_payload(log_text, "run_outcome:")
    if outcome_payload is None:
        raise RuntimeError("pipeline did not emit run_outcome")

    metrics_payload = _extract_payload(log_text, "run_metrics:")

    processed_urls = int(
        (metrics_payload or {}).get("processed_urls", outcome_payload.get("processed_urls", 0))
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
            }
        )
        return outputs

    outputs["digest_date"] = str(metrics_payload.get("digest_date", "unknown"))
    outputs["pipeline_seconds"] = _as_output_float(metrics_payload.get("pipeline_seconds"))
    seconds_per_processed = metrics_payload.get("seconds_per_processed_url")
    outputs["seconds_per_processed_url"] = (
        "n/a" if seconds_per_processed is None else _as_output_float(seconds_per_processed)
    )
    outputs["fetch_ok_article_count"] = str(int(metrics_payload.get("fetch_ok_article_count", 0)))
    outputs["fetch_ok_youtube_count"] = str(int(metrics_payload.get("fetch_ok_youtube_count", 0)))
    outputs["fetch_failed_count"] = str(int(metrics_payload.get("fetch_failed_count", 0)))
    return outputs
