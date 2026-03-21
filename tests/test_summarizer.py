import contextlib
import os
import tempfile
import threading
import time
import unittest
from datetime import date
from pathlib import Path
from typing import Dict, Iterator, Optional
from unittest.mock import ANY, patch

from src.summarizer import (
    OpenRouterSummarizer,
    _clamp_concurrency,
    _order_models,
    _source_output_path,
    summarize_item,
    summarize_items,
)
from src.summarization.notebooklm_backend import YOUTUBE_AUTH_EXPIRED, YOUTUBE_SOURCE_FAILED, YouTubeSummaryError


@contextlib.contextmanager
def _override_env(overrides: Dict[str, str]) -> Iterator[None]:
    """Temporarily set environment variables, restoring originals on exit."""
    saved: Dict[str, Optional[str]] = {name: os.environ.get(name) for name in overrides}
    os.environ.update(overrides)
    try:
        yield
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


class _FakeSummarizer:
    def summarize_article(self, url: str, content: str) -> str:
        return "article summary for " + url

    def summarize_article_from_url(self, url: str) -> str:
        return "article fallback summary for " + url

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
        # Note: this test intentionally *removes* the key, so _override_env isn't a fit.
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["status"], "ok")

    @patch("src.summarizer.OpenRouterSummarizer")
    def test_summarize_items_uses_openrouter_env(self, mock_cls) -> None:
        fake = _FakeSummarizer()
        mock_cls.from_config.return_value =  fake

        with tempfile.TemporaryDirectory() as tmpdir:
            env = {
                "OPENROUTER_API_KEY": "openrouter-key",
                "OPENROUTER_API_BASE": "https://openrouter.ai/api/v1",
                "OPENROUTER_PREFERRED_MODELS": "model/a:free,model/b:free",
                "OPENROUTER_MIN_SPACING_SECONDS": "2",
                "OPENROUTER_MAX_RETRIES": "7",
                "OPENROUTER_INITIAL_BACKOFF_SECONDS": "6",
                "OPENROUTER_MAX_BACKOFF_SECONDS": "90",
                "OPENROUTER_MODELS_CACHE_PATH": str(Path(tmpdir) / "models.json"),
                "OPENROUTER_MODELS_CACHE_TTL_SECONDS": "123",
            }
            with _override_env(env):
                results = summarize_items(
                    items=[{"status": "ok", "kind": "article", "url": "https://example.com", "content": "hello"}],
                    run_date=date(2026, 3, 15),
                    sources_base_dir=tmpdir,
                    failed_base_dir=tmpdir,
                )

            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["status"], "ok")
            mock_cls.from_config.assert_called_once()
            config = mock_cls.from_config.call_args[0][0]
            self.assertEqual(config.api_key, "openrouter-key")
            self.assertEqual(config.base_url, "https://openrouter.ai/api/v1")
            self.assertEqual(config.preferred_models, ["model/a:free", "model/b:free"])
            self.assertAlmostEqual(config.min_spacing_seconds, 2.0)
            self.assertEqual(config.max_retries, 7)
            self.assertAlmostEqual(config.initial_backoff_seconds, 6.0)
            self.assertAlmostEqual(config.max_backoff_seconds, 90.0)
            self.assertEqual(config.models_cache_path, str(Path(tmpdir) / "models.json"))
            self.assertEqual(config.models_cache_ttl_seconds, 123)

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

        mock_openrouter_cls.from_config.return_value = _ArticleOnly()
        mock_summarize_youtube.return_value = "youtube via notebooklm"

        with tempfile.TemporaryDirectory() as tmpdir:
            with _override_env({"OPENROUTER_API_KEY": "key"}):
                results = summarize_items(
                    items=[
                        {"status": "ok", "kind": "article", "url": "https://example.com/a", "content": "body"},
                        {"status": "ok", "kind": "youtube", "url": "https://youtu.be/abc"},
                    ],
                    run_date=date(2026, 3, 15),
                    sources_base_dir=tmpdir,
                    failed_base_dir=tmpdir,
                )

            self.assertEqual(len(results), 2)
            self.assertEqual(results[0]["status"], "ok")
            self.assertEqual(results[0]["kind"], "article")
            self.assertEqual(results[1]["status"], "ok")
            self.assertEqual(results[1]["kind"], "youtube")
            mock_openrouter_cls.from_config.assert_called_once()
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

    @patch("src.summarizer.summarize_url_with_notebooklm")
    def test_failed_article_uses_notebooklm_fallback_by_default(self, mock_summarize_url) -> None:
        mock_summarize_url.return_value = "article fallback summary"

        with tempfile.TemporaryDirectory() as tmpdir:
            results = summarize_items(
                items=[
                    {
                        "status": "failed",
                        "kind": "article",
                        "url": "https://example.com/blocked",
                        "error": "403 Client Error",
                        "reason": "http_blocked",
                        "failure_path": str(Path(tmpdir) / "failed.md"),
                    }
                ],
                run_date=date(2026, 3, 15),
                sources_base_dir=tmpdir,
                failed_base_dir=tmpdir,
            )

        self.assertEqual(results[0]["status"], "ok")
        self.assertEqual(results[0]["kind"], "article")
        mock_summarize_url.assert_called_once_with(url="https://example.com/blocked", prompt=ANY)

    @patch("src.summarizer.summarize_url_with_notebooklm")
    def test_failed_article_fallback_can_be_disabled(self, mock_summarize_url) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, _override_env({"NOTEBOOKLM_ARTICLE_FALLBACK_ENABLED": "false"}):
            item = {
                "status": "failed",
                "kind": "article",
                "url": "https://example.com/blocked",
                "error": "403 Client Error",
                "reason": "http_blocked",
                "failure_path": str(Path(tmpdir) / "failed.md"),
            }
            results = summarize_items(
                items=[item],
                run_date=date(2026, 3, 15),
                sources_base_dir=tmpdir,
                failed_base_dir=tmpdir,
            )

        self.assertEqual(results[0]["status"], "failed")
        self.assertEqual(results[0]["url"], item["url"])
        mock_summarize_url.assert_not_called()


class ClampConcurrencyTests(unittest.TestCase):
    def test_default_when_env_unset(self) -> None:
        self.assertEqual(_clamp_concurrency("1", default=1, max_allowed=3), 1)

    def test_valid_value_within_range(self) -> None:
        self.assertEqual(_clamp_concurrency("2", default=1, max_allowed=3), 2)

    def test_clamps_above_max(self) -> None:
        self.assertEqual(_clamp_concurrency("10", default=1, max_allowed=3), 3)

    def test_clamps_below_min(self) -> None:
        self.assertEqual(_clamp_concurrency("0", default=1, max_allowed=3), 1)
        self.assertEqual(_clamp_concurrency("-5", default=1, max_allowed=3), 1)

    def test_non_numeric_uses_default(self) -> None:
        self.assertEqual(_clamp_concurrency("abc", default=2, max_allowed=3), 2)


class ConcurrencySummarizeItemsTests(unittest.TestCase):
    """Tests for dual-backend bounded concurrency in summarize_items."""

    @patch("src.summarizer.OpenRouterSummarizer")
    def test_default_sequential_single_article(self, mock_cls) -> None:
        """With default concurrency (1,1), a single article should still work."""
        fake = _FakeSummarizer()
        mock_cls.from_config.return_value = fake

        with tempfile.TemporaryDirectory() as tmpdir, _override_env({"OPENROUTER_API_KEY": "key"}):
            results = summarize_items(
                items=[{"status": "ok", "kind": "article", "url": "https://example.com/seq", "content": "body"}],
                run_date=date(2026, 3, 15),
                sources_base_dir=tmpdir,
                failed_base_dir=tmpdir,
            )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["status"], "ok")
        self.assertEqual(results[0]["kind"], "article")

    @patch("src.summarizer.summarize_youtube_with_notebooklm")
    @patch("src.summarizer.OpenRouterSummarizer")
    def test_concurrent_articles_and_youtube_run_in_parallel(self, mock_cls, mock_yt) -> None:
        """With concurrency > 1, articles and youtube should overlap."""
        call_log: list[tuple[str, float]] = []
        lock = threading.Lock()

        class _SlowArticle:
            def summarize_article(self, url: str, content: str) -> str:
                start = time.monotonic()
                time.sleep(0.05)
                with lock:
                    call_log.append(("article", start))
                return "article summary"

        mock_cls.from_config.return_value = _SlowArticle()

        def slow_youtube(url: str, prompt: str) -> str:
            start = time.monotonic()
            time.sleep(0.05)
            with lock:
                call_log.append(("youtube", start))
            return "youtube summary"

        mock_yt.side_effect = slow_youtube

        env_vars = {
            "OPENROUTER_API_KEY": "key",
            "OPENROUTER_MAX_CONCURRENCY": "2",
            "NOTEBOOKLM_MAX_CONCURRENCY": "2",
        }

        with tempfile.TemporaryDirectory() as tmpdir, _override_env(env_vars):
            results = summarize_items(
                items=[
                    {"status": "ok", "kind": "article", "url": "https://example.com/a1", "content": "body1"},
                    {"status": "ok", "kind": "youtube", "url": "https://youtu.be/v1"},
                    {"status": "ok", "kind": "article", "url": "https://example.com/a2", "content": "body2"},
                    {"status": "ok", "kind": "youtube", "url": "https://youtu.be/v2"},
                ],
                run_date=date(2026, 3, 15),
                sources_base_dir=tmpdir,
                failed_base_dir=tmpdir,
            )

        self.assertEqual(len(results), 4)
        self.assertTrue(all(r["status"] == "ok" for r in results))

        # With concurrency=2 per pool and 50ms sleep, the 2 articles overlap and
        # the 2 youtube items overlap. Cross-pool also overlaps. Total wall time
        # should be well under 4*50ms = 200ms sequential.
        article_starts = [t for kind, t in call_log if kind == "article"]
        youtube_starts = [t for kind, t in call_log if kind == "youtube"]
        self.assertEqual(len(article_starts), 2)
        self.assertEqual(len(youtube_starts), 2)

    @patch("src.summarizer.summarize_youtube_with_notebooklm")
    @patch("src.summarizer.OpenRouterSummarizer")
    def test_order_preservation_with_mixed_kinds(self, mock_cls, mock_yt) -> None:
        """Results must be returned in original input order regardless of completion order."""
        class _ArticleOnly:
            def summarize_article(self, url: str, content: str) -> str:
                return "article:" + url

        mock_cls.from_config.return_value = _ArticleOnly()
        mock_yt.return_value = "youtube summary"

        env_vars = {
            "OPENROUTER_API_KEY": "key",
            "OPENROUTER_MAX_CONCURRENCY": "3",
            "NOTEBOOKLM_MAX_CONCURRENCY": "3",
        }

        with tempfile.TemporaryDirectory() as tmpdir, _override_env(env_vars):
            items = [
                {"status": "ok", "kind": "youtube", "url": "https://youtu.be/first"},
                {"status": "ok", "kind": "article", "url": "https://example.com/second", "content": "b"},
                {"status": "ok", "kind": "youtube", "url": "https://youtu.be/third"},
                {"status": "ok", "kind": "article", "url": "https://example.com/fourth", "content": "d"},
                {"status": "failed", "kind": "article", "url": "https://example.com/fifth", "error": "e", "failure_path": "x"},
            ]
            results = summarize_items(
                items=items,
                run_date=date(2026, 3, 15),
                sources_base_dir=tmpdir,
                failed_base_dir=tmpdir,
            )

        self.assertEqual(len(results), 5)
        self.assertEqual(results[0]["kind"], "youtube")
        self.assertEqual(results[0]["url"], "https://youtu.be/first")
        self.assertEqual(results[1]["kind"], "article")
        self.assertEqual(results[1]["url"], "https://example.com/second")
        self.assertEqual(results[2]["kind"], "youtube")
        self.assertEqual(results[2]["url"], "https://youtu.be/third")
        self.assertEqual(results[3]["kind"], "article")
        self.assertEqual(results[3]["url"], "https://example.com/fourth")
        # The failed item passes through unchanged
        self.assertEqual(results[4]["status"], "failed")

    @patch("src.summarizer.summarize_youtube_with_notebooklm")
    @patch("src.summarizer.OpenRouterSummarizer")
    def test_failure_isolation_between_backends(self, mock_cls, mock_yt) -> None:
        """A YouTube failure must not affect article results, and vice versa."""
        class _WorkingArticle:
            def summarize_article(self, url: str, content: str) -> str:
                return "article ok"

        mock_cls.from_config.return_value = _WorkingArticle()
        mock_yt.side_effect = RuntimeError("notebooklm crashed")

        with tempfile.TemporaryDirectory() as tmpdir, _override_env({"OPENROUTER_API_KEY": "key"}):
            results = summarize_items(
                items=[
                    {"status": "ok", "kind": "article", "url": "https://example.com/good", "content": "body"},
                    {"status": "ok", "kind": "youtube", "url": "https://youtu.be/bad"},
                ],
                run_date=date(2026, 3, 15),
                sources_base_dir=tmpdir,
                failed_base_dir=tmpdir,
            )

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["status"], "ok")
        self.assertEqual(results[0]["kind"], "article")
        self.assertEqual(results[1]["status"], "failed")
        self.assertEqual(results[1]["kind"], "youtube")
        self.assertIn("notebooklm crashed", results[1]["error"])

    @patch("src.summarizer.summarize_youtube_with_notebooklm")
    @patch("src.summarizer.OpenRouterSummarizer")
    def test_failure_isolation_article_fails_youtube_succeeds(self, mock_cls, mock_yt) -> None:
        """Article failure must not affect YouTube results."""
        class _BrokenArticle:
            def summarize_article(self, url: str, content: str) -> str:
                raise RuntimeError("openrouter crashed")

        mock_cls.from_config.return_value = _BrokenArticle()
        mock_yt.return_value = "youtube ok"

        with tempfile.TemporaryDirectory() as tmpdir, _override_env({"OPENROUTER_API_KEY": "key"}):
            results = summarize_items(
                items=[
                    {"status": "ok", "kind": "youtube", "url": "https://youtu.be/good"},
                    {"status": "ok", "kind": "article", "url": "https://example.com/bad", "content": "body"},
                ],
                run_date=date(2026, 3, 15),
                sources_base_dir=tmpdir,
                failed_base_dir=tmpdir,
            )

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["status"], "ok")
        self.assertEqual(results[0]["kind"], "youtube")
        self.assertEqual(results[1]["status"], "failed")
        self.assertEqual(results[1]["kind"], "article")


class OpenRouterThreadSafetyTests(unittest.TestCase):
    """Verify concurrency protections in OpenRouterSummarizer."""

    def test_spacing_lock_preserves_min_gap_with_staggered_arrivals(self) -> None:
        summarizer = OpenRouterSummarizer.__new__(OpenRouterSummarizer)
        summarizer.min_spacing_seconds = 0.05
        summarizer._next_request_at = time.monotonic() + summarizer.min_spacing_seconds
        summarizer._spacing_lock = threading.Lock()
        summarizer._models_lock = threading.Lock()

        start_times: list[float] = []
        lock = threading.Lock()

        def worker(arrive_delay: float, work_delay: float) -> None:
            time.sleep(arrive_delay)
            summarizer._wait_for_min_spacing()
            with lock:
                start_times.append(time.monotonic())
            time.sleep(work_delay)

        threads = [
            threading.Thread(target=worker, args=(0.00, 0.01)),
            threading.Thread(target=worker, args=(0.001, 0.08)),
            threading.Thread(target=worker, args=(0.002, 0.08)),
            threading.Thread(target=worker, args=(0.07, 0.01)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        self.assertEqual(len(start_times), 4)

        ordered_starts = sorted(start_times)
        intervals = [ordered_starts[idx + 1] - ordered_starts[idx] for idx in range(len(ordered_starts) - 1)]
        min_interval = min(intervals)
        self.assertGreaterEqual(
            min_interval,
            0.045,
            f"Observed start interval {min_interval:.4f}s was below configured spacing",
        )

    def test_models_initialization_runs_once_under_concurrency(self) -> None:
        summarizer = OpenRouterSummarizer.__new__(OpenRouterSummarizer)
        summarizer._ordered_models = None
        summarizer._models_lock = threading.Lock()
        call_count = 0
        call_lock = threading.Lock()

        def discover() -> list[str]:
            nonlocal call_count
            with call_lock:
                call_count += 1
            time.sleep(0.02)
            return ["model/a:free"]

        summarizer._discover_free_models = discover  # type: ignore[method-assign]

        results: list[list[str]] = []
        results_lock = threading.Lock()

        def worker() -> None:
            models = summarizer._models()
            with results_lock:
                results.append(models)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        self.assertEqual(call_count, 1)
        self.assertEqual(len(results), 5)
        self.assertTrue(all(models == ["model/a:free"] for models in results))

    def test_spacing_lock_exists_on_new_instance(self) -> None:
        """A freshly constructed OpenRouterSummarizer must have concurrency locks."""
        s = OpenRouterSummarizer(api_key="test-key")
        self.assertIsInstance(s._spacing_lock, type(threading.Lock()))
        self.assertIsInstance(s._models_lock, type(threading.Lock()))


class SummarizeItemsTimeoutTests(unittest.TestCase):
    @patch("src.summarizer._FUTURE_TIMEOUT_SECONDS", 0.01)
    @patch("src.summarizer.summarize_item")
    @patch("src.summarizer.OpenRouterSummarizer")
    def test_timeout_isolated_to_single_item(self, mock_cls, mock_summarize_item) -> None:
        mock_cls.from_config.return_value = _FakeSummarizer()

        def summarize_side_effect(item, summarizer, run_date, sources_base_dir="data/sources", failed_base_dir="data/failed"):
            if item["url"].endswith("/slow"):
                time.sleep(0.05)
                return {"status": "ok", "kind": "article", "url": item["url"], "summary_path": "slow.md"}
            return {"status": "ok", "kind": item["kind"], "url": item["url"], "summary_path": "fast.md"}

        mock_summarize_item.side_effect = summarize_side_effect

        env_vars = {
            "OPENROUTER_API_KEY": "key",
            "OPENROUTER_MAX_CONCURRENCY": "2",
        }

        with tempfile.TemporaryDirectory() as tmpdir, _override_env(env_vars):
            results = summarize_items(
                items=[
                    {"status": "ok", "kind": "article", "url": "https://example.com/slow", "content": "body"},
                    {"status": "ok", "kind": "article", "url": "https://example.com/fast", "content": "body"},
                ],
                run_date=date(2026, 3, 15),
                sources_base_dir=tmpdir,
                failed_base_dir=tmpdir,
            )

            self.assertEqual(len(results), 2)
            self.assertEqual(results[0]["status"], "failed")
            self.assertEqual(results[0]["url"], "https://example.com/slow")
            self.assertIn("timed out", results[0]["error"])
            self.assertTrue(Path(results[0]["failure_path"]).exists())
            self.assertEqual(results[1]["status"], "ok")
            self.assertEqual(results[1]["url"], "https://example.com/fast")


if __name__ == "__main__":
    unittest.main()
