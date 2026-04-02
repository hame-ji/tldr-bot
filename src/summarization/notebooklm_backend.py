from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
import threading
from pathlib import Path
from typing import NoReturn

try:
    from notebooklm import NotebookLMClient
    from notebooklm.exceptions import (
        AuthError,
        NotebookLMError,
        SourceAddError,
        SourceProcessingError,
        SourceTimeoutError,
    )
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
            raise NotebookLMError(
                "notebooklm import failed; install optional notebooklm dependency"
            )

    NotebookLMClient = _NotebookLMClientFallback

NOTEBOOKLM_AUTH_EXPIRED = "notebooklm_auth_expired"
NOTEBOOKLM_STORAGE_MISCONFIGURED = "notebooklm_storage_misconfigured"
NOTEBOOKLM_SOURCE_FAILED = "notebooklm_source_failed"
NOTEBOOKLM_SUMMARY_FAILED = "notebooklm_summary_failed"

NOTEBOOKLM_PREFLIGHT_OK = "ok"
NOTEBOOKLM_PREFLIGHT_AUTH_EXPIRED = "auth_expired"
NOTEBOOKLM_PREFLIGHT_MISCONFIGURED = "misconfigured"
NOTEBOOKLM_PREFLIGHT_BACKEND_ERROR = "backend_error"
NOTEBOOKLM_PREFLIGHT_SKIPPED = "skipped"

YOUTUBE_AUTH_EXPIRED = "youtube_auth_expired"
YOUTUBE_SOURCE_FAILED = "youtube_source_failed"
YOUTUBE_SUMMARY_FAILED = "youtube_summary_failed"

LOGGER = logging.getLogger(__name__)
_NOTEBOOKLM_PREFLIGHT_TIMEOUT_SECONDS = 20
_PREFLIGHT_OUTER_TIMEOUT_SECONDS = 25


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
    NOTEBOOKLM_STORAGE_MISCONFIGURED: YOUTUBE_AUTH_EXPIRED,
    NOTEBOOKLM_SOURCE_FAILED: YOUTUBE_SOURCE_FAILED,
    NOTEBOOKLM_SUMMARY_FAILED: YOUTUBE_SUMMARY_FAILED,
}


def _reraise_as_youtube_error(exc: NotebookLMSummaryError) -> NoReturn:
    mapped_reason = _YOUTUBE_REASON_MAP.get(exc.reason, YOUTUBE_SUMMARY_FAILED)
    message = str(exc)
    prefix = exc.reason + ": "
    if message.startswith(prefix):
        message = message[len(prefix) :]
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
                NOTEBOOKLM_STORAGE_MISCONFIGURED,
                "NOTEBOOKLM_STORAGE_STATE is not valid JSON",
            ) from exc

        fd, storage_path = tempfile.mkstemp(
            prefix="notebooklm-storage-", suffix=".json"
        )
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
        NOTEBOOKLM_STORAGE_MISCONFIGURED,
        "No storage_state.json found. Run `notebooklm login` locally or set NOTEBOOKLM_STORAGE_STATE.",
    )


def _cleanup_temp_storage(path: str, should_cleanup: bool) -> None:
    if not should_cleanup:
        return
    try:
        Path(path).unlink(missing_ok=True)
    except OSError as exc:
        LOGGER.warning(
            "Failed to remove temporary NotebookLM storage state %s: %s",
            path,
            exc,
        )


def _classify_preflight_storage_error(exc: NotebookLMSummaryError) -> str:
    if exc.reason == NOTEBOOKLM_STORAGE_MISCONFIGURED:
        return NOTEBOOKLM_PREFLIGHT_MISCONFIGURED
    return NOTEBOOKLM_PREFLIGHT_AUTH_EXPIRED


def check_notebooklm_auth() -> str:
    result: str = NOTEBOOKLM_PREFLIGHT_BACKEND_ERROR

    def _run() -> None:
        nonlocal result
        result = asyncio.run(_check_notebooklm_auth_async())

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    thread.join(timeout=_PREFLIGHT_OUTER_TIMEOUT_SECONDS)
    if thread.is_alive():
        LOGGER.error(
            "NotebookLM auth preflight timed out after %ds",
            _PREFLIGHT_OUTER_TIMEOUT_SECONDS,
        )
        return NOTEBOOKLM_PREFLIGHT_BACKEND_ERROR
    return result


async def _attempt_notebooklm_auth(storage_path: str) -> None:
    async with await NotebookLMClient.from_storage(storage_path):
        return None


async def _check_notebooklm_auth_async() -> str:
    try:
        storage_path, cleanup_storage_file = _resolve_storage_path()
    except NotebookLMSummaryError as exc:
        return _classify_preflight_storage_error(exc)
    except Exception:
        return NOTEBOOKLM_PREFLIGHT_BACKEND_ERROR

    try:
        await asyncio.wait_for(
            _attempt_notebooklm_auth(storage_path),
            timeout=_NOTEBOOKLM_PREFLIGHT_TIMEOUT_SECONDS,
        )
        return NOTEBOOKLM_PREFLIGHT_OK
    except asyncio.TimeoutError:
        return NOTEBOOKLM_PREFLIGHT_BACKEND_ERROR
    except AuthError:
        return NOTEBOOKLM_PREFLIGHT_AUTH_EXPIRED
    except NotebookLMError:
        return NOTEBOOKLM_PREFLIGHT_BACKEND_ERROR
    except Exception:
        return NOTEBOOKLM_PREFLIGHT_BACKEND_ERROR
    finally:
        _cleanup_temp_storage(storage_path, cleanup_storage_file)


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
                except (
                    SourceAddError,
                    SourceProcessingError,
                    SourceTimeoutError,
                ) as exc:
                    raise NotebookLMSummaryError(
                        NOTEBOOKLM_SOURCE_FAILED, str(exc)
                    ) from exc

                result = await client.chat.ask(nb.id, prompt)
                answer = result.answer if result else ""
                if not answer or not answer.strip():
                    raise NotebookLMSummaryError(
                        NOTEBOOKLM_SUMMARY_FAILED, "NotebookLM returned empty answer"
                    )
                return answer.strip()
            finally:
                try:
                    await client.notebooks.delete(nb.id)
                except Exception as exc:  # noqa: BLE001
                    LOGGER.warning(
                        "NotebookLM cleanup failed for notebook %s: %s", nb.id, exc
                    )
    except NotebookLMSummaryError:
        raise
    except AuthError as exc:
        raise NotebookLMSummaryError(NOTEBOOKLM_AUTH_EXPIRED, str(exc)) from exc
    except NotebookLMError as exc:
        raise NotebookLMSummaryError(NOTEBOOKLM_SUMMARY_FAILED, str(exc)) from exc
    finally:
        _cleanup_temp_storage(storage_path, cleanup_storage_file)


def summarize_youtube(url: str, prompt: str) -> str:
    try:
        return summarize_url(url=url, prompt=prompt)
    except NotebookLMSummaryError as exc:
        _reraise_as_youtube_error(exc)
