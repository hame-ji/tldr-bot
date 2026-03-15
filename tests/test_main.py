import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from src.main import run_pipeline


class MainPipelineOutcomeTests(unittest.TestCase):
    @patch("src.main.send_digest_from_env")
    @patch("src.main.generate_digest")
    @patch("src.main.summarize_items")
    @patch("src.main.fetch_urls")
    @patch("src.main.poll_urls_from_env")
    def test_run_pipeline_returns_empty_day_outcome(
        self,
        mock_poll_urls_from_env,
        mock_fetch_urls,
        mock_summarize_items,
        mock_generate_digest,
        mock_send_digest_from_env,
    ) -> None:
        mock_poll_urls_from_env.return_value = {
            "urls": [],
            "update_count": 0,
            "previous_offset": 12,
            "next_offset": 12,
        }

        outcome = run_pipeline(now=datetime(2026, 3, 15, tzinfo=timezone.utc))

        self.assertEqual(outcome["processed_urls"], 0)
        self.assertEqual(outcome["digest_created"], False)
        self.assertEqual(outcome["digest_sent_chunks"], 0)
        mock_fetch_urls.assert_not_called()
        mock_summarize_items.assert_not_called()
        mock_generate_digest.assert_not_called()
        mock_send_digest_from_env.assert_not_called()

    @patch("src.main.send_digest_from_env")
    @patch("src.main.generate_digest")
    @patch("src.main.summarize_items")
    @patch("src.main.fetch_urls")
    @patch("src.main.poll_urls_from_env")
    def test_run_pipeline_returns_non_empty_outcome(
        self,
        mock_poll_urls_from_env,
        mock_fetch_urls,
        mock_summarize_items,
        mock_generate_digest,
        mock_send_digest_from_env,
    ) -> None:
        mock_poll_urls_from_env.return_value = {
            "urls": ["https://one.example", "https://two.example"],
            "update_count": 2,
            "previous_offset": 10,
            "next_offset": 12,
        }
        mock_fetch_urls.return_value = [
            {"status": "ok", "kind": "article", "url": "https://one.example", "content": "Body"},
            {"status": "ignored", "kind": "youtube", "url": "https://two.example"},
        ]
        mock_summarize_items.return_value = [
            {
                "status": "ok",
                "kind": "article",
                "url": "https://one.example",
                "summary_path": "data/sources/2026-03-15/one.md",
            },
            {"status": "ignored", "kind": "youtube", "url": "https://two.example"},
        ]
        mock_generate_digest.return_value = {
            "digest_path": "data/digests/2026-03-15.md",
            "digest_text": "digest body",
        }
        mock_send_digest_from_env.return_value = [{"ok": True}, {"ok": True}]

        outcome = run_pipeline(now=datetime(2026, 3, 15, tzinfo=timezone.utc))

        self.assertEqual(outcome["processed_urls"], 1)
        self.assertEqual(outcome["summary_ok_count"], 1)
        self.assertEqual(outcome["summary_failed_count"], 0)
        self.assertEqual(outcome["digest_created"], True)
        self.assertEqual(outcome["digest_path"], "data/digests/2026-03-15.md")
        self.assertEqual(outcome["digest_sent_chunks"], 2)

    @patch("src.main.send_digest_from_env")
    @patch("src.main.generate_digest")
    @patch("src.main.summarize_items")
    @patch("src.main.fetch_urls")
    @patch("src.main.poll_urls_from_env")
    def test_run_pipeline_skips_when_only_ignored_urls(
        self,
        mock_poll_urls_from_env,
        mock_fetch_urls,
        mock_summarize_items,
        mock_generate_digest,
        mock_send_digest_from_env,
    ) -> None:
        mock_poll_urls_from_env.return_value = {
            "urls": ["https://youtu.be/abc"],
            "update_count": 1,
            "previous_offset": 10,
            "next_offset": 11,
        }
        mock_fetch_urls.return_value = [
            {"status": "ignored", "kind": "youtube", "url": "https://youtu.be/abc"},
        ]

        outcome = run_pipeline(now=datetime(2026, 3, 15, tzinfo=timezone.utc))

        self.assertEqual(outcome["processed_urls"], 0)
        self.assertEqual(outcome["digest_created"], False)
        mock_summarize_items.assert_not_called()
        mock_generate_digest.assert_not_called()
        mock_send_digest_from_env.assert_not_called()


class MainEntryPointTests(unittest.TestCase):
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
