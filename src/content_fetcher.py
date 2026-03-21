from __future__ import annotations

from io import BytesIO
from collections.abc import Iterable
from typing import Any
from urllib.parse import urlparse

import requests
from requests import exceptions as requests_exceptions

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

from src._failures import (  # noqa: E402
    ARTICLE_EXTRACT_TOO_SHORT,
    HTTP_BLOCKED,
    NETWORK_ERROR,
    PDF_EXTRACT_FAILED,
    TLS_ERROR,
    write_failure_record,
)
from src._prompts import load_prompt  # noqa: E402
from src._url_utils import (  # noqa: E402
    YOUTUBE_HOSTS,
    classify_url,
    normalize_url_for_fetch,
    url_to_slug,
)

# Re-export for backward compatibility
__all__ = [
    "ARTICLE_EXTRACT_TOO_SHORT",
    "HTTP_BLOCKED",
    "NETWORK_ERROR",
    "PDF_EXTRACT_FAILED",
    "TLS_ERROR",
    "FetchProcessingError",
    "YOUTUBE_HOSTS",
    "classify_url",
    "fetch_article_text",
    "fetch_url",
    "fetch_urls",
    "load_prompt",
    "normalize_url_for_fetch",
    "url_to_slug",
    "write_failure_record",
]

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/136.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


class FetchProcessingError(RuntimeError):
    def __init__(self, reason: str, message: str) -> None:
        self.reason = reason
        super().__init__(message)


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


def fetch_url(url: str, failed_base_dir: str = "data/failed") -> dict[str, Any]:
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


def fetch_urls(urls: Iterable[str], failed_base_dir: str = "data/failed") -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for url in urls:
        results.append(fetch_url(url, failed_base_dir=failed_base_dir))
    return results
