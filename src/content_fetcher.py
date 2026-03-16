from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlparse

import requests
from slugify import slugify

try:
    from x_content_fetcher import X_HOSTS, XContentError, fetch_x_text
except ImportError:
    from src.x_content_fetcher import X_HOSTS, XContentError, fetch_x_text

try:
    import trafilatura
except ImportError:
    class _TrafilaturaFallback:
        @staticmethod
        def extract(*_args: Any, **_kwargs: Any) -> str:
            raise RuntimeError("trafilatura import failed; install optional html clean dependency")

    trafilatura = _TrafilaturaFallback()


def url_to_slug(url: str, fallback: str = "url") -> str:
    parsed = urlparse(url)
    slug_seed = (parsed.netloc + parsed.path).strip("/") or fallback
    return slugify(slug_seed)[:80] or fallback


def load_prompt(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        raise RuntimeError("Missing prompt file: " + path) from None


YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "youtu.be",
    "www.youtu.be",
}



def classify_url(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    if host in YOUTUBE_HOSTS:
        return "youtube"
    if host in X_HOSTS:
        return "x_post"
    return "article"


def fetch_article_text(url: str) -> str:
    response = requests.get(url, timeout=(10, 30))
    response.raise_for_status()

    extracted = trafilatura.extract(
        response.text,
        output_format="txt",
        include_comments=False,
        include_tables=False,
    )

    if not extracted or len(extracted.strip()) < 200:
        raise RuntimeError("Extracted article content is empty or too short")

    return extracted.strip()


def write_failure_record(
    url: str,
    error: str,
    base_dir: str = "data/failed",
    now: Optional[datetime] = None,
) -> Path:
    timestamp = now or datetime.now(timezone.utc)
    day = timestamp.strftime("%Y-%m-%d")
    stamp = timestamp.isoformat()

    slug = url_to_slug(url)

    out_dir = Path(base_dir) / day
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / (slug + ".md")
    out_path.write_text(
        "\n".join(
            [
                "# Fetch Failure",
                "",
                "- URL: " + url,
                "- Timestamp: " + stamp,
                "- Error: " + error,
                "",
            ]
        ),
        encoding="utf-8",
    )
    return out_path


def _fetch_and_record(
    url: str, fetcher: Any, failed_base_dir: str
) -> Dict[str, Any]:
    try:
        content = fetcher(url)
    except Exception as exc:  # noqa: BLE001
        failure_path = write_failure_record(url=url, error=str(exc), base_dir=failed_base_dir)
        return {
            "status": "failed",
            "kind": "article",
            "url": url,
            "error": str(exc),
            "failure_path": str(failure_path),
        }
    return {"status": "ok", "kind": "article", "url": url, "content": content}


def fetch_url(url: str, failed_base_dir: str = "data/failed") -> Dict[str, Any]:
    kind = classify_url(url)
    if kind == "youtube":
        return {"status": "ignored", "kind": "youtube", "url": url}

    if kind == "x_post":
        return _fetch_and_record(url, fetch_x_text, failed_base_dir)

    return _fetch_and_record(url, fetch_article_text, failed_base_dir)


def fetch_urls(urls: Iterable[str], failed_base_dir: str = "data/failed") -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for url in urls:
        results.append(fetch_url(url, failed_base_dir=failed_base_dir))
    return results
