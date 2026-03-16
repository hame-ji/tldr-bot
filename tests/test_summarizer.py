import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import ANY, patch

from src.summarizer import _order_models, _source_output_path, summarize_item, summarize_items
from src.youtube_summarizer import YOUTUBE_AUTH_EXPIRED, YOUTUBE_SOURCE_FAILED, YouTubeSummaryError


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

    def test_summarize_item_writes_source_file_for_youtube(self) -> None:
        fake = _FakeSummarizer()

        with tempfile.TemporaryDirectory() as tmpdir:
            result = summarize_item(
                item={"status": "ok", "kind": "youtube", "url": "https://youtu.be/abc"},
                summarizer=fake,
                run_date=date(2026, 3, 15),
                sources_base_dir=tmpdir,
            )

            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["kind"], "youtube")
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

    @patch("src.summarizer.summarize_youtube_with_notebooklm")
    def test_summarize_items_does_not_require_key_when_no_articles(self, mock_summarize_youtube) -> None:
        mock_summarize_youtube.return_value = "youtube summary"
        old_key = os.environ.pop("OPENROUTER_API_KEY", None)
        try:
            results = summarize_items(
                items=[{"status": "ok", "kind": "youtube", "url": "https://youtu.be/abc"}],
                run_date=date(2026, 3, 15),
            )
        finally:
            if old_key is not None:
                os.environ["OPENROUTER_API_KEY"] = old_key

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["status"], "ok")

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
                    items=[{"status": "ok", "kind": "article", "url": "https://example.com", "content": "hello"}],
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

    @patch("src.summarizer.summarize_youtube_with_notebooklm")
    @patch("src.summarizer.OpenRouterSummarizer")
    def test_summarize_items_routes_mixed_batch_by_kind(self, mock_openrouter_cls, mock_summarize_youtube) -> None:
        class _ArticleOnly:
            def summarize_article(self, url: str, content: str) -> str:
                return "article via openrouter"

        mock_openrouter_cls.return_value = _ArticleOnly()
        mock_summarize_youtube.return_value = "youtube via notebooklm"

        previous_key = os.environ.get("OPENROUTER_API_KEY")
        os.environ["OPENROUTER_API_KEY"] = "key"

        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                results = summarize_items(
                    items=[
                        {"status": "ok", "kind": "article", "url": "https://example.com/a", "content": "body"},
                        {"status": "ok", "kind": "youtube", "url": "https://youtu.be/abc"},
                    ],
                    run_date=date(2026, 3, 15),
                    sources_base_dir=tmpdir,
                    failed_base_dir=tmpdir,
                )
            finally:
                if previous_key is None:
                    os.environ.pop("OPENROUTER_API_KEY", None)
                else:
                    os.environ["OPENROUTER_API_KEY"] = previous_key

            self.assertEqual(len(results), 2)
            self.assertEqual(results[0]["status"], "ok")
            self.assertEqual(results[0]["kind"], "article")
            self.assertEqual(results[1]["status"], "ok")
            self.assertEqual(results[1]["kind"], "youtube")
            mock_openrouter_cls.assert_called_once()
            mock_summarize_youtube.assert_called_once_with(url="https://youtu.be/abc", prompt=ANY)

    @patch("src.summarizer.summarize_youtube_with_notebooklm")
    def test_summarize_items_youtube_auth_failure_writes_failure(self, mock_summarize_youtube) -> None:
        mock_summarize_youtube.side_effect = YouTubeSummaryError(YOUTUBE_AUTH_EXPIRED, "session expired")

        with tempfile.TemporaryDirectory() as tmpdir:
            results = summarize_items(
                items=[{"status": "ok", "kind": "youtube", "url": "https://youtu.be/auth"}],
                run_date=date(2026, 3, 15),
                sources_base_dir=tmpdir,
                failed_base_dir=tmpdir,
            )

            self.assertEqual(results[0]["status"], "failed")
            self.assertEqual(results[0]["kind"], "youtube")
            self.assertIn(YOUTUBE_AUTH_EXPIRED, results[0]["error"])
            self.assertTrue(Path(results[0]["failure_path"]).exists())

    @patch("src.summarizer.summarize_youtube_with_notebooklm")
    def test_summarize_items_youtube_source_failure_writes_failure(self, mock_summarize_youtube) -> None:
        mock_summarize_youtube.side_effect = YouTubeSummaryError(YOUTUBE_SOURCE_FAILED, "processing failed")

        with tempfile.TemporaryDirectory() as tmpdir:
            results = summarize_items(
                items=[{"status": "ok", "kind": "youtube", "url": "https://youtu.be/source"}],
                run_date=date(2026, 3, 15),
                sources_base_dir=tmpdir,
                failed_base_dir=tmpdir,
            )

            self.assertEqual(results[0]["status"], "failed")
            self.assertEqual(results[0]["kind"], "youtube")
            self.assertIn(YOUTUBE_SOURCE_FAILED, results[0]["error"])
            self.assertTrue(Path(results[0]["failure_path"]).exists())


if __name__ == "__main__":
    unittest.main()
