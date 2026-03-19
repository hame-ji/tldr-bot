from datetime import datetime, timezone
import hashlib
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import parse_qs, urlparse, urlsplit, urlunsplit

import requests
from requests import exceptions as requests_exceptions
from slugify import slugify

try:
    import trafilatura
except ImportError:
    class _TrafilaturaFallback:
        @staticmethod
        def extract(*_args: Any, **_kwargs: Any) -> str:
            raise RuntimeError("trafilatura import failed; install optional html clean dependency")

    trafilatura = _TrafilaturaFallback()

try:
    from pypdf import PdfReader
except ImportError:
    class _PdfReaderFallback:
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            raise RuntimeError("pypdf import failed; install optional pdf dependency")

    PdfReader = _PdfReaderFallback


YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "youtu.be",
    "www.youtu.be",
}

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/136.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

HTTP_BLOCKED = "http_blocked"
TLS_ERROR = "tls_error"
PDF_EXTRACT_FAILED = "pdf_extract_failed"
ARTICLE_EXTRACT_TOO_SHORT = "article_extract_too_short"
NETWORK_ERROR = "network_error"


class FetchProcessingError(RuntimeError):
    def __init__(self, reason: str, message: str) -> None:
        self.reason = reason
        super().__init__(message)


def url_to_slug(url: str, fallback: str = "url") -> str:
    parsed = urlparse(url)
    slug_seed = (parsed.netloc + parsed.path).strip("/") or fallback

    host = (parsed.hostname or "").lower()
    if host in YOUTUBE_HOSTS:
        query = parse_qs(parsed.query)
        if host.endswith("youtu.be"):
            video_id = parsed.path.strip("/")
        else:
            video_id = (query.get("v") or [""])[0]

        if video_id:
            slug_seed = f"{slug_seed}-{video_id}"
        else:
            digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:10]
            slug_seed = f"{slug_seed}-{digest}"

    return slugify(slug_seed)[:80] or fallback


def load_prompt(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        raise RuntimeError("Missing prompt file: " + path) from None


def classify_url(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    if host in YOUTUBE_HOSTS:
        return "youtube"
    return "article"


def normalize_url_for_fetch(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))


def _is_pdf_response(url: str, content_type: str) -> bool:
    parsed = urlparse(url)
    path = parsed.path.lower()
    if path.endswith(".pdf") or "/pdf/" in path:
        return True
    return "application/pdf" in content_type.lower()


def _extract_html_text(html: str) -> str:
    extracted = trafilatura.extract(
        html,
        output_format="txt",
        include_comments=False,
        include_tables=False,
    )

    if not extracted or len(extracted.strip()) < 200:
        raise FetchProcessingError(ARTICLE_EXTRACT_TOO_SHORT, "Extracted article content is empty or too short")

    return extracted.strip()


def _extract_pdf_text(content: bytes) -> str:
    try:
        reader = PdfReader(BytesIO(content))
        pages = [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:  # noqa: BLE001
        raise FetchProcessingError(PDF_EXTRACT_FAILED, "PDF extraction failed: " + str(exc)) from exc

    extracted = "\n\n".join(page.strip() for page in pages if page and page.strip()).strip()
    if len(extracted) < 200:
        raise FetchProcessingError(PDF_EXTRACT_FAILED, "Extracted PDF content is empty or too short")
    return extracted


def fetch_article_text(url: str) -> str:
    normalized_url = normalize_url_for_fetch(url)
    response = requests.get(normalized_url, timeout=(10, 30), headers=REQUEST_HEADERS)
    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "")
    if _is_pdf_response(normalized_url, content_type):
        return _extract_pdf_text(response.content)

    return _extract_html_text(response.text)


def _classify_fetch_error(exc: Exception) -> str:
    explicit_reason = getattr(exc, "reason", None)
    if isinstance(explicit_reason, str) and explicit_reason:
        return explicit_reason

    if isinstance(exc, requests_exceptions.SSLError):
        return TLS_ERROR

    if isinstance(exc, requests_exceptions.HTTPError):
        response = exc.response
        status_code = response.status_code if response is not None else None
        if status_code in {401, 403, 429}:
            return HTTP_BLOCKED
        return NETWORK_ERROR

    if isinstance(exc, requests_exceptions.RequestException):
        return NETWORK_ERROR

    return NETWORK_ERROR


def write_failure_record(
    url: str,
    error: str,
    base_dir: str = "data/failed",
    now: Optional[datetime] = None,
    reason: Optional[str] = None,
) -> Path:
    timestamp = now or datetime.now(timezone.utc)
    day = timestamp.strftime("%Y-%m-%d")
    stamp = timestamp.isoformat()

    slug = url_to_slug(url)

    out_dir = Path(base_dir) / day
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / (slug + ".md")

    lines = [
        "# Fetch Failure",
        "",
        "- URL: " + url,
        "- Timestamp: " + stamp,
    ]
    if reason:
        lines.append("- Reason: " + reason)
    lines.extend(
        [
            "- Error: " + error,
            "",
        ]
    )
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def fetch_url(url: str, failed_base_dir: str = "data/failed") -> Dict[str, Any]:
    kind = classify_url(url)
    if kind == "youtube":
        return {"status": "ok", "kind": "youtube", "url": url}

    try:
        content = fetch_article_text(url)
    except Exception as exc:  # noqa: BLE001
        reason = _classify_fetch_error(exc)
        failure_path = write_failure_record(url=url, error=str(exc), base_dir=failed_base_dir, reason=reason)
        return {
            "status": "failed",
            "kind": "article",
            "url": url,
            "error": str(exc),
            "reason": reason,
            "failure_path": str(failure_path),
        }

    return {"status": "ok", "kind": "article", "url": url, "content": content}


def fetch_urls(urls: Iterable[str], failed_base_dir: str = "data/failed") -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for url in urls:
        results.append(fetch_url(url, failed_base_dir=failed_base_dir))
    return results
