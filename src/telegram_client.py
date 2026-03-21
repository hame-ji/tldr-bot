from __future__ import annotations

import html
import json
import os
import re
from pathlib import Path
from typing import Any

import requests


URL_PATTERN = re.compile(r"https?://[^\s<>()\[\]{}\"']+")


def load_offset(state_path: str | Path = "state.json") -> int | None:
    path = Path(state_path)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    offset = data.get("telegram_offset")
    if isinstance(offset, int):
        return offset
    return None


def save_offset(offset: int, state_path: str | Path = "state.json") -> None:
    path = Path(state_path)
    payload = {"telegram_offset": offset}
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def extract_urls(text: str) -> list[str]:
    urls = []
    for match in URL_PATTERN.finditer(text):
        url = match.group(0).rstrip(".,;:!?)]}")
        urls.append(url)
    return urls


def _telegram_api(
    bot_token: str, method: str, data: dict[str, Any], *, post: bool = False,
) -> dict[str, Any]:
    url = f"https://api.telegram.org/bot{bot_token}/{method}"
    if post:
        response = requests.post(url, json=data, timeout=(10, 30))
    else:
        response = requests.get(url, params=data, timeout=(10, 30))
    response.raise_for_status()
    payload: dict[str, Any] = response.json()
    if not payload.get("ok"):
        raise RuntimeError(f"Telegram API error for {method}: {payload}")
    return payload


def get_updates(bot_token: str, offset: int | None) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"timeout": 0, "limit": 100}
    if offset is not None:
        params["offset"] = offset
    payload = _telegram_api(bot_token, "getUpdates", params)
    result = payload.get("result", [])
    if not isinstance(result, list):
        raise RuntimeError("Telegram getUpdates response missing result list")
    return result


def poll_urls(
    bot_token: str,
    allowed_chat_id: int,
    state_path: str | Path = "state.json",
) -> dict[str, Any]:
    previous_offset = load_offset(state_path)
    updates = get_updates(bot_token, previous_offset)

    if updates:
        max_update_id = max(int(update["update_id"]) for update in updates)
        next_offset = max_update_id + 1
        save_offset(next_offset, state_path)
    else:
        next_offset = previous_offset

    urls: list[str] = []
    for update in updates:
        message = update.get("message") or update.get("edited_message") or {}
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        if chat_id != allowed_chat_id:
            continue
        text = message.get("text") or ""
        if not isinstance(text, str):
            continue
        urls.extend(extract_urls(text))

    return {
        "urls": urls,
        "update_count": len(updates),
        "previous_offset": previous_offset,
        "next_offset": next_offset,
    }


def _telegram_credentials_from_env() -> tuple[str, int]:
    from src._config import telegram_config_from_env
    config = telegram_config_from_env()
    return config.bot_token, config.chat_id


def poll_urls_from_env(state_path: str | Path = "state.json") -> dict[str, Any]:
    bot_token, allowed_chat_id = _telegram_credentials_from_env()
    return poll_urls(bot_token=bot_token, allowed_chat_id=allowed_chat_id, state_path=state_path)


def _split_long_text(text: str, max_length: int) -> list[str]:
    return [text[start : start + max_length] for start in range(0, len(text), max_length)]


def chunk_text_by_paragraph(text: str, max_length: int = 4096) -> list[str]:
    if not text:
        return []

    paragraphs = text.split("\n\n")
    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        escaped_paragraph = html.escape(paragraph, quote=False)

        if len(escaped_paragraph) > max_length:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(_split_long_text(escaped_paragraph, max_length=max_length))
            continue

        candidate = escaped_paragraph if not current else current + "\n\n" + escaped_paragraph
        if len(candidate) <= max_length:
            current = candidate
        else:
            if current:
                chunks.append(current)
            current = escaped_paragraph

    if current:
        chunks.append(current)

    return chunks


def send_digest(
    bot_token: str,
    chat_id: int,
    digest_text: str,
    parse_mode: str = "HTML",
    max_chunk_length: int = 4096,
) -> list[dict[str, Any]]:
    chunks = chunk_text_by_paragraph(digest_text, max_length=max_chunk_length)
    responses: list[dict[str, Any]] = []

    for chunk in chunks:
        body: dict[str, Any] = {
            "chat_id": chat_id,
            "text": chunk,
        }
        if parse_mode:
            body["parse_mode"] = parse_mode
        responses.append(_telegram_api(bot_token, "sendMessage", body, post=True))

    return responses


def send_digest_from_env(digest_text: str) -> list[dict[str, Any]]:
    bot_token, chat_id = _telegram_credentials_from_env()
    return send_digest(bot_token=bot_token, chat_id=chat_id, digest_text=digest_text)
