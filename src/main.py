import json
from datetime import datetime, timezone
from typing import Any, Optional

try:
    from content_fetcher import fetch_urls
    from digest_generator import generate_digest
    from summarizer import summarize_items
    from telegram_client import poll_urls_from_env, send_digest_from_env
except Exception:  # noqa: BLE001
    from src.content_fetcher import fetch_urls
    from src.digest_generator import generate_digest
    from src.summarizer import summarize_items
    from src.telegram_client import poll_urls_from_env, send_digest_from_env


def run_pipeline(now: Optional[datetime] = None) -> dict[str, Any]:
    now_utc = now or datetime.now(timezone.utc)
    run_date = now_utc.date()
    timestamp = now_utc.isoformat()
    result = poll_urls_from_env()
    print(f"tldr-bot polling run at {timestamp}")
    print(f"updates={result['update_count']} previous_offset={result['previous_offset']} next_offset={result['next_offset']}")

    if len(result["urls"]) == 0:
        print("no_urls_processed; skipping digest generation and delivery")
        return {
            "processed_urls": 0,
            "summary_ok_count": 0,
            "summary_failed_count": 0,
            "digest_created": False,
            "digest_path": "",
            "digest_sent_chunks": 0,
        }

    fetch_results = fetch_urls(result["urls"])
    for item in fetch_results:
        if item["status"] == "ok":
            print(f"ok:{item['kind']}:{item['url']}")
        elif item["status"] == "ignored":
            print(f"ignored:{item['kind']}:{item['url']}")
        else:
            print(f"failed:{item['url']} -> {item['failure_path']}")

    processable_items = [item for item in fetch_results if item.get("kind") == "article"]
    if len(processable_items) == 0:
        print("no_article_urls_processed; skipping digest generation and delivery")
        return {
            "processed_urls": 0,
            "summary_ok_count": 0,
            "summary_failed_count": 0,
            "digest_created": False,
            "digest_path": "",
            "digest_sent_chunks": 0,
        }

    summarized = summarize_items(fetch_results, run_date=run_date)
    for item in summarized:
        if item["status"] == "ok":
            print(f"summary:{item['url']} -> {item['summary_path']}")
        elif item["status"] == "ignored":
            print(f"summary_ignored:{item['url']}")
        else:
            error = item.get("error", "unknown")
            print(f"summary_failed:{item['url']} -> {item['failure_path']} ({error})")

    digest = generate_digest(summarized, run_date=run_date)
    print(f"digest:{digest['digest_path']}")

    send_responses = send_digest_from_env(digest["digest_text"])
    print(f"digest_sent_chunks:{len(send_responses)}")

    summary_ok_count = len([item for item in summarized if item.get("status") == "ok" and item.get("kind") == "article"])
    summary_failed_count = len(
        [item for item in summarized if item.get("status") == "failed" and item.get("kind") == "article"]
    )
    return {
        "processed_urls": summary_ok_count + summary_failed_count,
        "summary_ok_count": summary_ok_count,
        "summary_failed_count": summary_failed_count,
        "digest_created": True,
        "digest_path": digest["digest_path"],
        "digest_sent_chunks": len(send_responses),
    }


def main() -> None:
    outcome = run_pipeline()
    print("run_outcome:" + json.dumps(outcome, sort_keys=True))


if __name__ == "__main__":
    main()
