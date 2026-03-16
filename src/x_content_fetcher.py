import html
import re
from typing import Any
from urllib.parse import urlparse

import requests


X_HOSTS = {
    "x.com",
    "www.x.com",
    "twitter.com",
    "www.twitter.com",
    "mobile.twitter.com",
    "mobile.x.com",
}

X_CONTENT_UNAVAILABLE = "x_content_unavailable"
X_INTERSTITIAL_DETECTED = "x_interstitial_detected"
X_LOW_SIGNAL_CONTENT = "x_low_signal_content"


class XContentError(RuntimeError):
    def __init__(self, reason: str, message: str = "") -> None:
        self.reason = reason
        final_message = reason if not message else f"{reason}: {message}"
        super().__init__(final_message)


def parse_tweet_id(url: str) -> str | None:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if host not in X_HOSTS:
        return None

    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 3:
        return None

    for index, part in enumerate(parts):
        if part != "status":
            continue
        if index + 1 >= len(parts):
            return None
        candidate = parts[index + 1]
        if candidate.isdigit():
            return candidate
        return None
    return None


def _is_interstitial_text(text: str) -> bool:
    lowered = text.lower()
    signals = (
        "javascript is disabled",
        "enable javascript",
        "javascript is not available",
        "supported browser",
        "log in to x",
        "sign in to x",
        "access denied",
    )
    return any(signal in lowered for signal in signals)


def _is_low_signal_text(text: str) -> bool:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return True

    if _is_interstitial_text(cleaned):
        return False

    if len(cleaned) < 12:
        return True

    without_urls = re.sub(r"https?://\S+", "", cleaned)
    without_urls = re.sub(r"t\.co/\S+", "", without_urls)
    letters = re.findall(r"[A-Za-z0-9]", without_urls)
    return len(letters) < 12


def _validate_text(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        raise XContentError(X_CONTENT_UNAVAILABLE, "empty response")
    if _is_interstitial_text(normalized):
        raise XContentError(X_INTERSTITIAL_DETECTED, "access wall or JS interstitial")
    if _is_low_signal_text(normalized):
        raise XContentError(X_LOW_SIGNAL_CONTENT, "content lacks substantive text")
    return normalized


def _normalize_syndication_payload(payload: dict[str, Any]) -> str:
    candidates: list[str] = []
    for key in ("text", "full_text"):
        value = payload.get(key)
        if isinstance(value, str):
            candidates.append(value)

    user = payload.get("user")
    if isinstance(user, dict):
        screen_name = user.get("screen_name") or user.get("name")
        if isinstance(screen_name, str):
            candidates.append("Author: " + screen_name)

    created_at = payload.get("created_at")
    if isinstance(created_at, str) and created_at.strip():
        candidates.append("Posted: " + created_at.strip())

    return "\n".join(item.strip() for item in candidates if item.strip()).strip()


def _normalize_oembed_payload(payload: dict[str, Any]) -> str:
    pieces: list[str] = []
    author = payload.get("author_name")
    if isinstance(author, str) and author.strip():
        pieces.append("Author: " + author.strip())

    html_block = payload.get("html")
    if isinstance(html_block, str) and html_block.strip():
        match = re.search(r"<p[^>]*>(.*?)</p>", html_block, flags=re.IGNORECASE | re.DOTALL)
        if match:
            inner = match.group(1)
            inner = re.sub(r"<[^>]+>", " ", inner)
            inner = html.unescape(inner)
            pieces.append(re.sub(r"\s+", " ", inner).strip())

    return "\n".join(item for item in pieces if item).strip()


def _fetch_syndication(tweet_id: str, timeout: tuple[int, int]) -> dict[str, Any]:
    try:
        response = requests.get(
            "https://cdn.syndication.twimg.com/tweet-result",
            params={"id": tweet_id, "lang": "en"},
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise XContentError(X_CONTENT_UNAVAILABLE, "syndication_request_failed") from exc
    if response.status_code >= 400:
        raise XContentError(X_CONTENT_UNAVAILABLE, f"syndication_http_{response.status_code}")

    try:
        payload = response.json()
    except ValueError as exc:
        raise XContentError(X_CONTENT_UNAVAILABLE, "syndication_invalid_json") from exc

    if not isinstance(payload, dict):
        raise XContentError(X_CONTENT_UNAVAILABLE, "syndication_invalid_payload")
    return payload


def _fetch_oembed(url: str, timeout: tuple[int, int]) -> dict[str, Any]:
    try:
        response = requests.get(
            "https://publish.twitter.com/oembed",
            params={"url": url},
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise XContentError(X_CONTENT_UNAVAILABLE, "oembed_request_failed") from exc
    if response.status_code >= 400:
        raise XContentError(X_CONTENT_UNAVAILABLE, f"oembed_http_{response.status_code}")

    try:
        payload = response.json()
    except ValueError as exc:
        raise XContentError(X_CONTENT_UNAVAILABLE, "oembed_invalid_json") from exc

    if not isinstance(payload, dict):
        raise XContentError(X_CONTENT_UNAVAILABLE, "oembed_invalid_payload")
    return payload


def fetch_x_text(url: str, timeout: tuple[int, int] = (10, 30)) -> str:
    tweet_id = parse_tweet_id(url)
    if not tweet_id:
        raise XContentError(X_CONTENT_UNAVAILABLE, "tweet_id_missing")

    syndication_error: XContentError | None = None
    try:
        syndication_payload = _fetch_syndication(tweet_id=tweet_id, timeout=timeout)
        syndication_text = _normalize_syndication_payload(syndication_payload)
        return _validate_text(syndication_text)
    except XContentError as exc:
        syndication_error = exc

    try:
        oembed_payload = _fetch_oembed(url=url, timeout=timeout)
        oembed_text = _normalize_oembed_payload(oembed_payload)
        return _validate_text(oembed_text)
    except XContentError as exc:
        fallback_error = exc
        detail = f"syndication={syndication_error}; oembed={fallback_error}"
        if fallback_error.reason in {X_INTERSTITIAL_DETECTED, X_LOW_SIGNAL_CONTENT}:
            raise XContentError(fallback_error.reason, detail) from fallback_error
        raise XContentError(X_CONTENT_UNAVAILABLE, detail) from fallback_error
