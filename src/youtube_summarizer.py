import asyncio
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Tuple

from notebooklm import NotebookLMClient
from notebooklm.exceptions import AuthError, NotebookLMError, SourceAddError, SourceProcessingError, SourceTimeoutError

YOUTUBE_AUTH_EXPIRED = "youtube_auth_expired"
YOUTUBE_SOURCE_FAILED = "youtube_source_failed"
YOUTUBE_SUMMARY_FAILED = "youtube_summary_failed"

LOGGER = logging.getLogger(__name__)


class YouTubeSummaryError(RuntimeError):
    def __init__(self, reason: str, message: str = "") -> None:
        self.reason = reason
        super().__init__(reason if not message else f"{reason}: {message}")


def _resolve_storage_path() -> Tuple[str, bool]:
    """Resolve the NotebookLM storage_state.json path.

    Priority:
    1. NOTEBOOKLM_STORAGE_PATH env var — explicit file path
    2. NOTEBOOKLM_STORAGE_STATE env var — JSON content (from GitHub Actions secret), written to temp file
    3. Default ~/.notebooklm/storage_state.json (created by `notebooklm login`)

    Returns:
        (path, should_cleanup) — should_cleanup is True when a temp file was created.
    """
    explicit_path = os.environ.get("NOTEBOOKLM_STORAGE_PATH")
    if explicit_path and Path(explicit_path).exists():
        return explicit_path, False

    state_content = os.environ.get("NOTEBOOKLM_STORAGE_STATE")
    if state_content:
        try:
            json.loads(state_content)
        except json.JSONDecodeError as exc:
            raise YouTubeSummaryError(YOUTUBE_AUTH_EXPIRED, "NOTEBOOKLM_STORAGE_STATE is not valid JSON") from exc

        fd, storage_path = tempfile.mkstemp(prefix="notebooklm-storage-", suffix=".json")
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(state_content)
        return storage_path, True

    default = Path.home() / ".notebooklm" / "storage_state.json"
    if default.exists():
        return str(default), False

    raise YouTubeSummaryError(
        YOUTUBE_AUTH_EXPIRED,
        "No storage_state.json found. Run `notebooklm login` locally or set NOTEBOOKLM_STORAGE_STATE.",
    )


def summarize_youtube(url: str, prompt: str) -> str:
    """Fetch and summarize a YouTube video via NotebookLM.

    Creates a temporary notebook, adds the YouTube URL, asks NotebookLM
    to summarize using the provided prompt, then deletes the notebook.

    Args:
        url: YouTube video URL.
        prompt: The summarization prompt text.

    Returns:
        Summary text from NotebookLM.

    Raises:
        YouTubeSummaryError: On auth failure, source processing failure, or empty response.
    """
    return asyncio.run(_summarize_youtube_async(url, prompt))


async def _summarize_youtube_async(url: str, prompt: str) -> str:
    storage_path, cleanup_storage_file = _resolve_storage_path()

    try:
        async with NotebookLMClient.from_storage(storage_path) as client:
            nb = await client.notebooks.create("tldr-bot-temp")
            try:
                try:
                    await client.sources.add_url(nb.id, url, wait=True)
                except (SourceAddError, SourceProcessingError, SourceTimeoutError) as exc:
                    raise YouTubeSummaryError(YOUTUBE_SOURCE_FAILED, str(exc)) from exc

                result = await client.chat.ask(nb.id, prompt)
                answer = (result.answer if result else "")
                if not answer or not answer.strip():
                    raise YouTubeSummaryError(YOUTUBE_SUMMARY_FAILED, "NotebookLM returned empty answer")
                return answer.strip()
            finally:
                try:
                    await client.notebooks.delete(nb.id)
                except Exception as exc:  # noqa: BLE001
                    LOGGER.warning("NotebookLM cleanup failed for notebook %s: %s", nb.id, exc)
    except YouTubeSummaryError:
        raise
    except AuthError as exc:
        raise YouTubeSummaryError(YOUTUBE_AUTH_EXPIRED, str(exc)) from exc
    except NotebookLMError as exc:
        raise YouTubeSummaryError(YOUTUBE_SUMMARY_FAILED, str(exc)) from exc
    finally:
        if cleanup_storage_file:
            try:
                Path(storage_path).unlink(missing_ok=True)
            except OSError as exc:
                LOGGER.warning("Failed to remove temporary NotebookLM storage state %s: %s", storage_path, exc)
