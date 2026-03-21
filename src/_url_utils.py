import hashlib
from urllib.parse import parse_qs, urlparse, urlsplit, urlunsplit

from slugify import slugify

YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "youtu.be",
    "www.youtu.be",
}


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


def classify_url(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    if host in YOUTUBE_HOSTS:
        return "youtube"
    return "article"


def normalize_url_for_fetch(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))
