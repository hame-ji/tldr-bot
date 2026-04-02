import io
import json
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from unittest.mock import patch

from src.main import run_pipeline


def _mock_summarize_items(results, diag=None):
    """Create a side_effect for summarize_items that populates diagnostics."""
    def _side_effect(*args, **kwargs):
        diagnostics = kwargs.get("diagnostics")
        if diagnostics is not None and diag:
            diagnostics.update(diag)
        return results
    return _side_effect


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
            {"status": "ok", "kind": "youtube", "url": "https://two.example"},
        ]
        mock_summarize_items.side_effect = _mock_summarize_items(
            results=[
                {
                    "status": "ok",
                    "kind": "article",
                    "url": "https://one.example",
                    "summary_path": "data/sources/2026-03-15/one.md",
                },
                {
                    "status": "ok",
                    "kind": "youtube",
                    "url": "https://two.example",
                    "summary_path": "data/sources/2026-03-15/two.md",
                },
            ],
            diag={
                "summary_ok_count": 2,
                "summary_failed_count": 0,
                "youtube_auth_failure_count": 0,
                "notebooklm_auth_failure_count": 0,
                "notebooklm_work_item_count": 1,
                "notebooklm_preflight_status": "skipped",
            },
        )
        mock_generate_digest.return_value = {
            "digest_path": "data/digests/2026-03-15.md",
            "digest_text": "digest body",
        }
        mock_send_digest_from_env.return_value = [{"ok": True}, {"ok": True}]

        outcome = run_pipeline(now=datetime(2026, 3, 15, tzinfo=timezone.utc))

        self.assertEqual(outcome["processed_urls"], 2)
        self.assertEqual(outcome["summary_ok_count"], 2)
        self.assertEqual(outcome["summary_failed_count"], 0)
        self.assertEqual(outcome["digest_created"], True)
        self.assertEqual(outcome["digest_path"], "data/digests/2026-03-15.md")
        self.assertEqual(outcome["digest_sent_chunks"], 2)

    @patch("src.main.send_digest_from_env")
    @patch("src.main.generate_digest")
    @patch("src.main.summarize_items")
    @patch("src.main.fetch_urls")
    @patch("src.main.poll_urls_from_env")
    def test_run_pipeline_counts_failed_article_items(
        self,
        mock_poll_urls_from_env,
        mock_fetch_urls,
        mock_summarize_items,
        mock_generate_digest,
        mock_send_digest_from_env,
    ) -> None:
        mock_poll_urls_from_env.return_value = {
            "urls": ["https://x.com/user/status/123"],
            "update_count": 1,
            "previous_offset": 10,
            "next_offset": 11,
        }
        mock_fetch_urls.return_value = [
            {
                "status": "failed",
                "kind": "article",
                "url": "https://x.com/user/status/123",
                "error": "x_low_signal_content",
                "failure_path": "data/failed/2026-03-15/x.md",
            }
        ]
        mock_summarize_items.side_effect = _mock_summarize_items(
            results=[
                {
                    "status": "failed",
                    "kind": "article",
                    "url": "https://x.com/user/status/123",
                    "error": "x_low_signal_content",
                    "failure_path": "data/failed/2026-03-15/x.md",
                }
            ],
            diag={
                "summary_ok_count": 0,
                "summary_failed_count": 1,
                "youtube_auth_failure_count": 0,
                "notebooklm_auth_failure_count": 0,
                "notebooklm_work_item_count": 0,
                "notebooklm_preflight_status": "skipped",
            },
        )
        mock_generate_digest.return_value = {
            "digest_path": "data/digests/2026-03-15.md",
            "digest_text": "digest body",
        }
        mock_send_digest_from_env.return_value = [{"ok": True}]

        outcome = run_pipeline(now=datetime(2026, 3, 15, tzinfo=timezone.utc))

        self.assertEqual(outcome["processed_urls"], 1)
        self.assertEqual(outcome["summary_ok_count"], 0)
        self.assertEqual(outcome["summary_failed_count"], 1)
        self.assertEqual(outcome["digest_created"], True)

    @patch("src.main.send_digest_from_env")
    @patch("src.main.generate_digest")
    @patch("src.main.summarize_items")
    @patch("src.main.fetch_urls")
    @patch("src.main.poll_urls_from_env")
    def test_run_pipeline_counts_mixed_article_and_youtube_failures(
        self,
        mock_poll_urls_from_env,
        mock_fetch_urls,
        mock_summarize_items,
        mock_generate_digest,
        mock_send_digest_from_env,
    ) -> None:
        mock_poll_urls_from_env.return_value = {
            "urls": ["https://one.example", "https://youtu.be/xyz"],
            "update_count": 2,
            "previous_offset": 10,
            "next_offset": 12,
        }
        mock_fetch_urls.return_value = [
            {"status": "ok", "kind": "article", "url": "https://one.example", "content": "Body"},
            {"status": "ok", "kind": "youtube", "url": "https://youtu.be/xyz"},
        ]
        mock_summarize_items.side_effect = _mock_summarize_items(
            results=[
                {
                    "status": "ok",
                    "kind": "article",
                    "url": "https://one.example",
                    "summary_path": "data/sources/2026-03-15/one.md",
                },
                {
                    "status": "failed",
                    "kind": "youtube",
                    "url": "https://youtu.be/xyz",
                    "error": "youtube_auth_expired",
                    "failure_path": "data/failed/2026-03-15/xyz.md",
                },
            ],
            diag={
                "summary_ok_count": 1,
                "summary_failed_count": 1,
                "youtube_auth_failure_count": 1,
                "notebooklm_auth_failure_count": 1,
                "notebooklm_work_item_count": 1,
                "notebooklm_preflight_status": "skipped",
            },
        )
        mock_generate_digest.return_value = {
            "digest_path": "data/digests/2026-03-15.md",
            "digest_text": "digest body",
        }
        mock_send_digest_from_env.return_value = [{"ok": True}]

        outcome = run_pipeline(now=datetime(2026, 3, 15, tzinfo=timezone.utc))

        self.assertEqual(outcome["processed_urls"], 2)
        self.assertEqual(outcome["summary_ok_count"], 1)
        self.assertEqual(outcome["summary_failed_count"], 1)

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
            "urls": ["https://example.com/unsupported"],
            "update_count": 1,
            "previous_offset": 10,
            "next_offset": 11,
        }
        mock_fetch_urls.return_value = [
            {"status": "ignored", "kind": "unknown", "url": "https://example.com/unsupported"},
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

        stdout = io.StringIO()
        with redirect_stdout(stdout):
            main()

        mock_fetch_urls.assert_not_called()
        mock_summarize_items.assert_not_called()
        mock_generate_digest.assert_not_called()
        mock_send_digest_from_env.assert_not_called()

        lines = stdout.getvalue().splitlines()
        run_outcome_lines = [line for line in lines if line.startswith("run_outcome:")]
        run_metrics_lines = [line for line in lines if line.startswith("run_metrics:")]

        self.assertEqual(len(run_outcome_lines), 1)
        self.assertEqual(len(run_metrics_lines), 1)

        outcome_payload = json.loads(run_outcome_lines[0].split("run_outcome:", 1)[1].strip())
        metrics_payload = json.loads(run_metrics_lines[0].split("run_metrics:", 1)[1].strip())
        self.assertEqual(outcome_payload["processed_urls"], 0)
        self.assertEqual(metrics_payload["metrics_version"], 1)
        self.assertEqual(metrics_payload["processed_urls"], 0)
        self.assertIsNone(metrics_payload["seconds_per_processed_url"])


if __name__ == "__main__":
    unittest.main()
