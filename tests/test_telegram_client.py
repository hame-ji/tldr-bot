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

    @patch("src.telegram_client._telegram_api_get")
    def test_send_digest_targets_configured_chat(self, mock_api_get) -> None:
        mock_api_get.return_value = {"ok": True, "result": {"message_id": 1}}

        send_digest(bot_token="token", chat_id=123, digest_text="hello")

        self.assertEqual(mock_api_get.call_count, 1)
        _, method, params = mock_api_get.call_args[0]
        self.assertEqual(method, "sendMessage")
        self.assertEqual(params["chat_id"], 123)
        self.assertEqual(params["parse_mode"], "HTML")


class MainEmptyDayTests(unittest.TestCase):
    @patch("src.main.send_digest_from_env")
    @patch("src.main.generate_digest")
    @patch("src.main.summarize_items")
    @patch("src.main.fetch_urls")
    @patch("src.main.poll_urls_from_env")
    def test_main_skips_digest_generation_when_no_urls(
        self,
        mock_poll_urls_from_env,
        mock_fetch_urls,
        mock_summarize_items,
        mock_generate_digest,
        mock_send_digest_from_env,
    ) -> None:
        from src.main import main

        mock_poll_urls_from_env.return_value = {
            "urls": [],
            "update_count": 0,
            "previous_offset": 12,
            "next_offset": 12,
        }

        main()

        mock_fetch_urls.assert_not_called()
        mock_summarize_items.assert_not_called()
        mock_generate_digest.assert_not_called()
        mock_send_digest_from_env.assert_not_called()


if __name__ == "__main__":
    unittest.main()
