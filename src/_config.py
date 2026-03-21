from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env_enabled(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default

    normalized = raw.strip().lower()
    if normalized in {"0", "false", "no", "off"}:
        return False
    if normalized in {"1", "true", "yes", "on"}:
        return True
    return default


@dataclass(frozen=True)
class OpenRouterConfig:
    api_key: str
    base_url: str = "https://openrouter.ai/api/v1"
    preferred_models: list[str] = field(default_factory=list)
    min_spacing_seconds: float = 1.0
    max_retries: int = 6
    initial_backoff_seconds: float = 5.0
    max_backoff_seconds: float = 120.0
    models_cache_path: str = "data/cache/openrouter_models.json"
    models_cache_ttl_seconds: int = 21600


@dataclass(frozen=True)
class NotebookLMConfig:
    youtube_prompt_path: str = "prompts/youtube_summarize.txt"
    article_fallback_prompt_path: str = "prompts/summarize.txt"
    article_fallback_enabled: bool = True


@dataclass(frozen=True)
class TelegramConfig:
    bot_token: str
    chat_id: int


def openrouter_config_from_env() -> OpenRouterConfig:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("Missing OPENROUTER_API_KEY environment variable")

    preferred_models_raw = os.environ.get("OPENROUTER_PREFERRED_MODELS", "")
    preferred_models = [m.strip() for m in preferred_models_raw.split(",") if m.strip()]

    return OpenRouterConfig(
        api_key=api_key,
        base_url=os.environ.get("OPENROUTER_API_BASE", "https://openrouter.ai/api/v1"),
        preferred_models=preferred_models,
        min_spacing_seconds=float(os.environ.get("OPENROUTER_MIN_SPACING_SECONDS", "1")),
        max_retries=int(os.environ.get("OPENROUTER_MAX_RETRIES", "6")),
        initial_backoff_seconds=float(os.environ.get("OPENROUTER_INITIAL_BACKOFF_SECONDS", "5")),
        max_backoff_seconds=float(os.environ.get("OPENROUTER_MAX_BACKOFF_SECONDS", "120")),
        models_cache_path=os.environ.get("OPENROUTER_MODELS_CACHE_PATH", "data/cache/openrouter_models.json"),
        models_cache_ttl_seconds=int(os.environ.get("OPENROUTER_MODELS_CACHE_TTL_SECONDS", "21600")),
    )


def notebooklm_config_from_env() -> NotebookLMConfig:
    return NotebookLMConfig(
        youtube_prompt_path=os.environ.get("NOTEBOOKLM_SUMMARIZE_PROMPT_PATH", "prompts/youtube_summarize.txt"),
        article_fallback_prompt_path=os.environ.get("NOTEBOOKLM_ARTICLE_SUMMARIZE_PROMPT_PATH", "prompts/summarize.txt"),
        article_fallback_enabled=_env_enabled("NOTEBOOKLM_ARTICLE_FALLBACK_ENABLED", default=True),
    )


def telegram_config_from_env() -> TelegramConfig:
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id_raw = os.environ.get("TELEGRAM_CHAT_ID")

    if not bot_token:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN environment variable")
    if not chat_id_raw:
        raise RuntimeError("Missing TELEGRAM_CHAT_ID environment variable")

    try:
        chat_id = int(chat_id_raw)
    except ValueError as exc:
        raise RuntimeError("TELEGRAM_CHAT_ID must be an integer") from exc

    return TelegramConfig(bot_token=bot_token, chat_id=chat_id)
