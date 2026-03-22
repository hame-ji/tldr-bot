import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.telegram_client import chunk_text_by_paragraph, extract_urls, load_offset, poll_urls, save_offset, send_digest


class TelegramClientTests(unittest.TestCase):
    def test_extract_urls_with_surrounding_text(self) -> None:
        text = "check this out https://example.com/path?a=1 good stuff"
        self.assertEqual(extract_urls(text), ["https://example.com/path?a=1"])

    def test_extract_urls_trims_trailing_punctuation(self) -> None:
        text = "Links: https://a.example/test, https://b.example/ok.)"
        self.assertEqual(
            extract_urls(text),
            ["https://a.example/test", "https://b.example/ok"],
        )

    def test_state_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"
            self.assertIsNone(load_offset(state_path))
            save_offset(538711799, state_path)
            self.assertEqual(load_offset(state_path), 538711799)

    @patch("src.telegram_client.get_updates")
    def test_poll_urls_advances_offset_plus_one(self, mock_get_updates) -> None:
        mock_get_updates.return_value = [
            {
                "update_id": 10,
                "message": {
                    "chat": {"id": 1},
                    "text": "https://one.example",
                },
            },
            {
                "update_id": 12,
                "message": {
                    "chat": {"id": 1},
                    "text": "https://two.example",
                },
            },
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"
            result = poll_urls("token", allowed_chat_id=1, state_path=state_path)

            self.assertEqual(result["previous_offset"], None)
            self.assertEqual(result["next_offset"], 13)
            self.assertEqual(result["urls"], ["https://one.example", "https://two.example"])
            state_data = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(state_data["telegram_offset"], 13)

    @patch("src.telegram_client.get_updates")
    def test_poll_urls_filters_by_chat_id(self, mock_get_updates) -> None:
        mock_get_updates.return_value = [
            {
                "update_id": 20,
                "message": {
                    "chat": {"id": 99},
                    "text": "https://skip.example",
                },
            },
            {
                "update_id": 21,
                "message": {
                    "chat": {"id": 42},
                    "text": "https://keep.example",
                },
            },
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"
            result = poll_urls("token", allowed_chat_id=42, state_path=state_path)

            self.assertEqual(result["urls"], ["https://keep.example"])
            self.assertEqual(load_offset(state_path), 22)

    def test_chunk_text_by_paragraph_preserves_boundaries(self) -> None:
        first = "A" * 2000
        second = "B" * 2000
        third = "C" * 2000
        text = "\n\n".join([first, second, third])

        chunks = chunk_text_by_paragraph(text, max_length=4096)

        self.assertEqual(len(chunks), 2)
        self.assertIn(first, chunks[0])
        self.assertIn(second, chunks[0])
        self.assertIn(third, chunks[1])
        self.assertTrue(all(len(chunk) <= 4096 for chunk in chunks))

    def test_chunk_text_by_paragraph_splits_oversized_paragraph(self) -> None:
        text = "X" * 5000

        chunks = chunk_text_by_paragraph(text, max_length=4096)

        self.assertEqual(len(chunks), 2)
        self.assertTrue(all(len(chunk) <= 4096 for chunk in chunks))

    @patch("src.telegram_client._telegram_api")
    def test_send_digest_targets_configured_chat(self, mock_api) -> None:
        mock_api.return_value = {"ok": True, "result": {"message_id": 1}}

        send_digest(bot_token="token", chat_id=123, digest_text="hello")

        self.assertEqual(mock_api.call_count, 1)
        _, method, body = mock_api.call_args[0]
        self.assertEqual(method, "sendMessage")
        self.assertEqual(body["chat_id"], 123)
        self.assertEqual(body["parse_mode"], "HTML")

    @patch("src.telegram_client._telegram_api")
    def test_send_digest_formats_markdownish_text_for_html_parse_mode(self, mock_api) -> None:
        mock_api.return_value = {"ok": True, "result": {"message_id": 1}}
        digest_text = (
            "## Item 1\n\n"
            "URL: [example](https://example.com/path(with)parens)\n\n"
            "**Title:** A & B\n"
            "* **Action:** do it"
        )

        send_digest(bot_token="token", chat_id=123, digest_text=digest_text)

        body = mock_api.call_args[0][2]
        self.assertIn("<b>Item 1</b>", body["text"])
        self.assertIn('<a href="https://example.com/path(with)parens">example</a>', body["text"])
        self.assertIn("<b>Title:</b> A &amp; B", body["text"])
        self.assertIn("• <b>Action:</b> do it", body["text"])
        self.assertNotIn("##", body["text"])
        self.assertNotIn("**", body["text"])

    @patch("src.telegram_client._telegram_api")
    def test_send_digest_starts_new_message_for_each_item_section(self, mock_api) -> None:
        mock_api.return_value = {"ok": True, "result": {"message_id": 1}}
        digest_text = (
            "# Daily Research Digest - 2026-03-22\n\n"
            "Processed: 2 successful, 0 failed, 0 ignored\n\n"
            "## Item 1\n\n"
            "URL: https://example.com/one\n\n"
            "First item text\n\n"
            "## Item 2\n\n"
            "URL: https://example.com/two\n\n"
            "Second item text"
        )

        send_digest(bot_token="token", chat_id=123, digest_text=digest_text, max_chunk_length=4096)

        self.assertEqual(mock_api.call_count, 3)
        sent_texts = [call.args[2]["text"] for call in mock_api.call_args_list]
        self.assertIn("<b>Daily Research Digest - 2026-03-22</b>", sent_texts[0])
        self.assertIn("<b>Item 1</b>", sent_texts[1])
        self.assertIn("<b>Item 2</b>", sent_texts[2])

    @patch("src.telegram_client._telegram_api")
    def test_send_digest_splits_large_item_but_keeps_next_item_boundary(self, mock_api) -> None:
        mock_api.return_value = {"ok": True, "result": {"message_id": 1}}
        long_text = "X" * 250
        digest_text = (
            "## Item 1\n\n"
            f"{long_text}\n\n"
            "## Item 2\n\n"
            "Short"
        )

        send_digest(bot_token="token", chat_id=123, digest_text=digest_text, max_chunk_length=120)

        self.assertGreaterEqual(mock_api.call_count, 3)
        sent_texts = [call.args[2]["text"] for call in mock_api.call_args_list]
        self.assertIn("<b>Item 1</b>", sent_texts[0])
        self.assertIn("<b>Item 2</b>", sent_texts[-1])
        self.assertNotIn("<b>Item 2</b>", "\n".join(sent_texts[:-1]))


if __name__ == "__main__":
    unittest.main()
