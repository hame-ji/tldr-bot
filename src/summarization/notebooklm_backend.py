from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
from pathlib import Path

try:
    from notebooklm import NotebookLMClient
    from notebooklm.exceptions import AuthError, NotebookLMError, SourceAddError, SourceProcessingError, SourceTimeoutError
except ImportError:
    class NotebookLMError(RuntimeError):
        pass

    class AuthError(NotebookLMError):
        pass

    class SourceAddError(NotebookLMError):
        pass

    class SourceProcessingError(NotebookLMError):
        pass

    class SourceTimeoutError(NotebookLMError):
        pass

    class _NotebookLMClientFallback:
        @staticmethod
        async def from_storage(*_args: object, **_kwargs: object) -> object:
            raise NotebookLMError("notebooklm import failed; install optional notebooklm dependency")

    NotebookLMClient = _NotebookLMClientFallback

NOTEBOOKLM_AUTH_EXPIRED = "notebooklm_auth_expired"
NOTEBOOKLM_SOURCE_FAILED = "notebooklm_source_failed"
NOTEBOOKLM_SUMMARY_FAILED = "notebooklm_summary_failed"

YOUTUBE_AUTH_EXPIRED = "youtube_auth_expired"
YOUTUBE_SOURCE_FAILED = "youtube_source_failed"
YOUTUBE_SUMMARY_FAILED = "youtube_summary_failed"

LOGGER = logging.getLogger(__name__)


class NotebookLMSummaryError(RuntimeError):
    def __init__(self, reason: str, message: str = "") -> None:
        self.reason = reason
        super().__init__(reason if not message else f"{reason}: {message}")


class YouTubeSummaryError(RuntimeError):
    def __init__(self, reason: str, message: str = "") -> None:
        self.reason = reason
        super().__init__(reason if not message else f"{reason}: {message}")


_YOUTUBE_REASON_MAP = {
    NOTEBOOKLM_AUTH_EXPIRED: YOUTUBE_AUTH_EXPIRED,
    NOTEBOOKLM_SOURCE_FAILED: YOUTUBE_SOURCE_FAILED,
    NOTEBOOKLM_SUMMARY_FAILED: YOUTUBE_SUMMARY_FAILED,
}


def _reraise_as_youtube_error(exc: NotebookLMSummaryError) -> None:
    mapped_reason = _YOUTUBE_REASON_MAP.get(exc.reason, YOUTUBE_SUMMARY_FAILED)
    message = str(exc)
    prefix = exc.reason + ": "
    if message.startswith(prefix):
        message = message[len(prefix):]
    raise YouTubeSummaryError(mapped_reason, message) from exc


def _resolve_storage_path() -> tuple[str, bool]:
    explicit_path = os.environ.get("NOTEBOOKLM_STORAGE_PATH")
    if explicit_path and Path(explicit_path).exists():
        return explicit_path, False

    state_content = os.environ.get("NOTEBOOKLM_STORAGE_STATE")
    if state_content:
        try:
            json.loads(state_content)
        except json.JSONDecodeError as exc:
            raise NotebookLMSummaryError(
                NOTEBOOKLM_AUTH_EXPIRED,
                "NOTEBOOKLM_STORAGE_STATE is not valid JSON",
            ) from exc

        fd, storage_path = tempfile.mkstemp(prefix="notebooklm-storage-", suffix=".json")
        try:
            os.fchmod(fd, 0o600)
            handle = os.fdopen(fd, "w", encoding="utf-8")
            fd = None  # fdopen took ownership; don't close manually
            with handle:
                handle.write(state_content)
        except Exception:
            if fd is not None:
                os.close(fd)
            Path(storage_path).unlink(missing_ok=True)
            raise
        return storage_path, True

    default = Path.home() / ".notebooklm" / "storage_state.json"
    if default.exists():
        return str(default), False

    raise NotebookLMSummaryError(
        NOTEBOOKLM_AUTH_EXPIRED,
        "No storage_state.json found. Run `notebooklm login` locally or set NOTEBOOKLM_STORAGE_STATE.",
    )


def summarize_url(url: str, prompt: str) -> str:
    return asyncio.run(_summarize_url_async(url, prompt))


async def _summarize_url_async(url: str, prompt: str) -> str:
    storage_path, cleanup_storage_file = _resolve_storage_path()

    try:
        async with await NotebookLMClient.from_storage(storage_path) as client:
            nb = await client.notebooks.create("tldr-bot-temp")
            try:
                try:
                    await client.sources.add_url(nb.id, url, wait=True)
                except (SourceAddError, SourceProcessingError, SourceTimeoutError) as exc:
                    raise NotebookLMSummaryError(NOTEBOOKLM_SOURCE_FAILED, str(exc)) from exc

                result = await client.chat.ask(nb.id, prompt)
                answer = (result.answer if result else "")
                if not answer or not answer.strip():
                    raise NotebookLMSummaryError(NOTEBOOKLM_SUMMARY_FAILED, "NotebookLM returned empty answer")
                return answer.strip()
            finally:
                try:
                    await client.notebooks.delete(nb.id)
                except Exception as exc:  # noqa: BLE001
                    LOGGER.warning("NotebookLM cleanup failed for notebook %s: %s", nb.id, exc)
    except NotebookLMSummaryError:
        raise
    except AuthError as exc:
        raise NotebookLMSummaryError(NOTEBOOKLM_AUTH_EXPIRED, str(exc)) from exc
    except NotebookLMError as exc:
        raise NotebookLMSummaryError(NOTEBOOKLM_SUMMARY_FAILED, str(exc)) from exc
    finally:
        if cleanup_storage_file:
            try:
                Path(storage_path).unlink(missing_ok=True)
            except OSError as exc:
                LOGGER.warning("Failed to remove temporary NotebookLM storage state %s: %s", storage_path, exc)


def summarize_youtube(url: str, prompt: str) -> str:
    try:
        return summarize_url(url=url, prompt=prompt)
    except NotebookLMSummaryError as exc:
        _reraise_as_youtube_error(exc)
