import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.summarizer import (
    _extract_youtube_video_id,
    _fetch_youtube_transcript,
    _order_models,
    _source_output_path,
    summarize_item,
    summarize_items,
)


class _FakeSummarizer:
    def summarize_article(self, url: str, content: str) -> str:
        return "article summary for " + url

    def summarize_youtube(self, url: str) -> str:
        return "youtube summary for " + url


class SummarizerTests(unittest.TestCase):
    def test_source_output_path_uses_date_and_slug(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = _source_output_path("https://example.com/a/b", date(2026, 3, 15), base_dir=tmpdir)
            self.assertIn("2026-03-15", str(path))
            self.assertTrue(path.name.endswith(".md"))

    def test_summarize_item_writes_source_file_for_article(self) -> None:
        fake = _FakeSummarizer()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = summarize_item(
                item={"status": "ok", "kind": "article", "url": "https://example.com/x", "content": "body"},
                summarizer=fake,
                run_date=date(2026, 3, 15),
                sources_base_dir=tmpdir,
            )
            self.assertEqual(result["status"], "ok")
            self.assertTrue(Path(result["summary_path"]).exists())

    def test_summarize_item_writes_failure_record_on_exception(self) -> None:
        class _Broken:
            def summarize_article(self, url: str, content: str) -> str:
                raise RuntimeError("provider error")

            def summarize_youtube(self, url: str) -> str:
                raise RuntimeError("provider error")

        with tempfile.TemporaryDirectory() as tmpdir:
            result = summarize_item(
                item={"status": "ok", "kind": "article", "url": "https://example.com/x", "content": "body"},
                summarizer=_Broken(),
                run_date=date(2026, 3, 15),
                failed_base_dir=tmpdir,
            )
            self.assertEqual(result["status"], "failed")
            self.assertTrue(Path(result["failure_path"]).exists())

    @patch("src.summarizer.OpenRouterSummarizer")
    def test_summarize_items_uses_openrouter_env(self, mock_cls) -> None:
        fake = _FakeSummarizer()
        mock_cls.return_value = fake

        old_env = {
            name: os.environ.get(name)
            for name in [
                "OPENROUTER_API_KEY",
                "OPENROUTER_API_BASE",
                "OPENROUTER_PREFERRED_MODELS",
                "OPENROUTER_MIN_SPACING_SECONDS",
                "OPENROUTER_MAX_RETRIES",
                "OPENROUTER_INITIAL_BACKOFF_SECONDS",
                "OPENROUTER_MAX_BACKOFF_SECONDS",
                "OPENROUTER_MODELS_CACHE_PATH",
                "OPENROUTER_MODELS_CACHE_TTL_SECONDS",
            ]
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            os.environ["OPENROUTER_API_KEY"] = "openrouter-key"
            os.environ["OPENROUTER_API_BASE"] = "https://openrouter.ai/api/v1"
            os.environ["OPENROUTER_PREFERRED_MODELS"] = "model/a:free,model/b:free"
            os.environ["OPENROUTER_MIN_SPACING_SECONDS"] = "2"
            os.environ["OPENROUTER_MAX_RETRIES"] = "7"
            os.environ["OPENROUTER_INITIAL_BACKOFF_SECONDS"] = "6"
            os.environ["OPENROUTER_MAX_BACKOFF_SECONDS"] = "90"
            os.environ["OPENROUTER_MODELS_CACHE_PATH"] = str(Path(tmpdir) / "models.json")
            os.environ["OPENROUTER_MODELS_CACHE_TTL_SECONDS"] = "123"

            try:
                results = summarize_items(
                    items=[{"status": "ok", "kind": "youtube", "url": "https://youtu.be/abc"}],
                    run_date=date(2026, 3, 15),
                    sources_base_dir=tmpdir,
                    failed_base_dir=tmpdir,
                )
            finally:
                for name, value in old_env.items():
                    if value is None:
                        os.environ.pop(name, None)
                    else:
                        os.environ[name] = value

            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["status"], "ok")
            mock_cls.assert_called_once_with(
                api_key="openrouter-key",
                base_url="https://openrouter.ai/api/v1",
                preferred_models=["model/a:free", "model/b:free"],
                min_spacing_seconds=2.0,
                max_retries=7,
                initial_backoff_seconds=6.0,
                max_backoff_seconds=90.0,
                models_cache_path=str(Path(tmpdir) / "models.json"),
                models_cache_ttl_seconds=123,
            )

    def test_extract_youtube_video_id_from_multiple_formats(self) -> None:
        self.assertEqual(_extract_youtube_video_id("https://youtu.be/abc123"), "abc123")
        self.assertEqual(_extract_youtube_video_id("https://www.youtube.com/watch?v=xyz789"), "xyz789")
        self.assertEqual(_extract_youtube_video_id("https://www.youtube.com/shorts/short42"), "short42")
        self.assertIsNone(_extract_youtube_video_id("https://example.com/video"))

    @patch("src.summarizer.YouTubeTranscriptApi")
    def test_fetch_youtube_transcript_uses_fetch_api(self, mock_api_cls) -> None:
        snippet_a = MagicMock()
        snippet_a.text = "Hello"
        snippet_a.start = 12.2
        snippet_b = MagicMock()
        snippet_b.text = "World"
        snippet_b.start = 15.7

        instance = mock_api_cls.return_value
        instance.fetch.return_value = [snippet_a, snippet_b]

        transcript = _fetch_youtube_transcript("https://youtu.be/abc123")

        self.assertIn("[00:12] Hello", transcript)
        self.assertIn("[00:15] World", transcript)

    @patch("src.summarizer.YouTubeTranscriptApi")
    def test_fetch_youtube_transcript_raises_when_unavailable(self, mock_api_cls) -> None:
        instance = mock_api_cls.return_value
        instance.fetch.side_effect = RuntimeError("No transcripts")

        with self.assertRaises(RuntimeError):
            _fetch_youtube_transcript("https://youtu.be/abc123")

    def test_order_models_prefers_user_picks_then_quality(self) -> None:
        models = [
            {"id": "vendor/basic-model", "context_length": 4096, "pricing": {"prompt": "0", "completion": "0"}},
            {"id": "vendor/pro-model:free", "context_length": 32768},
            {"id": "vendor/paid-model", "context_length": 32768, "pricing": {"prompt": "0.1", "completion": "0.1"}},
        ]

        ordered = _order_models(models, preferred_models=["vendor/basic-model"])

        self.assertEqual(ordered[0], "vendor/basic-model")
        self.assertIn("vendor/pro-model:free", ordered)
        self.assertNotIn("vendor/paid-model", ordered)


if __name__ == "__main__":
    unittest.main()
