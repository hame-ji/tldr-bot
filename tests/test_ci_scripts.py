from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


class ScriptEntrypointTests(unittest.TestCase):
    def test_extract_pipeline_outputs_module_writes_github_output(self) -> None:
        log_text = "\n".join(
            [
                "some log line",
                'run_outcome:{"processed_urls": 2, "summary_ok_count": 2, "summary_failed_count": 0, "digest_created": true, "digest_path": "data/digests/2026-03-22.md", "digest_sent_chunks": 1}',
                'run_metrics:{"metrics_version": 1, "digest_date": "2026-03-22", "processed_urls": 2, "summary_ok_count": 2, "summary_failed_count": 0, "fetch_ok_article_count": 1, "fetch_ok_youtube_count": 1, "fetch_failed_count": 0, "pipeline_seconds": 90.5, "seconds_per_processed_url": 45.25}',
            ]
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "pipeline.log"
            output_path = Path(temp_dir) / "github_output.txt"
            log_path.write_text(log_text, encoding="utf-8")

            env = os.environ.copy()
            env["GITHUB_OUTPUT"] = str(output_path)

            result = subprocess.run(
                [sys.executable, "-m", "scripts.extract_pipeline_outputs", str(log_path)],
                cwd=REPO_ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)

            outputs = {}
            for line in output_path.read_text(encoding="utf-8").splitlines():
                key, value = line.split("=", 1)
                outputs[key] = value

            self.assertEqual(outputs["digest_date"], "2026-03-22")
            self.assertEqual(outputs["processed_urls"], "2")
            self.assertEqual(outputs["digest_created"], "true")
            self.assertEqual(outputs["pipeline_seconds"], "90.500")
            self.assertEqual(outputs["seconds_per_processed_url"], "45.250")

    def test_write_run_history_summary_module_writes_summary_with_warning(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            summary_path = Path(temp_dir) / "summary.md"

            env = os.environ.copy()
            env.update(
                {
                    "GITHUB_STEP_SUMMARY": str(summary_path),
                    "GITHUB_RUN_ID": "12345",
                    "GITHUB_RUN_NUMBER": "678",
                    "GITHUB_REPOSITORY": "invalid repo",
                    "DIGEST_DATE": "2026-03-22",
                    "PIPELINE_RESULT": "success",
                    "PROCESSED_URLS": "2",
                    "PIPELINE_SECONDS": "90.500",
                    "SECONDS_PER_PROCESSED_URL": "45.250",
                    "FETCH_FAILED_COUNT": "0",
                    "GITHUB_TOKEN": "",
                }
            )

            result = subprocess.run(
                [sys.executable, "-m", "scripts.write_run_history_summary"],
                cwd=REPO_ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)

            summary_text = summary_path.read_text(encoding="utf-8")
            self.assertIn("Performance Summary (Last 7 Runs)", summary_text)
            self.assertIn("Run history unavailable", summary_text)

    def test_empty_day_run_outcome_maps_to_skipped_empty_day_commit_status(self) -> None:
        log_text = (
            'run_outcome:{"processed_urls": 0, "summary_ok_count": 0, "summary_failed_count": 0, '
            '"digest_created": false, "digest_path": "", "digest_sent_chunks": 0}'
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "pipeline.log"
            log_path.write_text(log_text, encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    (
                        "from pathlib import Path; "
                        "from src.telemetry.pipeline_log_parser import extract_pipeline_outputs; "
                        "import sys; "
                        "print(extract_pipeline_outputs(Path(sys.argv[1]).read_text(encoding='utf-8'))['processed_urls'])"
                    ),
                    str(log_path),
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
            processed_urls = result.stdout.strip()
            commit_status = "skipped_empty_day" if processed_urls == "0" else "pushed"
            self.assertEqual(commit_status, "skipped_empty_day")


if __name__ == "__main__":
    unittest.main()
