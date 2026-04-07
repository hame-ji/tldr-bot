from __future__ import annotations

import argparse
import json
import logging
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from src._config import notebooklm_config_from_env
from src._prompts import load_prompt
from src.summarization.common import _source_output_path
from src.summarization.notebooklm_backend import summarize_url, summarize_youtube
from src.summarization.replay_queue import (
    append_completed_record,
    load_pending_records,
    rewrite_pending_file,
)

LOGGER = logging.getLogger(__name__)


def _replay_one(record: dict[str, Any]) -> str:
    config = notebooklm_config_from_env()
    kind = str(record.get("kind", ""))
    url = str(record.get("url", ""))
    if kind == "youtube":
        prompt = load_prompt(config.youtube_prompt_path)
        return summarize_youtube(url=url, prompt=prompt)
    prompt = load_prompt(config.article_fallback_prompt_path)
    return summarize_url(url=url, prompt=prompt)


def run_replay(
    *,
    limit: int,
    base_dir: str = "data/replay/notebooklm",
    sources_base_dir: str = "data/sources",
) -> dict[str, int]:
    grouped = load_pending_records(base_dir=base_dir)
    attempted = 0
    recovered = 0

    for pending_path, records in grouped.items():
        try:
            pending_date = date.fromisoformat(pending_path.stem)
        except ValueError:
            LOGGER.warning("Skipping malformed replay queue file: %s", pending_path)
            continue
        remaining: list[dict[str, Any]] = []
        completed_records: list[dict[str, Any]] = []
        for record in records:
            if limit > 0 and attempted >= limit:
                remaining.append(record)
                continue

            attempted += 1
            try:
                summary = _replay_one(record)
            except Exception as exc:  # noqa: BLE001
                next_record = dict(record)
                next_record["attempt_count"] = (
                    int(next_record.get("attempt_count", 0)) + 1
                )
                next_record["last_error"] = str(exc)
                next_record["last_attempt_at"] = datetime.now(timezone.utc).isoformat()
                remaining.append(next_record)
                continue

            try:
                out_path = _source_output_path(
                    url=str(record.get("url", "")),
                    run_date=pending_date,
                    base_dir=sources_base_dir,
                )
                out_path.write_text(summary + "\n", encoding="utf-8")
            except Exception as exc:  # noqa: BLE001
                next_record = dict(record)
                next_record["attempt_count"] = (
                    int(next_record.get("attempt_count", 0)) + 1
                )
                next_record["last_error"] = str(exc)
                next_record["last_attempt_at"] = datetime.now(timezone.utc).isoformat()
                remaining.append(next_record)
                continue

            completed_records.append(record)
            recovered += 1

        rewrite_pending_file(pending_path, remaining)
        for record in completed_records:
            append_completed_record(record, base_dir=base_dir)

    pending_remaining = sum(
        len(records) for records in load_pending_records(base_dir=base_dir).values()
    )
    return {
        "replay_attempted_count": attempted,
        "replay_recovered_count": recovered,
        "replay_pending_remaining_count": pending_remaining,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay NotebookLM auth failure queue")
    parser.add_argument(
        "--limit", type=int, default=0, help="Max replay attempts (0 = no limit)"
    )
    parser.add_argument("--base-dir", default="data/replay/notebooklm")
    parser.add_argument("--sources-base-dir", default="data/sources")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    summary = run_replay(
        limit=args.limit,
        base_dir=args.base_dir,
        sources_base_dir=args.sources_base_dir,
    )
    print("replay_outcome:" + json.dumps(summary, sort_keys=True))
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with Path(output_path).open("a", encoding="utf-8") as handle:
            for key, value in summary.items():
                handle.write(f"{key}={value}\n")


if __name__ == "__main__":
    main()
