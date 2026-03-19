from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional, Protocol

try:
    from content_fetcher import url_to_slug, write_failure_record
except ImportError:
    from src.content_fetcher import url_to_slug, write_failure_record


class Summarizer(Protocol):
    def summarize_article(self, url: str, content: str) -> str:
        ...

    def summarize_article_from_url(self, url: str) -> str:
        ...

    def summarize_youtube(self, url: str) -> str:
        ...


def _source_output_path(url: str, run_date: date, base_dir: str = "data/sources") -> Path:
    slug = url_to_slug(url, fallback="source")
    day = run_date.isoformat()
    out_dir = Path(base_dir) / day
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / (slug + ".md")


def _run_summarize(
    url: str,
    kind: str,
    summarize_fn,
    run_date: date,
    sources_base_dir: str,
    failed_base_dir: str,
    fallback_reason: Optional[str] = None,
) -> Dict[str, Any]:
    try:
        summary = summarize_fn()
    except Exception as exc:  # noqa: BLE001
        reason = getattr(exc, "reason", fallback_reason)
        failure = write_failure_record(url=url, error=str(exc), base_dir=failed_base_dir, reason=reason)
        result: Dict[str, Any] = {
            "status": "failed",
            "kind": kind,
            "url": url,
            "error": str(exc),
            "failure_path": str(failure),
        }
        if reason:
            result["reason"] = reason
        return result

    output_path = _source_output_path(url=url, run_date=run_date, base_dir=sources_base_dir)
    output_path.write_text(summary + "\n", encoding="utf-8")
    return {
        "status": "ok",
        "kind": kind,
        "url": url,
        "summary_path": str(output_path),
    }


def summarize_item(
    item: Dict[str, Any],
    summarizer: Summarizer,
    run_date: date,
    sources_base_dir: str = "data/sources",
    failed_base_dir: str = "data/failed",
) -> Dict[str, Any]:
    if item.get("status") != "ok":
        return item

    kind = item.get("kind")
    if kind not in {"article", "youtube"}:
        return {"status": "ignored", "kind": item.get("kind", "unknown"), "url": item.get("url", "")}

    url = item["url"]
    if kind == "article":
        fn = lambda: summarizer.summarize_article(url=url, content=item["content"])
    else:
        fn = lambda: summarizer.summarize_youtube(url=url)

    return _run_summarize(
        url=url, kind=kind, summarize_fn=fn,
        run_date=run_date, sources_base_dir=sources_base_dir, failed_base_dir=failed_base_dir,
    )


def summarize_failed_article_item(
    item: Dict[str, Any],
    summarizer: Summarizer,
    run_date: date,
    sources_base_dir: str = "data/sources",
    failed_base_dir: str = "data/failed",
) -> Dict[str, Any]:
    url = item.get("url", "")
    return _run_summarize(
        url=url, kind="article",
        summarize_fn=lambda: summarizer.summarize_article_from_url(url=url),
        run_date=run_date, sources_base_dir=sources_base_dir, failed_base_dir=failed_base_dir,
        fallback_reason=item.get("reason"),
    )


def _clamp_concurrency(raw: str, default: int, max_allowed: int) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = default
    return max(1, min(value, max_allowed))


def _timeout_result(
    item: Dict[str, Any],
    failed_base_dir: str,
    timeout_seconds: int,
) -> Dict[str, Any]:
    kind = item.get("kind", "unknown")
    url = item.get("url", "")
    error = f"Summarization timed out after {timeout_seconds} seconds"
    failure = write_failure_record(
        url=url,
        error=error,
        base_dir=failed_base_dir,
        reason="summarization_timeout",
    )
    return {
        "status": "failed",
        "kind": kind,
        "url": url,
        "error": error,
        "failure_path": str(failure),
        "reason": "summarization_timeout",
    }
