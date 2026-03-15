from datetime import datetime, timezone

from content_fetcher import fetch_urls
from summarizer import summarize_items
from telegram_client import poll_urls_from_env


def main() -> None:
    timestamp = datetime.now(timezone.utc).isoformat()
    result = poll_urls_from_env()
    print(f"tldr-bot polling run at {timestamp}")
    print(f"updates={result['update_count']} previous_offset={result['previous_offset']} next_offset={result['next_offset']}")

    fetch_results = fetch_urls(result["urls"])
    for item in fetch_results:
        if item["status"] == "ok":
            print(f"ok:{item['kind']}:{item['url']}")
        else:
            print(f"failed:{item['url']} -> {item['failure_path']}")

    summarized = summarize_items(fetch_results, run_date=datetime.now(timezone.utc).date())
    for item in summarized:
        if item["status"] == "ok":
            print(f"summary:{item['url']} -> {item['summary_path']}")
        else:
            error = item.get("error", "unknown")
            print(f"summary_failed:{item['url']} -> {item['failure_path']} ({error})")


if __name__ == "__main__":
    main()
