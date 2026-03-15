from typing import Literal


CommitMode = Literal["skip", "create", "amend"]


def daily_commit_message(run_date_iso: str) -> str:
    return f"chore(digest): {run_date_iso} daily digest"


def decide_commit_mode(
    processed_urls: int,
    has_staged_changes: bool,
    head_commit_subject: str,
    expected_daily_subject: str,
) -> CommitMode:
    if processed_urls <= 0:
        return "skip"
    if not has_staged_changes:
        return "skip"
    if head_commit_subject == expected_daily_subject:
        return "amend"
    return "create"
