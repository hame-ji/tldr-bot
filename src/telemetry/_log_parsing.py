from __future__ import annotations

import json
from typing import Any


def extract_payload(log_text: str, prefix: str) -> dict[str, Any] | None:
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
