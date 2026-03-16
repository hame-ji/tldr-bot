import unittest
from unittest.mock import MagicMock, patch

import requests

from src.x_content_fetcher import (
    X_CONTENT_UNAVAILABLE,
    X_INTERSTITIAL_DETECTED,
    X_LOW_SIGNAL_CONTENT,
    XContentError,
    fetch_x_text,
    parse_tweet_id,
)


def _response(payload: object, status_code: int = 200) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = payload
    return response


class XContentFetcherTests(unittest.TestCase):
    def test_parse_tweet_id_variants(self) -> None:
        self.assertEqual(parse_tweet_id("https://x.com/user/status/1234567890"), "1234567890")
        self.assertEqual(parse_tweet_id("https://twitter.com/user/status/1234567890?s=20"), "1234567890")
        self.assertEqual(parse_tweet_id("https://www.x.com/user/status/1234567890"), "1234567890")
        self.assertIsNone(parse_tweet_id("https://x.com/home"))
        self.assertIsNone(parse_tweet_id("https://example.com/user/status/1234567890"))

    def test_fetch_x_text_missing_tweet_id(self) -> None:
        with self.assertRaises(XContentError) as ctx:
            fetch_x_text("https://x.com/home")

        self.assertEqual(ctx.exception.reason, X_CONTENT_UNAVAILABLE)

    @patch("src.x_content_fetcher.requests.get")
    def test_fetch_x_text_syndication_success(self, mock_get) -> None:
        mock_get.return_value = _response({"text": "This is a substantive tweet about test automation and reliability."})

        text = fetch_x_text("https://x.com/user/status/1234567890")

        self.assertIn("substantive tweet", text)
        self.assertEqual(mock_get.call_count, 1)

    @patch("src.x_content_fetcher.requests.get")
    def test_fetch_x_text_falls_back_to_oembed(self, mock_get) -> None:
        mock_get.side_effect = [
            _response({}),
            _response(
                {
                    "author_name": "Alice",
                    "html": "<blockquote><p>Ship useful software every day with clear quality gates.</p></blockquote>",
                }
            ),
        ]

        text = fetch_x_text("https://x.com/user/status/1234567890")

        self.assertIn("Author: Alice", text)
        self.assertIn("Ship useful software", text)
        self.assertEqual(mock_get.call_count, 2)

    @patch("src.x_content_fetcher.requests.get")
    def test_fetch_x_text_interstitial_detected(self, mock_get) -> None:
        mock_get.side_effect = [
            _response({"text": "JavaScript is disabled in this browser. Please enable JavaScript."}),
            _response({"author_name": "Alice", "html": "<blockquote><p>https://t.co/abc</p></blockquote>"}),
        ]

        with self.assertRaises(XContentError) as ctx:
            fetch_x_text("https://x.com/user/status/1234567890")

        self.assertEqual(ctx.exception.reason, X_LOW_SIGNAL_CONTENT)

    @patch("src.x_content_fetcher.requests.get")
    def test_fetch_x_text_low_signal_content(self, mock_get) -> None:
        mock_get.side_effect = [
            _response({"text": "https://t.co/abc"}),
            _response({"author_name": "Alice", "html": "<blockquote><p>https://t.co/abc</p></blockquote>"}),
        ]

        with self.assertRaises(XContentError) as ctx:
            fetch_x_text("https://x.com/user/status/1234567890")

        self.assertEqual(ctx.exception.reason, X_LOW_SIGNAL_CONTENT)

    @patch("src.x_content_fetcher.requests.get")
    def test_fetch_x_text_content_unavailable(self, mock_get) -> None:
        mock_get.side_effect = [
            _response({}, status_code=404),
            _response({}, status_code=404),
        ]

        with self.assertRaises(XContentError) as ctx:
            fetch_x_text("https://x.com/user/status/1234567890")

        self.assertEqual(ctx.exception.reason, X_CONTENT_UNAVAILABLE)

    @patch("src.x_content_fetcher.requests.get")
    def test_fetch_x_text_interstitial_reason_survives(self, mock_get) -> None:
        mock_get.side_effect = [
            _response({}),
            _response({"author_name": "X", "html": "<blockquote><p>Enable JavaScript to view this content</p></blockquote>"}),
        ]

        with self.assertRaises(XContentError) as ctx:
            fetch_x_text("https://twitter.com/user/status/1234567890")

        self.assertEqual(ctx.exception.reason, X_INTERSTITIAL_DETECTED)

    @patch("src.x_content_fetcher.requests.get")
    def test_fetch_x_text_request_exception_becomes_content_unavailable(self, mock_get) -> None:
        mock_get.side_effect = requests.RequestException("boom")

        with self.assertRaises(XContentError) as ctx:
            fetch_x_text("https://twitter.com/user/status/1234567890")

        self.assertEqual(ctx.exception.reason, X_CONTENT_UNAVAILABLE)


if __name__ == "__main__":
    unittest.main()
