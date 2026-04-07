from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

AUTH_FAILURE_REASONS = {
    "youtube_auth_expired",
    "notebooklm_auth_expired",
}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            records.append(payload)
    return records


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not records:
        path.unlink(missing_ok=True)
        return
    lines = [json.dumps(record, sort_keys=True) for record in records]
    content = "\n".join(lines) + "\n"
    with NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        prefix=path.name + ".",
        suffix=".tmp",
        delete=False,
    ) as handle:
        handle.write(content)
        temp_path = Path(handle.name)
    temp_path.replace(path)


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def _pending_path(run_date: date, base_dir: str) -> Path:
    return Path(base_dir) / "pending" / f"{run_date.isoformat()}.jsonl"


def _completed_path(base_dir: str) -> Path:
    today = datetime.now(timezone.utc).date().isoformat()
    return Path(base_dir) / "completed" / f"{today}.jsonl"


def enqueue_notebooklm_auth_failure(
    *,
    run_date: date,
    url: str,
    kind: str,
    reason: str,
    source_failure_path: str,
    base_dir: str = "data/replay/notebooklm",
) -> bool:
    if reason not in AUTH_FAILURE_REASONS:
        return False
    if kind not in {"article", "youtube"}:
        return False

    pending_path = _pending_path(run_date=run_date, base_dir=base_dir)
    existing = _read_jsonl(pending_path)
    for record in existing:
        if record.get("url") == url and record.get("kind") == kind:
            return False

    now_iso = datetime.now(timezone.utc).isoformat()
    record = {
        "url": url,
        "kind": kind,
        "reason": reason,
        "first_failed_at": now_iso,
        "last_attempt_at": now_iso,
        "attempt_count": 0,
        "source_failure_path": source_failure_path,
    }
    _append_jsonl(pending_path, record)
    return True


def load_pending_records(
    *,
    base_dir: str = "data/replay/notebooklm",
) -> dict[Path, list[dict[str, Any]]]:
    pending_dir = Path(base_dir) / "pending"
    if not pending_dir.exists():
        return {}
    grouped: dict[Path, list[dict[str, Any]]] = {}
    for path in sorted(pending_dir.glob("*.jsonl")):
        grouped[path] = _read_jsonl(path)
    return grouped


def rewrite_pending_file(path: Path, records: list[dict[str, Any]]) -> None:
    _write_jsonl(path, records)


def append_completed_record(
    record: dict[str, Any],
    *,
    base_dir: str = "data/replay/notebooklm",
) -> None:
    completed = dict(record)
    completed["recovered_at"] = datetime.now(timezone.utc).isoformat()
    _append_jsonl(_completed_path(base_dir), completed)
