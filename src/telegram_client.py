import json
import os
import re
from pathlib import Path
from typing import Any, Optional, Union

import requests


URL_PATTERN = re.compile(r"https?://[^\s<>()\[\]{}\"']+")


def load_offset(state_path: Union[str, Path] = "state.json") -> Optional[int]:
    path = Path(state_path)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    offset = data.get("telegram_offset")
    if isinstance(offset, int):
        return offset
    return None


def save_offset(offset: int, state_path: Union[str, Path] = "state.json") -> None:
    path = Path(state_path)
    payload = {"telegram_offset": offset}
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def extract_urls(text: str) -> list[str]:
    urls = []
    for match in URL_PATTERN.finditer(text):
        url = match.group(0).rstrip(".,;:!?)]}")
        urls.append(url)
    return urls


def _telegram_api_get(bot_token: str, method: str, params: dict[str, Any]) -> dict[str, Any]:
    response = requests.get(
        f"https://api.telegram.org/bot{bot_token}/{method}",
        params=params,
        timeout=(10, 30),
    )
    response.raise_for_status()
    payload: dict[str, Any] = response.json()
    if not payload.get("ok"):
        raise RuntimeError(f"Telegram API error for {method}: {payload}")
    return payload


def get_updates(bot_token: str, offset: Optional[int]) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"timeout": 0, "limit": 100}
    if offset is not None:
        params["offset"] = offset
    payload = _telegram_api_get(bot_token, "getUpdates", params)
    result = payload.get("result", [])
    if not isinstance(result, list):
        raise RuntimeError("Telegram getUpdates response missing result list")
    return result


def poll_urls(
    bot_token: str,
    allowed_chat_id: int,
    state_path: Union[str, Path] = "state.json",
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


def poll_urls_from_env(state_path: Union[str, Path] = "state.json") -> dict[str, Any]:
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id_raw = os.environ.get("TELEGRAM_CHAT_ID")

    if not bot_token:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN environment variable")
    if not chat_id_raw:
        raise RuntimeError("Missing TELEGRAM_CHAT_ID environment variable")

    try:
        allowed_chat_id = int(chat_id_raw)
    except ValueError as exc:
        raise RuntimeError("TELEGRAM_CHAT_ID must be an integer") from exc

    return poll_urls(bot_token=bot_token, allowed_chat_id=allowed_chat_id, state_path=state_path)
