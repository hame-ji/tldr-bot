import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from requests import HTTPError, Response
from requests.exceptions import SSLError

from src.content_fetcher import (
    ARTICLE_EXTRACT_TOO_SHORT,
    HTTP_BLOCKED,
    PDF_EXTRACT_FAILED,
    REQUEST_HEADERS,
    TLS_ERROR,
    classify_url,
    fetch_url,
    normalize_url_for_fetch,
    url_to_slug,
    write_failure_record,
)


class ContentFetcherTests(unittest.TestCase):
    def test_classify_youtube_urls(self) -> None:
        self.assertEqual(classify_url("https://www.youtube.com/watch?v=abc"), "youtube")
        self.assertEqual(classify_url("https://youtu.be/abc"), "youtube")
        self.assertEqual(classify_url("https://example.com/article"), "article")

    def test_fetch_url_youtube_is_marked_summarizable(self) -> None:
        result = fetch_url("https://youtu.be/abc")

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["kind"], "youtube")

    def test_url_to_slug_includes_youtube_video_identifier(self) -> None:
        slug_a = url_to_slug("https://www.youtube.com/watch?v=abc")
        slug_b = url_to_slug("https://www.youtube.com/watch?v=def")
        short = url_to_slug("https://youtu.be/xyz")

        self.assertNotEqual(slug_a, slug_b)
        self.assertIn("abc", slug_a)
        self.assertIn("xyz", short)

    def test_normalize_url_for_fetch_strips_fragment(self) -> None:
        url = "https://example.com/article#:~:text=excerpt"
        self.assertEqual(normalize_url_for_fetch(url), "https://example.com/article")

    @patch("src.content_fetcher.trafilatura.extract")
    @patch("src.content_fetcher.requests.get")
    def test_fetch_url_article_uses_timeout_and_extract(self, mock_get, mock_extract) -> None:
        mock_response = MagicMock()
        mock_response.text = "<html>content</html>"
        mock_response.headers = {"Content-Type": "text/html; charset=utf-8"}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        mock_extract.return_value = "x" * 250

        result = fetch_url("https://example.com/article#:~:text=excerpt")

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["kind"], "article")
        self.assertIn("content", result)
        mock_get.assert_called_once_with(
            "https://example.com/article",
            timeout=(10, 30),
            headers=REQUEST_HEADERS,
        )

    @patch("src.content_fetcher._extract_pdf_text")
    @patch("src.content_fetcher.requests.get")
    def test_fetch_url_article_detects_pdf_by_content_type(self, mock_get, mock_extract_pdf) -> None:
        mock_response = MagicMock()
        mock_response.content = b"%PDF-1.7 fake"
        mock_response.headers = {"Content-Type": "application/pdf"}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        mock_extract_pdf.return_value = "pdf body " * 40

        result = fetch_url("https://arxiv.org/pdf/2602.20021")

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["kind"], "article")
        mock_extract_pdf.assert_called_once_with(b"%PDF-1.7 fake")

    @patch("src.content_fetcher.fetch_article_text")
    def test_fetch_url_writes_failure_record_on_error(self, mock_fetch_article_text) -> None:
        mock_fetch_article_text.side_effect = RuntimeError("timeout")

        with tempfile.TemporaryDirectory() as tmpdir:
            result = fetch_url("https://example.com/fail", failed_base_dir=tmpdir)

            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["reason"], "network_error")
            self.assertIn("failure_path", result)
            self.assertTrue(Path(result["failure_path"]).exists())

    @patch("src.content_fetcher.fetch_article_text")
    def test_fetch_url_classifies_tls_failures(self, mock_fetch_article_text) -> None:
        mock_fetch_article_text.side_effect = SSLError("certificate verify failed")

        with tempfile.TemporaryDirectory() as tmpdir:
            result = fetch_url("https://example.com/tls", failed_base_dir=tmpdir)

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["reason"], TLS_ERROR)

    @patch("src.content_fetcher.fetch_article_text")
    def test_fetch_url_classifies_http_blocked_failures(self, mock_fetch_article_text) -> None:
        response = Response()
        response.status_code = 403
        error = HTTPError("403 Client Error", response=response)
        mock_fetch_article_text.side_effect = error

        with tempfile.TemporaryDirectory() as tmpdir:
            result = fetch_url("https://example.com/blocked", failed_base_dir=tmpdir)

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["reason"], HTTP_BLOCKED)

    def test_write_failure_record_path_structure(self) -> None:
        now = datetime(2026, 3, 15, 10, 30, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = write_failure_record(
                url="https://example.com/a/b",
                error="forbidden",
                base_dir=tmpdir,
                now=now,
                reason=ARTICLE_EXTRACT_TOO_SHORT,
            )
            self.assertIn("2026-03-15", str(path))
            content = path.read_text(encoding="utf-8")
            self.assertIn("forbidden", content)
            self.assertIn("https://example.com/a/b", content)
            self.assertIn(ARTICLE_EXTRACT_TOO_SHORT, content)

    @patch("src.content_fetcher.PdfReader")
    @patch("src.content_fetcher.requests.get")
    def test_extract_pdf_failure_is_classified(self, mock_get, mock_reader) -> None:
        mock_response = MagicMock()
        mock_response.content = b"%PDF-1.7 fake"
        mock_response.headers = {"Content-Type": "application/pdf"}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        mock_reader.side_effect = RuntimeError("bad pdf")

        with tempfile.TemporaryDirectory() as tmpdir:
            result = fetch_url("https://example.com/report.pdf", failed_base_dir=tmpdir)

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["reason"], PDF_EXTRACT_FAILED)


if __name__ == "__main__":
    unittest.main()
