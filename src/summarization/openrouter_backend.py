from __future__ import annotations

import json
import random
import re
import threading
import time
from pathlib import Path
from typing import Any

import requests

from src._config import OpenRouterConfig
from src._prompts import load_prompt


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
        self._cached_prompt: str | None = None
        self.min_spacing_seconds = min_spacing_seconds
        self.max_retries = max_retries
        self.initial_backoff_seconds = initial_backoff_seconds
        self.max_backoff_seconds = max_backoff_seconds
        self._next_request_at = 0.0
        self._spacing_lock = threading.Lock()

    def _wait_for_min_spacing(self) -> None:
        with self._spacing_lock:
            now = time.monotonic()
            earliest_allowed = max(now, self._next_request_at)
            wait_seconds = earliest_allowed - now
            self._next_request_at = earliest_allowed + self.min_spacing_seconds
        if wait_seconds > 0:
            time.sleep(wait_seconds)

    def _is_rate_limited(self, error: Exception) -> bool:
        text = str(error).lower()
        return ("429" in text) or ("rate" in text and "limit" in text)

    def _extract_retry_after(self, error: Exception) -> float | None:
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

    def _generate_once(self, prompt: str, contents: list[str]) -> str:
        raise NotImplementedError

    def _generate_with_retry(self, contents: list[str], error_prefix: str) -> str:
        if self._cached_prompt is None:
            self._cached_prompt = load_prompt(self.prompt_path)
        prompt = self._cached_prompt
        last_error: Exception | None = None

        for attempt in range(self.max_retries):
            try:
                self._wait_for_min_spacing()
                text = self._generate_once(prompt=prompt, contents=contents)
                if not text:
                    raise RuntimeError("Response contained no text")
                return text.strip()
            except Exception as exc:  # noqa: BLE001
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
        preferred_models: list[str] | None = None,
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
        self._ordered_models: list[str] | None = None
        self._models_lock = threading.Lock()
        super().__init__(
            prompt_path=prompt_path,
            min_spacing_seconds=min_spacing_seconds,
            max_retries=max_retries,
            initial_backoff_seconds=initial_backoff_seconds,
            max_backoff_seconds=max_backoff_seconds,
        )

    @classmethod
    def from_config(cls, config: OpenRouterConfig) -> OpenRouterSummarizer:
        return cls(
            api_key=config.api_key,
            base_url=config.base_url,
            preferred_models=config.preferred_models,
            min_spacing_seconds=config.min_spacing_seconds,
            max_retries=config.max_retries,
            initial_backoff_seconds=config.initial_backoff_seconds,
            max_backoff_seconds=config.max_backoff_seconds,
            models_cache_path=config.models_cache_path,
            models_cache_ttl_seconds=config.models_cache_ttl_seconds,
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
            with self._models_lock:
                if self._ordered_models is None:
                    self._ordered_models = self._discover_free_models()
        return self._ordered_models

    def _generate_once(self, prompt: str, contents: list[str]) -> str:
        user_content = "\n\n".join(contents)
        last_error: Exception | None = None

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
