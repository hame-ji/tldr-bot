from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from src._url_utils import url_to_slug

HTTP_BLOCKED = "http_blocked"
TLS_ERROR = "tls_error"
PDF_EXTRACT_FAILED = "pdf_extract_failed"
ARTICLE_EXTRACT_TOO_SHORT = "article_extract_too_short"
NETWORK_ERROR = "network_error"


def write_failure_record(
    url: str,
    error: str,
    base_dir: str = "data/failed",
    now: datetime | None = None,
    reason: str | None = None,
) -> Path:
    timestamp = now or datetime.now(timezone.utc)
    day = timestamp.strftime("%Y-%m-%d")
    stamp = timestamp.isoformat()

    slug = url_to_slug(url)

    out_dir = Path(base_dir) / day
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / (slug + ".md")

    lines = [
        "# Fetch Failure",
        "",
        "- URL: " + url,
        "- Timestamp: " + stamp,
    ]
    if reason:
        lines.append("- Reason: " + reason)
    lines.extend(
        [
            "- Error: " + error,
            "",
        ]
    )
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path
