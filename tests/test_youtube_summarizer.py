import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from src.youtube_summarizer import (
    YOUTUBE_AUTH_EXPIRED,
    YOUTUBE_SOURCE_FAILED,
    YOUTUBE_SUMMARY_FAILED,
    YouTubeSummaryError,
    _resolve_storage_path,
    summarize_youtube,
)


class ResolveStoragePathTests(unittest.TestCase):
    def test_explicit_path_env_takes_priority(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            f.write(b"{}")
            tmppath = f.name
        try:
            with patch.dict(os.environ, {"NOTEBOOKLM_STORAGE_PATH": tmppath}):
                result = _resolve_storage_path()
            self.assertEqual(result, (tmppath, False))
        finally:
            os.unlink(tmppath)

    def test_state_content_env_writes_temp_file(self) -> None:
        state_json = '{"cookies": []}'
        env = {"NOTEBOOKLM_STORAGE_STATE": state_json}
        env.pop("NOTEBOOKLM_STORAGE_PATH", None)
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("NOTEBOOKLM_STORAGE_PATH", None)
            result = _resolve_storage_path()
        path_str, should_cleanup = result
        path = Path(path_str)
        try:
            self.assertTrue(path.exists())
            self.assertEqual(path.read_text(encoding="utf-8"), state_json)
            self.assertTrue(should_cleanup)
            if os.name != "nt":
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        finally:
            if path.exists():
                path.unlink()

    def test_invalid_state_json_raises_auth_expired(self) -> None:
        env = {"NOTEBOOKLM_STORAGE_STATE": "{invalid-json"}
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("NOTEBOOKLM_STORAGE_PATH", None)
            with self.assertRaises(YouTubeSummaryError) as ctx:
                _resolve_storage_path()
        self.assertEqual(ctx.exception.reason, YOUTUBE_AUTH_EXPIRED)

    def test_raises_auth_expired_when_nothing_configured(self) -> None:
        env = {}
        with patch.dict(os.environ, env):
            os.environ.pop("NOTEBOOKLM_STORAGE_PATH", None)
            os.environ.pop("NOTEBOOKLM_STORAGE_STATE", None)
            with patch("src.youtube_summarizer.Path.home") as mock_home:
                mock_home.return_value = Path("/nonexistent-home-xyz")
                with self.assertRaises(YouTubeSummaryError) as ctx:
                    _resolve_storage_path()
        self.assertEqual(ctx.exception.reason, YOUTUBE_AUTH_EXPIRED)


class SummarizeYoutubeTests(unittest.TestCase):
    def _make_mock_client(self, answer: str = "great summary") -> MagicMock:
        mock_source = MagicMock()
        mock_source.id = "source-id-1"

        mock_nb = MagicMock()
        mock_nb.id = "notebook-id-1"

        mock_ask_result = MagicMock()
        mock_ask_result.answer = answer

        mock_notebooks = AsyncMock()
        mock_notebooks.create = AsyncMock(return_value=mock_nb)
        mock_notebooks.delete = AsyncMock(return_value=True)

        mock_sources = AsyncMock()
        mock_sources.add_url = AsyncMock(return_value=mock_source)

        mock_chat = AsyncMock()
        mock_chat.ask = AsyncMock(return_value=mock_ask_result)

        mock_client = AsyncMock()
        mock_client.notebooks = mock_notebooks
        mock_client.sources = mock_sources
        mock_client.chat = mock_chat
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        return mock_client

    @patch("src.youtube_summarizer._resolve_storage_path")
    @patch("src.youtube_summarizer.NotebookLMClient")
    def test_happy_path_returns_answer(self, mock_client_cls, mock_resolve) -> None:
        mock_resolve.return_value = ("/tmp/notebooklm/storage_state.json", False)
        mock_client = self._make_mock_client("video summary text")
        mock_client_cls.from_storage = AsyncMock(return_value=mock_client)

        result = summarize_youtube("https://youtu.be/abc", "Summarize this")

        self.assertEqual(result, "video summary text")
        mock_client.notebooks.create.assert_called_once_with("tldr-bot-temp")
        mock_client.sources.add_url.assert_called_once_with("notebook-id-1", "https://youtu.be/abc", wait=True)
        mock_client.chat.ask.assert_called_once_with("notebook-id-1", "Summarize this")
        mock_client.notebooks.delete.assert_called_once_with("notebook-id-1")

    @patch("src.youtube_summarizer._resolve_storage_path")
    @patch("src.youtube_summarizer.NotebookLMClient")
    def test_cleanup_failure_does_not_override_success(self, mock_client_cls, mock_resolve) -> None:
        mock_resolve.return_value = ("/tmp/notebooklm/storage_state.json", False)
        mock_client = self._make_mock_client("video summary text")
        mock_client.notebooks.delete = AsyncMock(side_effect=RuntimeError("cleanup failed"))
        mock_client_cls.from_storage = AsyncMock(return_value=mock_client)

        with self.assertLogs("src.youtube_summarizer", level="WARNING") as logs:
            result = summarize_youtube("https://youtu.be/abc", "Summarize this")

        self.assertEqual(result, "video summary text")
        mock_client.notebooks.delete.assert_called_once_with("notebook-id-1")
        self.assertTrue(any("cleanup failed" in line for line in logs.output))

    @patch("src.youtube_summarizer._resolve_storage_path")
    @patch("src.youtube_summarizer.NotebookLMClient")
    def test_temp_storage_file_removed_after_success(self, mock_client_cls, mock_resolve) -> None:
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            f.write(b"{}")
            tmppath = f.name

        mock_resolve.return_value = (tmppath, True)
        mock_client = self._make_mock_client("video summary text")
        mock_client_cls.from_storage = AsyncMock(return_value=mock_client)

        result = summarize_youtube("https://youtu.be/abc", "Summarize this")

        self.assertEqual(result, "video summary text")
        self.assertFalse(Path(tmppath).exists())

    @patch("src.youtube_summarizer._resolve_storage_path")
    @patch("src.youtube_summarizer.NotebookLMClient")
    def test_notebook_deleted_even_on_source_failure(self, mock_client_cls, mock_resolve) -> None:
        from notebooklm.exceptions import SourceAddError
        mock_resolve.return_value = ("/tmp/notebooklm/storage_state.json", False)
        mock_client = self._make_mock_client()
        mock_client.sources.add_url = AsyncMock(side_effect=SourceAddError("https://youtu.be/abc"))
        mock_client_cls.from_storage = AsyncMock(return_value=mock_client)

        with self.assertRaises(YouTubeSummaryError) as ctx:
            summarize_youtube("https://youtu.be/abc", "Summarize")

        self.assertEqual(ctx.exception.reason, YOUTUBE_SOURCE_FAILED)
        mock_client.notebooks.delete.assert_called_once_with("notebook-id-1")

    @patch("src.youtube_summarizer._resolve_storage_path")
    @patch("src.youtube_summarizer.NotebookLMClient")
    def test_empty_answer_raises_summary_failed(self, mock_client_cls, mock_resolve) -> None:
        mock_resolve.return_value = ("/tmp/notebooklm/storage_state.json", False)
        mock_client = self._make_mock_client(answer="")
        mock_client_cls.from_storage = AsyncMock(return_value=mock_client)

        with self.assertRaises(YouTubeSummaryError) as ctx:
            summarize_youtube("https://youtu.be/abc", "Summarize")

        self.assertEqual(ctx.exception.reason, YOUTUBE_SUMMARY_FAILED)
        mock_client.notebooks.delete.assert_called_once_with("notebook-id-1")

    @patch("src.youtube_summarizer._resolve_storage_path")
    @patch("src.youtube_summarizer.NotebookLMClient")
    def test_whitespace_answer_raises_summary_failed(self, mock_client_cls, mock_resolve) -> None:
        mock_resolve.return_value = ("/tmp/notebooklm/storage_state.json", False)
        mock_client = self._make_mock_client(answer="   \n\t")
        mock_client_cls.from_storage = AsyncMock(return_value=mock_client)

        with self.assertRaises(YouTubeSummaryError) as ctx:
            summarize_youtube("https://youtu.be/abc", "Summarize")

        self.assertEqual(ctx.exception.reason, YOUTUBE_SUMMARY_FAILED)
        mock_client.notebooks.delete.assert_called_once_with("notebook-id-1")

    @patch("src.youtube_summarizer._resolve_storage_path")
    @patch("src.youtube_summarizer.NotebookLMClient")
    def test_auth_error_raises_auth_expired(self, mock_client_cls, mock_resolve) -> None:
        from notebooklm.exceptions import AuthError
        mock_resolve.return_value = ("/tmp/notebooklm/storage_state.json", False)
        mock_client = self._make_mock_client()
        mock_client.__aenter__ = AsyncMock(side_effect=AuthError("session expired"))
        mock_client_cls.from_storage = AsyncMock(return_value=mock_client)

        with self.assertRaises(YouTubeSummaryError) as ctx:
            summarize_youtube("https://youtu.be/abc", "Summarize")

        self.assertEqual(ctx.exception.reason, YOUTUBE_AUTH_EXPIRED)


if __name__ == "__main__":
    unittest.main()
