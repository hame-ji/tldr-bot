from __future__ import annotations

import json
import sys
from typing import Any
from pathlib import Path


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


def main() -> None:
    log_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/pipeline.log")
    try:
        log_text = log_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"pipeline log not found: {log_path}", file=sys.stderr)
        raise SystemExit(1)
    except OSError as exc:
        print(f"failed to read pipeline log: {exc}", file=sys.stderr)
        raise SystemExit(1)

    try:
        outcome_payload = _extract_payload(log_text, "run_outcome:")
        if outcome_payload is None:
            raise RuntimeError("pipeline did not emit run_outcome")
        processed_urls = int(outcome_payload.get("processed_urls", 0))
    except RuntimeError as exc:
        print(f"invalid pipeline log contract: {exc}", file=sys.stderr)
        raise SystemExit(1)
    except (TypeError, ValueError) as exc:
        print(f"invalid pipeline log contract: invalid processed_urls in run_outcome ({exc})", file=sys.stderr)
        raise SystemExit(1)
    except Exception as exc:  # noqa: BLE001
        print(f"failed to parse pipeline log: {exc.__class__.__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)

    print(processed_urls)


if __name__ == "__main__":
    main()
