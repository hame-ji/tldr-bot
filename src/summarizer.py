import os
import random
import re
import time
from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional, Protocol

from slugify import slugify

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
        return "429" in text or "resource_exhausted" in text or "ratelimit" in text

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


class GeminiSummarizer(_RetryingSummarizerBase):
    def __init__(
        self,
        api_key: str,
        prompt_path: str = "prompts/summarize.txt",
        model: str = "gemini-2.5-flash",
        fallback_models: Optional[list[str]] = None,
        min_spacing_seconds: float = 1.0,
        max_retries: int = 6,
        initial_backoff_seconds: float = 5.0,
        max_backoff_seconds: float = 120.0,
    ) -> None:
        from google import genai

        self.client = genai.Client(api_key=api_key)
        self.model = model
        self.fallback_models = fallback_models or []
        super().__init__(
            prompt_path=prompt_path,
            min_spacing_seconds=min_spacing_seconds,
            max_retries=max_retries,
            initial_backoff_seconds=initial_backoff_seconds,
            max_backoff_seconds=max_backoff_seconds,
        )

    def _is_model_unavailable(self, error: Exception) -> bool:
        text = str(error).lower()
        return (
            ("404" in text or "not_found" in text)
            and "model" in text
            and (
                "no longer available" in text
                or "not available" in text
                or "not found" in text
            )
        )

    def _generate_once(self, prompt: str, contents: list[str]) -> str:
        models_to_try = [self.model] + self.fallback_models
        last_error: Optional[Exception] = None

        for idx, model_name in enumerate(models_to_try):
            try:
                response = self.client.models.generate_content(
                    model=model_name,
                    contents=[prompt] + contents,
                )
                text = getattr(response, "text", None)
                if not text:
                    raise RuntimeError("Gemini response contained no text")
                self.model = model_name
                return str(text)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                is_last_model = idx == len(models_to_try) - 1
                if self._is_model_unavailable(exc) and not is_last_model:
                    continue
                raise

        if last_error is None:
            raise RuntimeError("Gemini summarization failed: model selection failed")
        raise last_error

    def summarize_article(self, url: str, content: str) -> str:
        return self._generate_with_retry(["URL: " + url, content], error_prefix="Gemini summarization failed")

    def summarize_youtube(self, url: str) -> str:
        return self._generate_with_retry(["YouTube URL: " + url], error_prefix="Gemini summarization failed")


def _source_output_path(url: str, run_date: date, base_dir: str = "data/sources") -> Path:
    from urllib.parse import urlparse

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
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing GEMINI_API_KEY environment variable")

    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    fallback_models_raw = os.environ.get("GEMINI_FALLBACK_MODELS", "gemini-2.5-flash-lite")
    fallback_models = [
        model_name.strip()
        for model_name in fallback_models_raw.split(",")
        if model_name.strip()
    ]
    min_spacing_seconds = float(os.environ.get("GEMINI_MIN_SPACING_SECONDS", "1"))
    max_retries = int(os.environ.get("GEMINI_MAX_RETRIES", "6"))
    initial_backoff_seconds = float(os.environ.get("GEMINI_INITIAL_BACKOFF_SECONDS", "5"))
    max_backoff_seconds = float(os.environ.get("GEMINI_MAX_BACKOFF_SECONDS", "120"))

    summarizer = GeminiSummarizer(
        api_key=api_key,
        model=model,
        fallback_models=fallback_models,
        min_spacing_seconds=min_spacing_seconds,
        max_retries=max_retries,
        initial_backoff_seconds=initial_backoff_seconds,
        max_backoff_seconds=max_backoff_seconds,
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
