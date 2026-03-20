import io
import json
import unittest
import zipfile

from src.telemetry.run_history.models import RunHistorySnapshot
from src.telemetry.run_history.parser import (
    extract_run_metrics_from_log_text,
    extract_run_metrics_from_logs_zip,
)
from src.telemetry.run_history.report import (
    build_current_snapshot,
    fetch_history_snapshots,
    render_performance_summary,
)


class RunHistoryParserTests(unittest.TestCase):
    def test_extract_run_metrics_from_log_text_handles_timestamp_prefix(self) -> None:
        line = (
            "2026-03-20T07:51:51.1524289Z run_metrics:"
            + json.dumps(
                {
                    "metrics_version": 1,
                    "digest_date": "2026-03-20",
                    "processed_urls": 6,
                }
            )
        )
        payload = extract_run_metrics_from_log_text(line)
        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertEqual(payload["digest_date"], "2026-03-20")
        self.assertEqual(payload["processed_urls"], 6)

    def test_extract_run_metrics_from_logs_zip_reads_txt_entries(self) -> None:
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("job/log-1.txt", "hello\n")
            archive.writestr(
                "job/log-2.txt",
                'run_metrics:{"metrics_version":1,"digest_date":"2026-03-19","processed_urls":5}',
            )

        payload = extract_run_metrics_from_logs_zip(stream.getvalue())
        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertEqual(payload["digest_date"], "2026-03-19")


class RunHistoryReportTests(unittest.TestCase):
    def test_build_current_snapshot_parses_numeric_fields(self) -> None:
        snapshot = build_current_snapshot(
            run_id="123",
            run_number="29",
            digest_date="2026-03-20",
            status="success",
            processed_urls="6",
            pipeline_seconds="111.000",
            seconds_per_processed_url="18.500",
            fetch_failed_count="2",
        )
        self.assertEqual(snapshot.run_id, 123)
        self.assertEqual(snapshot.run_number, 29)
        self.assertEqual(snapshot.processed_urls, 6)
        self.assertEqual(snapshot.pipeline_seconds, 111.0)
        self.assertEqual(snapshot.seconds_per_processed_url, 18.5)
        self.assertEqual(snapshot.fetch_failed_count, 2)

    def test_render_performance_summary_computes_delta_from_previous_row(self) -> None:
        current = RunHistorySnapshot(
            run_id=200,
            run_number=29,
            digest_date="2026-03-20",
            status="success",
            processed_urls=6,
            pipeline_seconds=111.0,
            seconds_per_processed_url=18.5,
            fetch_failed_count=1,
            metrics_available=True,
        )
        previous = RunHistorySnapshot(
            run_id=199,
            run_number=28,
            digest_date="2026-03-19",
            status="success",
            processed_urls=5,
            pipeline_seconds=188.0,
            seconds_per_processed_url=37.6,
            fetch_failed_count=2,
            metrics_available=True,
        )

        report = render_performance_summary([current, previous], window_size=7)
        self.assertIn("Performance Summary (Last 7 Runs)", report)
        self.assertIn("#29", report)
        self.assertIn("+19.10", report)


class RunHistoryFetchTests(unittest.TestCase):
    def test_fetch_history_snapshots_returns_empty_when_limit_is_zero(self) -> None:
        class FakeClient:
            def list_workflow_runs(self, workflow_file: str, per_page: int = 30):  # noqa: ANN001
                raise AssertionError("should not fetch runs when limit is zero")

            def download_run_logs_zip(self, run_id: int) -> bytes:
                raise AssertionError("should not download logs when limit is zero")

        snapshots = fetch_history_snapshots(
            client=FakeClient(),
            workflow_file="digest.yml",
            current_run_id=300,
            limit=0,
        )

        self.assertEqual(snapshots, [])

    def test_fetch_history_snapshots_uses_completed_runs_and_excludes_current(self) -> None:
        class FakeClient:
            def list_workflow_runs(self, workflow_file: str, per_page: int = 30):  # noqa: ANN001
                self.workflow_file = workflow_file
                self.per_page = per_page
                return [
                    {"id": 301, "run_number": 31, "status": "in_progress", "created_at": "2026-03-21T07:00:00Z"},
                    {"id": 300, "run_number": 30, "status": "completed", "conclusion": "success", "created_at": "2026-03-20T07:00:00Z"},
                    {"id": 299, "run_number": 29, "status": "completed", "conclusion": "failure", "created_at": "2026-03-19T07:00:00Z"},
                ]

            def download_run_logs_zip(self, run_id: int) -> bytes:
                stream = io.BytesIO()
                with zipfile.ZipFile(stream, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
                    if run_id == 300:
                        archive.writestr(
                            "job/1.txt",
                            'run_metrics:{"metrics_version":1,"digest_date":"2026-03-20","processed_urls":6,"pipeline_seconds":120.0,"seconds_per_processed_url":20.0,"fetch_failed_count":0}',
                        )
                    else:
                        archive.writestr("job/2.txt", "no metrics line")
                return stream.getvalue()

        snapshots = fetch_history_snapshots(
            client=FakeClient(),
            workflow_file="digest.yml",
            current_run_id=300,
            limit=3,
        )

        self.assertEqual(len(snapshots), 1)
        self.assertEqual(snapshots[0].run_number, 29)
        self.assertFalse(snapshots[0].metrics_available)


if __name__ == "__main__":
    unittest.main()
