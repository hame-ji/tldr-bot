import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.main import _run_pipeline_with_context


class PipelineIntegrationTests(unittest.TestCase):
    @patch("src.telegram_client._telegram_api")
    @patch("src.content_fetcher.requests.get")
    @patch("src.telegram_client.get_updates")
    def test_pipeline_end_to_end_with_article_url(
        self,
        mock_get_updates,
        mock_requests_get,
        mock_telegram_api,
    ) -> None:
        mock_get_updates.return_value = [
            {
                "update_id": 100,
                "message": {
                    "chat": {"id": 42},
                    "text": "https://example.com/article",
                },
            },
        ]

        mock_response = MagicMock()
        mock_response.text = "<html><body>" + "x" * 500 + "</body></html>"
        mock_response.headers = {"Content-Type": "text/html; charset=utf-8"}
        mock_response.raise_for_status.return_value = None
        mock_requests_get.return_value = mock_response

        mock_telegram_api.return_value = {"ok": True, "result": {"message_id": 1}}

        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"
            sources_dir = Path(tmpdir) / "sources"
            digests_dir = Path(tmpdir) / "digests"
            failed_dir = Path(tmpdir) / "failed"
            prompt_path = Path(tmpdir) / "digest.txt"
            prompt_path.write_text(
                "# Digest {{date}}\n\n{{summaries}}\n\n{{failed_urls_section}}\n",
                encoding="utf-8",
            )

            summary_path = sources_dir / "2026-03-15" / "article.md"
            summary_path.parent.mkdir(parents=True, exist_ok=True)
            summary_path.write_text("Test summary content", encoding="utf-8")

            def fake_summarize(items, run_date, diagnostics=None):
                if diagnostics is not None:
                    diagnostics.update({
                        "summary_ok_count": 1,
                        "summary_failed_count": 0,
                        "youtube_auth_failure_count": 0,
                        "notebooklm_auth_failure_count": 0,
                        "notebooklm_work_item_count": 0,
                        "notebooklm_preflight_status": "skipped",
                        "notebooklm_circuit_breaker_skipped_count": 0,
                        "replay_queued_count": 0,
                    })
                return [
                    {
                        "status": "ok",
                        "kind": "article",
                        "url": "https://example.com/article",
                        "summary_path": str(summary_path),
                    }
                ]

            with (
                patch("src.main.poll_urls_from_env") as mock_poll,
                patch("src.main.summarize_items", side_effect=fake_summarize),
                patch("src.main.generate_digest") as mock_digest,
                patch("src.main.send_digest_from_env") as mock_send,
            ):
                mock_poll.return_value = {
                    "urls": ["https://example.com/article"],
                    "update_count": 1,
                    "previous_offset": 99,
                    "next_offset": 101,
                }
                mock_digest.return_value = {
                    "digest_path": str(digests_dir / "2026-03-15.md"),
                    "digest_text": "# Digest\n\nTest summary content",
                }
                mock_send.return_value = [{"ok": True}]

                outcome, fetch_results, elapsed, run_date = _run_pipeline_with_context(
                    now=datetime(2026, 3, 15, tzinfo=timezone.utc),
                )

            self.assertEqual(outcome["processed_urls"], 1)
            self.assertEqual(outcome["summary_ok_count"], 1)
            self.assertEqual(outcome["summary_failed_count"], 0)
            self.assertTrue(outcome["digest_created"])
            self.assertEqual(outcome["digest_sent_chunks"], 1)
            self.assertEqual(run_date, "2026-03-15")

            self.assertEqual(len(fetch_results), 1)
            self.assertEqual(fetch_results[0]["status"], "ok")
            self.assertEqual(fetch_results[0]["kind"], "article")
            self.assertIn("content", fetch_results[0])


if __name__ == "__main__":
    unittest.main()
