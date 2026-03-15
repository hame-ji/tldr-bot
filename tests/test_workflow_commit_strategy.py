import unittest

from src.workflow_commit_strategy import daily_commit_message, decide_commit_mode


class WorkflowCommitStrategyTests(unittest.TestCase):
    def test_daily_commit_message_format(self) -> None:
        self.assertEqual(
            daily_commit_message("2026-03-15"),
            "chore(digest): 2026-03-15 daily digest",
        )

    def test_decide_commit_mode_skips_when_no_processed_urls(self) -> None:
        mode = decide_commit_mode(
            processed_urls=0,
            has_staged_changes=True,
            head_commit_subject="chore(digest): 2026-03-15 daily digest",
            expected_daily_subject="chore(digest): 2026-03-15 daily digest",
        )
        self.assertEqual(mode, "skip")

    def test_decide_commit_mode_skips_when_no_staged_changes(self) -> None:
        mode = decide_commit_mode(
            processed_urls=3,
            has_staged_changes=False,
            head_commit_subject="chore(digest): 2026-03-15 daily digest",
            expected_daily_subject="chore(digest): 2026-03-15 daily digest",
        )
        self.assertEqual(mode, "skip")

    def test_decide_commit_mode_amends_when_head_is_today_digest(self) -> None:
        mode = decide_commit_mode(
            processed_urls=2,
            has_staged_changes=True,
            head_commit_subject="chore(digest): 2026-03-15 daily digest",
            expected_daily_subject="chore(digest): 2026-03-15 daily digest",
        )
        self.assertEqual(mode, "amend")

    def test_decide_commit_mode_creates_when_head_differs(self) -> None:
        mode = decide_commit_mode(
            processed_urls=2,
            has_staged_changes=True,
            head_commit_subject="feat: tweak summarizer prompt",
            expected_daily_subject="chore(digest): 2026-03-15 daily digest",
        )
        self.assertEqual(mode, "create")


if __name__ == "__main__":
    unittest.main()
