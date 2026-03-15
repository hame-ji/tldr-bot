import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.telegram_client import extract_urls, load_offset, poll_urls, save_offset


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


if __name__ == "__main__":
    unittest.main()
