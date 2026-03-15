import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from src.summarizer import _source_output_path, summarize_item, summarize_items


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
                raise RuntimeError("429 rate limited")

            def summarize_youtube(self, url: str) -> str:
                raise RuntimeError("429 rate limited")

        broken = _Broken()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = summarize_item(
                item={"status": "ok", "kind": "article", "url": "https://example.com/x", "content": "body"},
                summarizer=broken,
                run_date=date(2026, 3, 15),
                failed_base_dir=tmpdir,
            )
            self.assertEqual(result["status"], "failed")
            self.assertTrue(Path(result["failure_path"]).exists())

    @patch("src.summarizer.GeminiSummarizer")
    def test_summarize_items_uses_env_key_and_model(self, mock_cls) -> None:
        fake = _FakeSummarizer()
        mock_cls.return_value = fake
        with tempfile.TemporaryDirectory() as tmpdir:
            old_key = os.environ.get("GEMINI_API_KEY")
            old_model = os.environ.get("GEMINI_MODEL")
            old_spacing = os.environ.get("GEMINI_MIN_SPACING_SECONDS")
            old_retries = os.environ.get("GEMINI_MAX_RETRIES")
            old_initial_backoff = os.environ.get("GEMINI_INITIAL_BACKOFF_SECONDS")
            old_max_backoff = os.environ.get("GEMINI_MAX_BACKOFF_SECONDS")
            old_fallback_models = os.environ.get("GEMINI_FALLBACK_MODELS")
            os.environ["GEMINI_API_KEY"] = "test-key"
            os.environ["GEMINI_MODEL"] = "gemini-2.5-flash"
            os.environ["GEMINI_FALLBACK_MODELS"] = "gemini-2.5-flash-lite"
            os.environ["GEMINI_MIN_SPACING_SECONDS"] = "1"
            os.environ["GEMINI_MAX_RETRIES"] = "6"
            os.environ["GEMINI_INITIAL_BACKOFF_SECONDS"] = "5"
            os.environ["GEMINI_MAX_BACKOFF_SECONDS"] = "120"
            try:
                results = summarize_items(
                    items=[{"status": "ok", "kind": "youtube", "url": "https://youtu.be/abc"}],
                    run_date=date(2026, 3, 15),
                    sources_base_dir=tmpdir,
                    failed_base_dir=tmpdir,
                )
            finally:
                if old_key is None:
                    os.environ.pop("GEMINI_API_KEY", None)
                else:
                    os.environ["GEMINI_API_KEY"] = old_key
                if old_model is None:
                    os.environ.pop("GEMINI_MODEL", None)
                else:
                    os.environ["GEMINI_MODEL"] = old_model
                if old_spacing is None:
                    os.environ.pop("GEMINI_MIN_SPACING_SECONDS", None)
                else:
                    os.environ["GEMINI_MIN_SPACING_SECONDS"] = old_spacing
                if old_retries is None:
                    os.environ.pop("GEMINI_MAX_RETRIES", None)
                else:
                    os.environ["GEMINI_MAX_RETRIES"] = old_retries
                if old_initial_backoff is None:
                    os.environ.pop("GEMINI_INITIAL_BACKOFF_SECONDS", None)
                else:
                    os.environ["GEMINI_INITIAL_BACKOFF_SECONDS"] = old_initial_backoff
                if old_max_backoff is None:
                    os.environ.pop("GEMINI_MAX_BACKOFF_SECONDS", None)
                else:
                    os.environ["GEMINI_MAX_BACKOFF_SECONDS"] = old_max_backoff
                if old_fallback_models is None:
                    os.environ.pop("GEMINI_FALLBACK_MODELS", None)
                else:
                    os.environ["GEMINI_FALLBACK_MODELS"] = old_fallback_models

            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["status"], "ok")
            mock_cls.assert_called_once_with(
                api_key="test-key",
                model="gemini-2.5-flash",
                fallback_models=["gemini-2.5-flash-lite"],
                min_spacing_seconds=1.0,
                max_retries=6,
                initial_backoff_seconds=5.0,
                max_backoff_seconds=120.0,
            )


if __name__ == "__main__":
    unittest.main()
