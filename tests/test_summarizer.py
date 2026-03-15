import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from src.summarizer import OpenRouterSummarizer, _source_output_path, summarize_item, summarize_items


class _FakeSummarizer:
    def summarize_article(self, url: str, content: str) -> str:
        return "article summary for " + url


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

    def test_summarize_item_ignores_non_article_ok_items(self) -> None:
        fake = _FakeSummarizer()

        result = summarize_item(
            item={"status": "ok", "kind": "youtube", "url": "https://youtu.be/abc"},
            summarizer=fake,
            run_date=date(2026, 3, 15),
        )

        self.assertEqual(result["status"], "ignored")
        self.assertEqual(result["kind"], "youtube")

    def test_summarize_item_writes_failure_record_on_exception(self) -> None:
        class _Broken:
            def summarize_article(self, url: str, content: str) -> str:
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

    def test_summarize_items_does_not_require_key_when_no_articles(self) -> None:
        old_key = os.environ.pop("OPENROUTER_API_KEY", None)
        try:
            results = summarize_items(
                items=[{"status": "ignored", "kind": "youtube", "url": "https://youtu.be/abc"}],
                run_date=date(2026, 3, 15),
            )
        finally:
            if old_key is not None:
                os.environ["OPENROUTER_API_KEY"] = old_key

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["status"], "ignored")

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
            )

    def test_openrouter_models_append_openrouter_free_fallback(self) -> None:
        summarizer = OpenRouterSummarizer(
            api_key="key",
            preferred_models=[
                "meta-llama/llama-3.3-70b-instruct:free",
                "nousresearch/hermes-3-llama-3.1-405b:free",
            ],
        )

        ordered = summarizer._models()

        self.assertEqual(
            ordered,
            [
                "meta-llama/llama-3.3-70b-instruct:free",
                "nousresearch/hermes-3-llama-3.1-405b:free",
                "openrouter/free",
            ],
        )

    def test_openrouter_models_dedupe_openrouter_free(self) -> None:
        summarizer = OpenRouterSummarizer(
            api_key="key",
            preferred_models=["openrouter/free", "meta-llama/llama-3.3-70b-instruct:free"],
        )

        ordered = summarizer._models()

        self.assertEqual(
            ordered,
            [
                "openrouter/free",
                "meta-llama/llama-3.3-70b-instruct:free",
            ],
        )


if __name__ == "__main__":
    unittest.main()
