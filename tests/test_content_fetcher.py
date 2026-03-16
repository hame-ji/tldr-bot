import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.content_fetcher import classify_url, fetch_url, write_failure_record
from src.x_content_fetcher import XContentError, X_LOW_SIGNAL_CONTENT


class ContentFetcherTests(unittest.TestCase):
    def test_classify_youtube_urls(self) -> None:
        self.assertEqual(classify_url("https://www.youtube.com/watch?v=abc"), "youtube")
        self.assertEqual(classify_url("https://youtu.be/abc"), "youtube")
        self.assertEqual(classify_url("https://example.com/article"), "article")

    def test_classify_x_urls(self) -> None:
        self.assertEqual(classify_url("https://x.com/user/status/123"), "x_post")
        self.assertEqual(classify_url("https://twitter.com/user/status/123"), "x_post")

    def test_fetch_url_youtube_is_ignored(self) -> None:
        result = fetch_url("https://youtu.be/abc")

        self.assertEqual(result["status"], "ignored")
        self.assertEqual(result["kind"], "youtube")

    @patch("src.content_fetcher.trafilatura.extract")
    @patch("src.content_fetcher.requests.get")
    def test_fetch_url_article_uses_timeout_and_extract(self, mock_get, mock_extract) -> None:
        mock_response = MagicMock()
        mock_response.text = "<html>content</html>"
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        mock_extract.return_value = "x" * 250

        result = fetch_url("https://example.com/article")

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["kind"], "article")
        self.assertIn("content", result)
        mock_get.assert_called_once_with("https://example.com/article", timeout=(10, 30))

    @patch("src.content_fetcher.fetch_article_text")
    def test_fetch_url_writes_failure_record_on_error(self, mock_fetch_article_text) -> None:
        mock_fetch_article_text.side_effect = RuntimeError("timeout")

        with tempfile.TemporaryDirectory() as tmpdir:
            result = fetch_url("https://example.com/fail", failed_base_dir=tmpdir)

            self.assertEqual(result["status"], "failed")
            self.assertIn("failure_path", result)
            self.assertTrue(Path(result["failure_path"]).exists())

    @patch("src.content_fetcher.fetch_x_text")
    def test_fetch_url_x_post_routes_to_x_fetcher(self, mock_fetch_x_text) -> None:
        mock_fetch_x_text.return_value = "substantive tweet text"

        result = fetch_url("https://x.com/user/status/123")

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["kind"], "article")
        self.assertIn("content", result)
        mock_fetch_x_text.assert_called_once_with("https://x.com/user/status/123")

    @patch("src.content_fetcher.fetch_x_text")
    def test_fetch_url_x_post_failure_is_failed_with_record(self, mock_fetch_x_text) -> None:
        mock_fetch_x_text.side_effect = XContentError(X_LOW_SIGNAL_CONTENT, "link-only")

        with tempfile.TemporaryDirectory() as tmpdir:
            result = fetch_url("https://x.com/user/status/123", failed_base_dir=tmpdir)

            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["kind"], "article")
            self.assertIn(X_LOW_SIGNAL_CONTENT, result["error"])
            self.assertTrue(Path(result["failure_path"]).exists())

    def test_write_failure_record_path_structure(self) -> None:
        now = datetime(2026, 3, 15, 10, 30, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = write_failure_record(
                url="https://example.com/a/b",
                error="forbidden",
                base_dir=tmpdir,
                now=now,
            )
            self.assertIn("2026-03-15", str(path))
            content = path.read_text(encoding="utf-8")
            self.assertIn("forbidden", content)
            self.assertIn("https://example.com/a/b", content)


if __name__ == "__main__":
    unittest.main()
