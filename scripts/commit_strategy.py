from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from src.telemetry.pipeline_log_parser import extract_pipeline_outputs
from src.workflow_commit_strategy import daily_commit_message, decide_commit_mode


def _has_staged_changes() -> bool:
    result = subprocess.run(
        ["git", "diff", "--staged", "--quiet"],
        capture_output=True,
    )
    return result.returncode != 0


def _head_commit_subject() -> str:
    result = subprocess.run(
        ["git", "log", "-1", "--format=%s"],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


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
        outputs = extract_pipeline_outputs(log_text)
        processed_urls = int(outputs.get("processed_urls", 0))
        digest_date = outputs.get("digest_date", "unknown")
    except RuntimeError as exc:
        print(f"invalid pipeline log contract: {exc}", file=sys.stderr)
        raise SystemExit(1)
    except (TypeError, ValueError) as exc:
        print(f"invalid pipeline log contract: {exc}", file=sys.stderr)
        raise SystemExit(1)

    expected_subject = daily_commit_message(digest_date)
    mode = decide_commit_mode(
        processed_urls=processed_urls,
        has_staged_changes=_has_staged_changes(),
        head_commit_subject=_head_commit_subject(),
        expected_daily_subject=expected_subject,
    )
    print(mode)


if __name__ == "__main__":
    main()
