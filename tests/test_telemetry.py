import json
import unittest

from src.telemetry.pipeline_log_parser import extract_pipeline_outputs
from src.telemetry.run_metrics import RunMetrics, build_run_metrics, to_log_line


class RunMetricsTests(unittest.TestCase):
    def test_build_run_metrics_computes_expected_fields(self) -> None:
        fetch_results = [
            {"status": "ok", "kind": "article", "url": "https://article.example"},
            {"status": "ok", "kind": "youtube", "url": "https://youtu.be/abc"},
            {"status": "failed", "kind": "article", "url": "https://failed.example"},
            {"status": "ignored", "kind": "unknown", "url": "https://ignored.example"},
        ]
        outcome = {
            "processed_urls": 3,
            "summary_ok_count": 2,
            "summary_failed_count": 1,
            "youtube_auth_failure_count": 1,
            "notebooklm_auth_failure_count": 1,
            "notebooklm_work_item_count": 2,
            "notebooklm_preflight_status": "ok",
            "notebooklm_circuit_breaker_skipped_count": 1,
            "replay_queued_count": 1,
            "digest_created": True,
            "digest_path": "data/digests/2026-03-20.md",
            "digest_sent_chunks": 1,
        }

        metrics = build_run_metrics(
            digest_date="2026-03-20",
            fetch_results=fetch_results,
            outcome=outcome,
            pipeline_seconds=120.0,
        )

        self.assertEqual(metrics.metrics_version, 1)
        self.assertEqual(metrics.digest_date, "2026-03-20")
        self.assertEqual(metrics.processed_urls, 3)
        self.assertEqual(metrics.summary_ok_count, 2)
        self.assertEqual(metrics.summary_failed_count, 1)
        self.assertEqual(metrics.fetch_ok_article_count, 1)
        self.assertEqual(metrics.fetch_ok_youtube_count, 1)
        self.assertEqual(metrics.fetch_failed_count, 1)
        self.assertEqual(metrics.notebooklm_work_item_count, 2)
        self.assertEqual(metrics.notebooklm_preflight_status, "ok")
        self.assertEqual(metrics.notebooklm_circuit_breaker_skipped_count, 1)
        self.assertEqual(metrics.youtube_auth_failure_count, 1)
        self.assertEqual(metrics.notebooklm_auth_failure_count, 1)
        self.assertEqual(metrics.replay_queued_count, 1)
        self.assertEqual(metrics.pipeline_seconds, 120.0)
        self.assertEqual(metrics.seconds_per_processed_url, 40.0)

    def test_build_run_metrics_seconds_per_processed_url_is_none_when_no_processed_urls(
        self,
    ) -> None:
        metrics = build_run_metrics(
            digest_date="2026-03-20",
            fetch_results=[],
            outcome={
                "processed_urls": 0,
                "summary_ok_count": 0,
                "summary_failed_count": 0,
                "youtube_auth_failure_count": 0,
                "notebooklm_auth_failure_count": 0,
                "notebooklm_work_item_count": 0,
                "notebooklm_preflight_status": "skipped",
                "notebooklm_circuit_breaker_skipped_count": 0,
                "replay_queued_count": 0,
                "digest_created": False,
                "digest_path": "",
                "digest_sent_chunks": 0,
            },
            pipeline_seconds=10.0,
        )

        self.assertIsNone(metrics.seconds_per_processed_url)

    def test_to_log_line_uses_stable_prefix_and_json(self) -> None:
        metrics = RunMetrics(
            metrics_version=1,
            digest_date="2026-03-20",
            processed_urls=2,
            summary_ok_count=2,
            summary_failed_count=0,
            fetch_ok_article_count=1,
            fetch_ok_youtube_count=1,
            fetch_failed_count=0,
            notebooklm_work_item_count=1,
            notebooklm_preflight_status="ok",
            notebooklm_circuit_breaker_skipped_count=0,
            youtube_auth_failure_count=0,
            notebooklm_auth_failure_count=0,
            replay_queued_count=0,
            pipeline_seconds=42.5,
            seconds_per_processed_url=21.25,
        )

        line = to_log_line(metrics)
        self.assertTrue(line.startswith("run_metrics:"))
        payload = json.loads(line.split("run_metrics:", 1)[1])
        self.assertEqual(payload["metrics_version"], 1)
        self.assertEqual(payload["pipeline_seconds"], 42.5)


class PipelineLogParserTests(unittest.TestCase):
    def test_extract_pipeline_outputs_prefers_run_metrics_when_present(self) -> None:
        log_text = "\n".join(
            [
                "some log line",
                'run_outcome:{"processed_urls": 2, "summary_ok_count": 2, "summary_failed_count": 0, "digest_created": true, "digest_path": "data/digests/2026-03-20.md", "digest_sent_chunks": 1}',
                'run_metrics:{"metrics_version": 1, "digest_date": "2026-03-20", "processed_urls": 2, "summary_ok_count": 2, "summary_failed_count": 0, "fetch_ok_article_count": 1, "fetch_ok_youtube_count": 1, "fetch_failed_count": 0, "notebooklm_work_item_count": 1, "notebooklm_preflight_status": "ok", "notebooklm_circuit_breaker_skipped_count": 0, "youtube_auth_failure_count": 0, "notebooklm_auth_failure_count": 0, "replay_queued_count": 0, "pipeline_seconds": 64.2, "seconds_per_processed_url": 32.1}',
            ]
        )

        outputs = extract_pipeline_outputs(log_text)
        self.assertEqual(outputs["processed_urls"], "2")
        self.assertEqual(outputs["digest_created"], "true")
        self.assertEqual(outputs["digest_date"], "2026-03-20")
        self.assertEqual(outputs["pipeline_seconds"], "64.200")
        self.assertEqual(outputs["seconds_per_processed_url"], "32.100")
        self.assertEqual(outputs["fetch_ok_article_count"], "1")
        self.assertEqual(outputs["fetch_ok_youtube_count"], "1")
        self.assertEqual(outputs["fetch_failed_count"], "0")
        self.assertEqual(outputs["notebooklm_preflight_status"], "ok")
        self.assertEqual(outputs["notebooklm_auth_failure_count"], "0")
        self.assertEqual(outputs["notebooklm_auth_incident"], "false")
        self.assertEqual(outputs["notebooklm_circuit_breaker_skipped_count"], "0")
        self.assertEqual(outputs["replay_queued_count"], "0")

    def test_extract_pipeline_outputs_supports_outcome_only_fallback(self) -> None:
        log_text = (
            'run_outcome:{"processed_urls": 0, "summary_ok_count": 0, "summary_failed_count": 0, '
            '"digest_created": false, "digest_path": "", "digest_sent_chunks": 0}'
        )

        outputs = extract_pipeline_outputs(log_text)
        self.assertEqual(outputs["processed_urls"], "0")
        self.assertEqual(outputs["digest_created"], "false")
        self.assertEqual(outputs["digest_date"], "unknown")
        self.assertEqual(outputs["pipeline_seconds"], "unknown")
        self.assertEqual(outputs["seconds_per_processed_url"], "unknown")
        self.assertEqual(outputs["notebooklm_preflight_status"], "unknown")
        self.assertEqual(outputs["notebooklm_auth_failure_count"], "unknown")
        self.assertEqual(outputs["notebooklm_auth_incident"], "unknown")
        self.assertEqual(outputs["notebooklm_circuit_breaker_skipped_count"], "unknown")
        self.assertEqual(outputs["replay_queued_count"], "unknown")

    def test_extract_pipeline_outputs_raises_when_run_outcome_missing(self) -> None:
        with self.assertRaises(RuntimeError):
            extract_pipeline_outputs("run_metrics:{}")

    def test_extract_pipeline_outputs_handles_malformed_run_metrics_payload(
        self,
    ) -> None:
        log_text = "\n".join(
            [
                'run_outcome:{"processed_urls": 2, "summary_ok_count": 2, "summary_failed_count": 0, "digest_created": true, "digest_path": "data/digests/2026-03-20.md", "digest_sent_chunks": 1}',
                "run_metrics:{bad json",
            ]
        )

        outputs = extract_pipeline_outputs(log_text)
        self.assertEqual(outputs["processed_urls"], "2")
        self.assertEqual(outputs["digest_created"], "true")
        self.assertEqual(outputs["digest_date"], "unknown")
        self.assertEqual(outputs["pipeline_seconds"], "unknown")
        self.assertEqual(outputs["seconds_per_processed_url"], "unknown")
        self.assertEqual(outputs["notebooklm_preflight_status"], "unknown")
        self.assertEqual(outputs["notebooklm_auth_failure_count"], "unknown")
        self.assertEqual(outputs["notebooklm_auth_incident"], "unknown")
        self.assertEqual(outputs["notebooklm_circuit_breaker_skipped_count"], "unknown")
        self.assertEqual(outputs["replay_queued_count"], "unknown")

    def test_extract_pipeline_outputs_raises_when_run_outcome_is_malformed(
        self,
    ) -> None:
        with self.assertRaises(RuntimeError):
            extract_pipeline_outputs("run_outcome:{not-json")

    def test_extract_pipeline_outputs_sets_auth_incident_true_on_preflight_or_failures(
        self,
    ) -> None:
        log_text = "\n".join(
            [
                'run_outcome:{"processed_urls": 1, "summary_ok_count": 0, "summary_failed_count": 1, "digest_created": true, "digest_path": "data/digests/2026-03-20.md", "digest_sent_chunks": 1}',
                'run_metrics:{"metrics_version": 1, "digest_date": "2026-03-20", "processed_urls": 1, "summary_ok_count": 0, "summary_failed_count": 1, "fetch_ok_article_count": 0, "fetch_ok_youtube_count": 1, "fetch_failed_count": 0, "notebooklm_work_item_count": 1, "notebooklm_preflight_status": "auth_expired", "notebooklm_circuit_breaker_skipped_count": 2, "youtube_auth_failure_count": 1, "notebooklm_auth_failure_count": 1, "replay_queued_count": 3, "pipeline_seconds": 8.0, "seconds_per_processed_url": 8.0}',
            ]
        )

        outputs = extract_pipeline_outputs(log_text)
        self.assertEqual(outputs["notebooklm_auth_incident"], "true")


if __name__ == "__main__":
    unittest.main()
