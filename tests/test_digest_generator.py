import tempfile
import unittest
from datetime import date
from pathlib import Path

from src.digest_generator import generate_digest


class DigestGeneratorTests(unittest.TestCase):
    def test_generate_digest_writes_dated_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            prompt_path = Path(tmpdir) / "digest.txt"
            prompt_path.write_text("# Digest {{date}}\n\n{{summaries}}\n\n{{failed_urls_section}}\n", encoding="utf-8")

            summary_file = Path(tmpdir) / "summary.md"
            summary_file.write_text("One summary", encoding="utf-8")

            result = generate_digest(
                items=[{"status": "ok", "url": "https://example.com/a", "summary_path": str(summary_file)}],
                run_date=date(2026, 3, 15),
                prompt_path=str(prompt_path),
                digests_base_dir=tmpdir,
            )

            digest_path = Path(result["digest_path"])
            self.assertTrue(digest_path.exists())
            self.assertEqual(digest_path.name, "2026-03-15.md")

    def test_prompt_template_controls_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            prompt_path = Path(tmpdir) / "digest.txt"
            prompt_path.write_text("DIGEST {{date}}\nCOUNT={{summary_count}}\n\n{{summaries}}\n", encoding="utf-8")

            summary_file = Path(tmpdir) / "summary.md"
            summary_file.write_text("Hello world", encoding="utf-8")

            result = generate_digest(
                items=[{"status": "ok", "url": "https://example.com/a", "summary_path": str(summary_file)}],
                run_date=date(2026, 3, 15),
                prompt_path=str(prompt_path),
                digests_base_dir=tmpdir,
            )

            text = result["digest_text"]
            self.assertIn("DIGEST 2026-03-15", text)
            self.assertIn("COUNT=1", text)
            self.assertIn("Hello world", text)

    def test_failed_urls_section_present_when_failures_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            prompt_path = Path(tmpdir) / "digest.txt"
            prompt_path.write_text("# Digest\n\n{{summaries}}\n\n{{failed_urls_section}}\n", encoding="utf-8")

            summary_file = Path(tmpdir) / "summary.md"
            summary_file.write_text("ok summary", encoding="utf-8")

            result = generate_digest(
                items=[
                    {"status": "ok", "url": "https://ok.example", "summary_path": str(summary_file)},
                    {"status": "failed", "url": "https://fail.example", "error": "timeout"},
                ],
                run_date=date(2026, 3, 15),
                prompt_path=str(prompt_path),
                digests_base_dir=tmpdir,
            )

            text = result["digest_text"]
            self.assertIn("## Failed URLs", text)
            self.assertIn("https://fail.example", text)
            self.assertIn("timeout", text)


if __name__ == "__main__":
    unittest.main()
