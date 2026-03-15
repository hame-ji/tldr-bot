import json
import os
import random
import re
import time
from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional, Protocol
from urllib.parse import parse_qs, urlparse

import requests
from slugify import slugify
from youtube_transcript_api import YouTubeTranscriptApi

try:
    from content_fetcher import write_failure_record
except Exception:  # noqa: BLE001
    from src.content_fetcher import write_failure_record


class _RetryingSummarizerBase:
    def __init__(
        self,
        prompt_path: str,
        min_spacing_seconds: float,
        max_retries: int,
        initial_backoff_seconds: float,
        max_backoff_seconds: float,
    ) -> None:
        self.prompt_path = prompt_path
        self.min_spacing_seconds = min_spacing_seconds
        self.max_retries = max_retries
        self.initial_backoff_seconds = initial_backoff_seconds
        self.max_backoff_seconds = max_backoff_seconds
        self._last_request_at = 0.0

    def _wait_for_min_spacing(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        wait_seconds = self.min_spacing_seconds - elapsed
        if wait_seconds > 0:
            time.sleep(wait_seconds)

    def _is_rate_limited(self, error: Exception) -> bool:
        text = str(error).lower()
        return "429" in text or "rate" in text and "limit" in text

    def _extract_retry_after(self, error: Exception) -> Optional[float]:
        text = str(error)

        retry_after_match = re.search(r"retry[-_ ]after\s*[:=]\s*(\d+)", text, flags=re.IGNORECASE)
        if retry_after_match:
            return float(retry_after_match.group(1))

        seconds_match = re.search(r"retry_delay\D+seconds\D+(\d+)", text, flags=re.IGNORECASE)
        if seconds_match:
            return float(seconds_match.group(1))

        return None

    def _compute_backoff_seconds(self, attempt: int, error: Exception) -> float:
        retry_after = self._extract_retry_after(error)
        if retry_after is not None:
            return min(retry_after, self.max_backoff_seconds)

        exp = self.initial_backoff_seconds * (2 ** attempt)
        jitter = random.uniform(0.0, 1.0)
        return min(exp + jitter, self.max_backoff_seconds)

    def _load_prompt(self) -> str:
        path = Path(self.prompt_path)
        if not path.exists():
            raise RuntimeError("Missing summarize prompt file: " + self.prompt_path)
        return path.read_text(encoding="utf-8").strip()

    def _generate_once(self, prompt: str, contents: list[str]) -> str:
        raise NotImplementedError

    def _generate_with_retry(self, contents: list[str], error_prefix: str) -> str:
        prompt = self._load_prompt()
        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries):
            try:
                self._wait_for_min_spacing()
                text = self._generate_once(prompt=prompt, contents=contents)
                self._last_request_at = time.monotonic()
                if not text:
                    raise RuntimeError("Response contained no text")
                return text.strip()
            except Exception as exc:  # noqa: BLE001
                self._last_request_at = time.monotonic()
                last_error = exc
                if not self._is_rate_limited(exc):
                    break
                if attempt == self.max_retries - 1:
                    break
                time.sleep(self._compute_backoff_seconds(attempt=attempt, error=exc))

        if last_error is None:
            raise RuntimeError(error_prefix + ": unknown error")
        raise RuntimeError(error_prefix + ": " + str(last_error)) from last_error


def _is_zero_price(value: Any) -> bool:
    if value is None:
        return False
    try:
        return float(str(value).strip()) == 0.0
    except ValueError:
        return False


def _is_free_openrouter_model(model: dict[str, Any]) -> bool:
    model_id = model.get("id")
    if isinstance(model_id, str) and model_id.endswith(":free"):
        return True

    pricing = model.get("pricing")
    if not isinstance(pricing, dict):
        return False

    prompt_price = pricing.get("prompt")
    completion_price = pricing.get("completion")
    return _is_zero_price(prompt_price) and _is_zero_price(completion_price)


def _model_quality_score(model_id: str, context_length: int) -> tuple[int, int]:
    text = model_id.lower()
    heuristic = 0
    if "gemini" in text:
        heuristic += 5
    if "qwen" in text:
        heuristic += 4
    if "deepseek" in text:
        heuristic += 4
    if "llama" in text:
        heuristic += 3
    if "instruct" in text:
        heuristic += 2
    return (heuristic, context_length)


def _order_models(models: list[dict[str, Any]], preferred_models: list[str]) -> list[str]:
    free_models: list[tuple[tuple[int, int], str]] = []
    for model in models:
        model_id = model.get("id")
        if not isinstance(model_id, str):
            continue
        if not _is_free_openrouter_model(model):
            continue

        context_length_raw = model.get("context_length", 0)
        try:
            context_length = int(context_length_raw)
        except (TypeError, ValueError):
            context_length = 0

        free_models.append((_model_quality_score(model_id, context_length), model_id))

    if not free_models:
        return []

    free_model_ids = {model_id for _, model_id in free_models}
    ordered: list[str] = []
    for preferred in preferred_models:
        if preferred in free_model_ids and preferred not in ordered:
            ordered.append(preferred)

    for _, model_id in sorted(free_models, key=lambda item: item[0], reverse=True):
        if model_id not in ordered:
            ordered.append(model_id)

    return ordered


def _load_cached_models(cache_path: str, ttl_seconds: int) -> list[str]:
    path = Path(cache_path)
    if not path.exists():
        return []

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []

    if not isinstance(payload, dict):
        return []

    fetched_at = payload.get("fetched_at")
    models = payload.get("models")
    if not isinstance(fetched_at, (int, float)):
        return []
    if not isinstance(models, list) or not all(isinstance(item, str) for item in models):
        return []

    if time.time() - float(fetched_at) > ttl_seconds:
        return []

    return models


def _save_cached_models(cache_path: str, models: list[str]) -> None:
    path = Path(cache_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "fetched_at": time.time(),
        "models": models,
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _extract_openrouter_text(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or len(choices) == 0:
        return ""

    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        return ""

    message = first_choice.get("message")
    if not isinstance(message, dict):
        return ""

    content = message.get("content")
    if not isinstance(content, str):
        return ""
    return content.strip()


class OpenRouterSummarizer(_RetryingSummarizerBase):
    def __init__(
        self,
        api_key: str,
        prompt_path: str = "prompts/summarize.txt",
        base_url: str = "https://openrouter.ai/api/v1",
        preferred_models: Optional[list[str]] = None,
        models_cache_path: str = "data/cache/openrouter_models.json",
        models_cache_ttl_seconds: int = 21600,
        min_spacing_seconds: float = 1.0,
        max_retries: int = 6,
        initial_backoff_seconds: float = 5.0,
        max_backoff_seconds: float = 120.0,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.preferred_models = preferred_models or []
        self.models_cache_path = models_cache_path
        self.models_cache_ttl_seconds = models_cache_ttl_seconds
        self._ordered_models: Optional[list[str]] = None
        super().__init__(
            prompt_path=prompt_path,
            min_spacing_seconds=min_spacing_seconds,
            max_retries=max_retries,
            initial_backoff_seconds=initial_backoff_seconds,
            max_backoff_seconds=max_backoff_seconds,
        )

    def _discover_free_models(self) -> list[str]:
        cached_models = _load_cached_models(self.models_cache_path, self.models_cache_ttl_seconds)
        if cached_models:
            return cached_models

        response = requests.get(
            self.base_url + "/models",
            headers={"Authorization": "Bearer " + self.api_key},
            timeout=(10, 30),
        )
        if response.status_code >= 400:
            raise RuntimeError(f"OpenRouter model discovery failed ({response.status_code}): {response.text[:300]}")

        try:
            payload = response.json()
        except ValueError as exc:
            raise RuntimeError("OpenRouter model discovery returned invalid JSON") from exc

        model_objects = payload.get("data")
        if not isinstance(model_objects, list):
            raise RuntimeError("OpenRouter model discovery response missing data list")

        ordered = _order_models(model_objects, self.preferred_models)
        if not ordered:
            raise RuntimeError("No free OpenRouter models available")

        _save_cached_models(self.models_cache_path, ordered)
        return ordered

    def _models(self) -> list[str]:
        if self._ordered_models is None:
            self._ordered_models = self._discover_free_models()
        return self._ordered_models

    def _generate_once(self, prompt: str, contents: list[str]) -> str:
        user_content = "\n\n".join(contents)
        last_error: Optional[Exception] = None

        for model_name in self._models():
            try:
                response = requests.post(
                    self.base_url + "/chat/completions",
                    headers={
                        "Authorization": "Bearer " + self.api_key,
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model_name,
                        "messages": [
                            {"role": "system", "content": prompt},
                            {"role": "user", "content": user_content},
                        ],
                        "temperature": 0.2,
                    },
                    timeout=(10, 60),
                )

                if response.status_code in (401, 403):
                    raise RuntimeError("OpenRouter authentication failed")
                if response.status_code >= 400:
                    raise RuntimeError(f"OpenRouter {response.status_code}: {response.text[:300]}")

                try:
                    payload = response.json()
                except ValueError as exc:
                    raise RuntimeError("OpenRouter response returned invalid JSON") from exc

                text = _extract_openrouter_text(payload)
                if not text:
                    raise RuntimeError("OpenRouter response contained no text")
                return text
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if "authentication failed" in str(exc).lower():
                    raise
                continue

        if last_error is None:
            raise RuntimeError("OpenRouter summarization failed: no model candidates")
        raise last_error

    def summarize_article(self, url: str, content: str) -> str:
        return self._generate_with_retry(["URL: " + url, content], error_prefix="OpenRouter summarization failed")

    def summarize_youtube(self, url: str) -> str:
        transcript = _fetch_youtube_transcript(url)
        return self._generate_with_retry(
            ["YouTube URL: " + url, "Transcript:\n" + transcript],
            error_prefix="OpenRouter summarization failed",
        )


def _extract_youtube_video_id(url: str) -> Optional[str]:
    parsed = urlparse(url)
    host = (parsed.netloc or "").lower()

    if host.endswith("youtu.be"):
        candidate = parsed.path.strip("/")
        return candidate or None

    if "youtube.com" in host:
        query_id = parse_qs(parsed.query).get("v", [])
        if query_id and isinstance(query_id[0], str) and query_id[0]:
            return query_id[0]

        parts = [segment for segment in parsed.path.split("/") if segment]
        if len(parts) >= 2 and parts[0] in {"shorts", "embed", "live", "v"}:
            return parts[1]

    return None


def _format_timestamp(seconds: float) -> str:
    total = max(int(seconds), 0)
    hours = total // 3600
    minutes = (total % 3600) // 60
    secs = total % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _fetch_youtube_transcript(url: str, languages: Optional[list[str]] = None) -> str:
    video_id = _extract_youtube_video_id(url)
    if not video_id:
        raise RuntimeError("Unsupported YouTube URL")

    requested_languages = languages or ["en", "en-US", "en-GB"]

    try:
        api = YouTubeTranscriptApi()
        if hasattr(api, "fetch"):
            snippets = api.fetch(video_id, languages=requested_languages)
            lines: list[str] = []
            for snippet in snippets:
                text = getattr(snippet, "text", "").strip()
                start = float(getattr(snippet, "start", 0.0))
                if text:
                    lines.append("[" + _format_timestamp(start) + "] " + text)
        else:
            raw_snippets = YouTubeTranscriptApi.get_transcript(video_id, languages=requested_languages)
            lines = []
            for snippet in raw_snippets:
                if not isinstance(snippet, dict):
                    continue
                text = str(snippet.get("text", "")).strip()
                start = float(snippet.get("start", 0.0))
                if text:
                    lines.append("[" + _format_timestamp(start) + "] " + text)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("YouTube transcript unavailable: " + str(exc)) from exc

    if not lines:
        raise RuntimeError("YouTube transcript unavailable: empty transcript")

    return "\n".join(lines)


def _source_output_path(url: str, run_date: date, base_dir: str = "data/sources") -> Path:
    parsed = urlparse(url)
    slug_seed = (parsed.netloc + parsed.path).strip("/") or "source"
    slug = slugify(slug_seed)[:80] or "source"
    day = run_date.isoformat()
    out_dir = Path(base_dir) / day
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / (slug + ".md")


class Summarizer(Protocol):
    def summarize_article(self, url: str, content: str) -> str:
        ...

    def summarize_youtube(self, url: str) -> str:
        ...


def summarize_item(
    item: Dict[str, Any],
    summarizer: Summarizer,
    run_date: date,
    sources_base_dir: str = "data/sources",
    failed_base_dir: str = "data/failed",
) -> Dict[str, Any]:
    url = item["url"]
    if item.get("status") != "ok":
        return item

    try:
        if item["kind"] == "article":
            summary = summarizer.summarize_article(url=url, content=item["content"])
        else:
            summary = summarizer.summarize_youtube(url=url)
    except Exception as exc:  # noqa: BLE001
        failure = write_failure_record(url=url, error=str(exc), base_dir=failed_base_dir)
        return {
            "status": "failed",
            "kind": item["kind"],
            "url": url,
            "error": str(exc),
            "failure_path": str(failure),
        }

    output_path = _source_output_path(url=url, run_date=run_date, base_dir=sources_base_dir)
    output_path.write_text(summary + "\n", encoding="utf-8")
    return {
        "status": "ok",
        "kind": item["kind"],
        "url": url,
        "summary_path": str(output_path),
    }


def summarize_items(
    items: list[Dict[str, Any]],
    run_date: date,
    sources_base_dir: str = "data/sources",
    failed_base_dir: str = "data/failed",
) -> list[Dict[str, Any]]:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("Missing OPENROUTER_API_KEY environment variable")

    base_url = os.environ.get("OPENROUTER_API_BASE", "https://openrouter.ai/api/v1")
    preferred_models_raw = os.environ.get("OPENROUTER_PREFERRED_MODELS", "")
    preferred_models = [
        model_name.strip()
        for model_name in preferred_models_raw.split(",")
        if model_name.strip()
    ]

    min_spacing_seconds = float(os.environ.get("OPENROUTER_MIN_SPACING_SECONDS", "1"))
    max_retries = int(os.environ.get("OPENROUTER_MAX_RETRIES", "6"))
    initial_backoff_seconds = float(os.environ.get("OPENROUTER_INITIAL_BACKOFF_SECONDS", "5"))
    max_backoff_seconds = float(os.environ.get("OPENROUTER_MAX_BACKOFF_SECONDS", "120"))
    models_cache_path = os.environ.get("OPENROUTER_MODELS_CACHE_PATH", "data/cache/openrouter_models.json")
    models_cache_ttl_seconds = int(os.environ.get("OPENROUTER_MODELS_CACHE_TTL_SECONDS", "21600"))

    summarizer = OpenRouterSummarizer(
        api_key=api_key,
        base_url=base_url,
        preferred_models=preferred_models,
        min_spacing_seconds=min_spacing_seconds,
        max_retries=max_retries,
        initial_backoff_seconds=initial_backoff_seconds,
        max_backoff_seconds=max_backoff_seconds,
        models_cache_path=models_cache_path,
        models_cache_ttl_seconds=models_cache_ttl_seconds,
    )

    results = []
    for item in items:
        results.append(
            summarize_item(
                item=item,
                summarizer=summarizer,
                run_date=run_date,
                sources_base_dir=sources_base_dir,
                failed_base_dir=failed_base_dir,
            )
        )
    return results
