try:
    from notebooklm_summarizer import (
        NOTEBOOKLM_AUTH_EXPIRED,
        NOTEBOOKLM_SOURCE_FAILED,
        NOTEBOOKLM_SUMMARY_FAILED,
        NotebookLMSummaryError,
        _resolve_storage_path as _resolve_storage_path_impl,
        summarize_url,
    )
except ImportError:
    from src.notebooklm_summarizer import (
        NOTEBOOKLM_AUTH_EXPIRED,
        NOTEBOOKLM_SOURCE_FAILED,
        NOTEBOOKLM_SUMMARY_FAILED,
        NotebookLMSummaryError,
        _resolve_storage_path as _resolve_storage_path_impl,
        summarize_url,
    )

YOUTUBE_AUTH_EXPIRED = "youtube_auth_expired"
YOUTUBE_SOURCE_FAILED = "youtube_source_failed"
YOUTUBE_SUMMARY_FAILED = "youtube_summary_failed"

class YouTubeSummaryError(RuntimeError):
    def __init__(self, reason: str, message: str = "") -> None:
        self.reason = reason
        super().__init__(reason if not message else f"{reason}: {message}")


_REASON_MAP = {
    NOTEBOOKLM_AUTH_EXPIRED: YOUTUBE_AUTH_EXPIRED,
    NOTEBOOKLM_SOURCE_FAILED: YOUTUBE_SOURCE_FAILED,
    NOTEBOOKLM_SUMMARY_FAILED: YOUTUBE_SUMMARY_FAILED,
}


def _reraise_as_youtube_error(exc: NotebookLMSummaryError) -> None:
    mapped_reason = _REASON_MAP.get(exc.reason, YOUTUBE_SUMMARY_FAILED)
    message = str(exc)
    prefix = exc.reason + ": "
    if message.startswith(prefix):
        message = message[len(prefix):]
    raise YouTubeSummaryError(mapped_reason, message) from exc


def _resolve_storage_path() -> tuple[str, bool]:
    try:
        return _resolve_storage_path_impl()
    except NotebookLMSummaryError as exc:
        _reraise_as_youtube_error(exc)


def summarize_youtube(url: str, prompt: str) -> str:
    try:
        return summarize_url(url=url, prompt=prompt)
    except NotebookLMSummaryError as exc:
        _reraise_as_youtube_error(exc)
