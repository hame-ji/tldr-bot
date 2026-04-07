from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from scripts.replay_notebooklm_failures import run_replay
from src.summarization.replay_queue import (
    append_completed_record,
    enqueue_notebooklm_auth_failure,
    load_pending_records,
)


class ReplayQueueTests(unittest.TestCase):
    def test_enqueue_auth_failure_writes_pending_record_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            first = enqueue_notebooklm_auth_failure(
                run_date=date(2026, 4, 1),
                url="https://youtu.be/abc",
                kind="youtube",
                reason="youtube_auth_expired",
                source_failure_path="data/failed/2026-04-01/abc.md",
                base_dir=tmpdir,
            )
            duplicate = enqueue_notebooklm_auth_failure(
                run_date=date(2026, 4, 1),
                url="https://youtu.be/abc",
                kind="youtube",
                reason="youtube_auth_expired",
                source_failure_path="data/failed/2026-04-01/abc.md",
                base_dir=tmpdir,
            )

            grouped = load_pending_records(base_dir=tmpdir)
            records = list(grouped.values())[0]
            self.assertTrue(first)
            self.assertFalse(duplicate)
            self.assertEqual(len(records), 1)

    def test_append_completed_record_writes_completed_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            append_completed_record(
                {
                    "url": "https://youtu.be/xyz",
                    "kind": "youtube",
                    "reason": "youtube_auth_expired",
                },
                base_dir=tmpdir,
            )
            completed_dir = Path(tmpdir) / "completed"
            files = list(completed_dir.glob("*.jsonl"))
            self.assertEqual(len(files), 1)
            text = files[0].read_text(encoding="utf-8")
            self.assertIn("recovered_at", text)


class ReplayRunnerTests(unittest.TestCase):
    @patch("scripts.replay_notebooklm_failures.summarize_youtube")
    @patch("scripts.replay_notebooklm_failures.load_prompt")
    @patch("scripts.replay_notebooklm_failures.notebooklm_config_from_env")
    def test_run_replay_recovers_pending_item(
        self,
        mock_notebooklm_config,
        mock_load_prompt,
        mock_summarize_youtube,
    ) -> None:
        class _Cfg:
            youtube_prompt_path = "prompts/youtube_summarize.txt"
            article_fallback_prompt_path = "prompts/summarize.txt"

        mock_notebooklm_config.return_value = _Cfg()
        mock_load_prompt.return_value = "prompt"
        mock_summarize_youtube.return_value = "summary"

        with tempfile.TemporaryDirectory() as tmpdir:
            enqueue_notebooklm_auth_failure(
                run_date=date(2026, 4, 1),
                url="https://youtu.be/recover",
                kind="youtube",
                reason="youtube_auth_expired",
                source_failure_path="data/failed/2026-04-01/recover.md",
                base_dir=tmpdir,
            )

            outcome = run_replay(
                limit=0,
                base_dir=tmpdir,
                sources_base_dir=str(Path(tmpdir) / "sources"),
            )

            self.assertEqual(outcome["replay_attempted_count"], 1)
            self.assertEqual(outcome["replay_recovered_count"], 1)
            self.assertEqual(outcome["replay_pending_remaining_count"], 0)

    @patch("scripts.replay_notebooklm_failures.summarize_youtube")
    @patch("scripts.replay_notebooklm_failures.load_prompt")
    @patch("scripts.replay_notebooklm_failures.notebooklm_config_from_env")
    def test_run_replay_keeps_failed_item_pending_with_incremented_attempt(
        self,
        mock_notebooklm_config,
        mock_load_prompt,
        mock_summarize_youtube,
    ) -> None:
        class _Cfg:
            youtube_prompt_path = "prompts/youtube_summarize.txt"
            article_fallback_prompt_path = "prompts/summarize.txt"

        mock_notebooklm_config.return_value = _Cfg()
        mock_load_prompt.return_value = "prompt"
        mock_summarize_youtube.side_effect = RuntimeError("auth still broken")

        with tempfile.TemporaryDirectory() as tmpdir:
            enqueue_notebooklm_auth_failure(
                run_date=date(2026, 4, 1),
                url="https://youtu.be/fail",
                kind="youtube",
                reason="youtube_auth_expired",
                source_failure_path="data/failed/2026-04-01/fail.md",
                base_dir=tmpdir,
            )

            outcome = run_replay(
                limit=0,
                base_dir=tmpdir,
                sources_base_dir=str(Path(tmpdir) / "sources"),
            )

            self.assertEqual(outcome["replay_attempted_count"], 1)
            self.assertEqual(outcome["replay_recovered_count"], 0)
            self.assertEqual(outcome["replay_pending_remaining_count"], 1)

    @patch("scripts.replay_notebooklm_failures.summarize_youtube")
    @patch("scripts.replay_notebooklm_failures.load_prompt")
    @patch("scripts.replay_notebooklm_failures.notebooklm_config_from_env")
    def test_run_replay_uses_pending_file_date_for_source_path(
        self,
        mock_notebooklm_config,
        mock_load_prompt,
        mock_summarize_youtube,
    ) -> None:
        class _Cfg:
            youtube_prompt_path = "prompts/youtube_summarize.txt"
            article_fallback_prompt_path = "prompts/summarize.txt"

        mock_notebooklm_config.return_value = _Cfg()
        mock_load_prompt.return_value = "prompt"
        mock_summarize_youtube.return_value = "summary"

        with tempfile.TemporaryDirectory() as tmpdir:
            enqueue_notebooklm_auth_failure(
                run_date=date(2026, 4, 1),
                url="https://youtu.be/dated",
                kind="youtube",
                reason="youtube_auth_expired",
                source_failure_path="data/failed/2026-04-01/dated.md",
                base_dir=tmpdir,
            )

            sources_dir = Path(tmpdir) / "sources"
            outcome = run_replay(
                limit=0,
                base_dir=tmpdir,
                sources_base_dir=str(sources_dir),
            )

            self.assertEqual(outcome["replay_recovered_count"], 1)
            source_files = list(sources_dir.rglob("*.md"))
            self.assertTrue(
                any("2026-04-01" in str(p) for p in source_files),
                f"Expected source under 2026-04-01 dir, got: {source_files}",
            )

    @patch("scripts.replay_notebooklm_failures.summarize_youtube")
    @patch("scripts.replay_notebooklm_failures.load_prompt")
    @patch("scripts.replay_notebooklm_failures.notebooklm_config_from_env")
    @patch("scripts.replay_notebooklm_failures._source_output_path")
    def test_run_replay_keeps_record_pending_on_persistence_failure(
        self,
        mock_source_path,
        mock_notebooklm_config,
        mock_load_prompt,
        mock_summarize_youtube,
    ) -> None:
        class _Cfg:
            youtube_prompt_path = "prompts/youtube_summarize.txt"
            article_fallback_prompt_path = "prompts/summarize.txt"

        mock_notebooklm_config.return_value = _Cfg()
        mock_load_prompt.return_value = "prompt"
        mock_summarize_youtube.return_value = "recovered summary"
        mock_source_path.side_effect = OSError("disk full")

        with tempfile.TemporaryDirectory() as tmpdir:
            enqueue_notebooklm_auth_failure(
                run_date=date(2026, 4, 1),
                url="https://youtu.be/persist-fail",
                kind="youtube",
                reason="youtube_auth_expired",
                source_failure_path="data/failed/2026-04-01/persist-fail.md",
                base_dir=tmpdir,
            )

            outcome = run_replay(
                limit=0,
                base_dir=tmpdir,
                sources_base_dir=str(Path(tmpdir) / "sources"),
            )

            self.assertEqual(outcome["replay_attempted_count"], 1)
            self.assertEqual(outcome["replay_recovered_count"], 0)
            self.assertEqual(outcome["replay_pending_remaining_count"], 1)
            grouped = load_pending_records(base_dir=tmpdir)
            all_records = [r for rs in grouped.values() for r in rs]
            self.assertEqual(len(all_records), 1)
            self.assertEqual(all_records[0]["attempt_count"], 1)
            self.assertIn("disk full", all_records[0]["last_error"])

    @patch("scripts.replay_notebooklm_failures.summarize_youtube")
    @patch("scripts.replay_notebooklm_failures.load_prompt")
    @patch("scripts.replay_notebooklm_failures.notebooklm_config_from_env")
    def test_run_replay_skips_malformed_pending_filename(
        self,
        mock_notebooklm_config,
        mock_load_prompt,
        mock_summarize_youtube,
    ) -> None:
        class _Cfg:
            youtube_prompt_path = "prompts/youtube_summarize.txt"
            article_fallback_prompt_path = "prompts/summarize.txt"

        mock_notebooklm_config.return_value = _Cfg()
        mock_load_prompt.return_value = "prompt"
        mock_summarize_youtube.return_value = "summary"

        with tempfile.TemporaryDirectory() as tmpdir:
            enqueue_notebooklm_auth_failure(
                run_date=date(2026, 4, 1),
                url="https://youtu.be/recover",
                kind="youtube",
                reason="youtube_auth_expired",
                source_failure_path="data/failed/2026-04-01/recover.md",
                base_dir=tmpdir,
            )
            malformed_path = Path(tmpdir) / "pending" / "not-a-date.jsonl"
            malformed_path.parent.mkdir(parents=True, exist_ok=True)
            malformed_path.write_text('{"url": "https://youtu.be/bad"}\n', encoding="utf-8")

            outcome = run_replay(
                limit=0,
                base_dir=tmpdir,
                sources_base_dir=str(Path(tmpdir) / "sources"),
            )

            self.assertEqual(outcome["replay_attempted_count"], 1)
            self.assertEqual(outcome["replay_recovered_count"], 1)
            self.assertEqual(outcome["replay_pending_remaining_count"], 1)
            self.assertTrue(malformed_path.exists())


if __name__ == "__main__":
    unittest.main()
