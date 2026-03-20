from __future__ import annotations

import io
import json
import zipfile
from typing import Any, Optional


def extract_run_metrics_from_log_text(log_text: str) -> Optional[dict[str, Any]]:
    payload: Optional[dict[str, Any]] = None
    for line in log_text.splitlines():
        if "run_metrics:" not in line:
            continue
        raw = line.split("run_metrics:", 1)[1].strip()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
    return payload


def extract_run_metrics_from_logs_zip(logs_zip_bytes: bytes) -> Optional[dict[str, Any]]:
    with zipfile.ZipFile(io.BytesIO(logs_zip_bytes)) as archive:
        for name in archive.namelist():
            if not name.endswith(".txt"):
                continue
            text = archive.read(name).decode("utf-8", errors="replace")
            payload = extract_run_metrics_from_log_text(text)
            if payload is not None:
                return payload
    return None

