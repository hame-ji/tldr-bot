import unittest

from scripts.validate_claude_sync import (
    Route,
    build_validation_errors,
    parse_routes_from_parent,
    resolve_required_child_paths,
)


def _child_content(date: str, commit: str, note: str, body: str = "## Scope\n\ntext\n") -> str:
    return (
        "# Child\n\n"
        f"Last-Reviewed-Date: {date}\n"
        f"Last-Reviewed-Commit: {commit}\n"
        f"Review-Note: {note}\n\n"
        f"{body}"
    )


class ClaudeRoutingManifestTests(unittest.TestCase):
    def test_parse_routes_from_parent_reads_manifest(self) -> None:
        parent_text = """
header
<!-- CLAUDE_ROUTING_MANIFEST_START -->
```yaml
routing_manifest:
  version: 1
  routes:
    - path: "src/telemetry/"
      claude: "src/telemetry/CLAUDE.md"
    - path: "src/"
      claude: "src/CLAUDE.md"
```
<!-- CLAUDE_ROUTING_MANIFEST_END -->
footer
"""
        routes = parse_routes_from_parent(parent_text)
        self.assertEqual(
            routes,
            [
                Route(path="src/telemetry/", claude="src/telemetry/CLAUDE.md"),
                Route(path="src/", claude="src/CLAUDE.md"),
            ],
        )

    def test_resolve_required_child_paths_uses_longest_prefix(self) -> None:
        routes = [
            Route(path="src/", claude="src/CLAUDE.md"),
            Route(path="src/telemetry/", claude="src/telemetry/CLAUDE.md"),
        ]
        required = resolve_required_child_paths(
            staged_paths=["src/telemetry/run_metrics.py", "src/main.py"],
            routes=routes,
        )
        self.assertEqual(required, {"src/telemetry/CLAUDE.md", "src/CLAUDE.md"})


class ClaudeSyncValidationTests(unittest.TestCase):
    def test_routed_code_change_without_child_update_blocks_commit(self) -> None:
        routes = [Route(path="src/telemetry/", claude="src/telemetry/CLAUDE.md")]
        errors = build_validation_errors(
            staged_paths=["src/telemetry/run_metrics.py"],
            routes=routes,
            staged_contents={},
            head_contents={},
        )
        self.assertEqual(len(errors), 1)
        self.assertIn("required child CLAUDE.md is not staged", errors[0])

    def test_routed_code_change_with_child_update_passes(self) -> None:
        routes = [Route(path="src/telemetry/", claude="src/telemetry/CLAUDE.md")]
        child_path = "src/telemetry/CLAUDE.md"
        head = _child_content("2026-03-21", "abc1234", "Old note")
        staged = _child_content("2026-03-22", "def4567", "Updated note")
        errors = build_validation_errors(
            staged_paths=["src/telemetry/run_metrics.py", child_path],
            routes=routes,
            staged_contents={child_path: staged},
            head_contents={child_path: head},
        )
        self.assertEqual(errors, [])

    def test_non_routed_change_passes_without_child_updates(self) -> None:
        routes = [Route(path="src/telemetry/", claude="src/telemetry/CLAUDE.md")]
        errors = build_validation_errors(
            staged_paths=["README.md"],
            routes=routes,
            staged_contents={},
            head_contents={},
        )
        self.assertEqual(errors, [])

    def test_multi_module_change_requires_all_children(self) -> None:
        routes = [
            Route(path="src/", claude="src/CLAUDE.md"),
            Route(path="tests/", claude="tests/CLAUDE.md"),
        ]
        errors = build_validation_errors(
            staged_paths=["src/main.py", "tests/test_main.py", "src/CLAUDE.md"],
            routes=routes,
            staged_contents={
                "src/CLAUDE.md": _child_content("2026-03-22", "aaa1111", "Runtime instruction review")
            },
            head_contents={
                "src/CLAUDE.md": _child_content("2026-03-21", "bbb2222", "Previous runtime instruction review")
            },
        )
        self.assertEqual(len(errors), 1)
        self.assertIn("tests/CLAUDE.md", errors[0])

    def test_child_staged_without_metadata_or_body_change_blocks_commit(self) -> None:
        routes = [Route(path="src/telemetry/", claude="src/telemetry/CLAUDE.md")]
        child_path = "src/telemetry/CLAUDE.md"
        same_content = _child_content("2026-03-21", "abc1234", "Old note")
        errors = build_validation_errors(
            staged_paths=["src/telemetry/run_metrics.py", child_path],
            routes=routes,
            staged_contents={child_path: same_content},
            head_contents={child_path: same_content},
        )
        self.assertEqual(len(errors), 1)
        self.assertIn("neither review headers nor body changed", errors[0])

    def test_child_missing_required_headers_blocks_commit(self) -> None:
        routes = [Route(path="src/telemetry/", claude="src/telemetry/CLAUDE.md")]
        child_path = "src/telemetry/CLAUDE.md"
        malformed = (
            "# Child\n\n"
            "Last-Reviewed-Date: 2026-03-21\n"
            "Last-Reviewed-Commit: abc1234\n\n"
            "## Scope\n\ntext\n"
        )
        errors = build_validation_errors(
            staged_paths=["src/telemetry/run_metrics.py", child_path],
            routes=routes,
            staged_contents={child_path: malformed},
            head_contents={child_path: None},
        )
        self.assertEqual(len(errors), 1)
        self.assertIn("missing required review headers", errors[0])

    def test_last_reviewed_commit_rejects_head(self) -> None:
        routes = [Route(path="src/telemetry/", claude="src/telemetry/CLAUDE.md")]
        child_path = "src/telemetry/CLAUDE.md"
        staged = _child_content("2026-03-22", "HEAD", "Attempted review marker")
        errors = build_validation_errors(
            staged_paths=["src/telemetry/run_metrics.py", child_path],
            routes=routes,
            staged_contents={child_path: staged},
            head_contents={child_path: None},
        )
        self.assertEqual(len(errors), 1)
        self.assertIn("lowercase hex SHA", errors[0])

    def test_last_reviewed_commit_rejects_arbitrary_token(self) -> None:
        routes = [Route(path="src/telemetry/", claude="src/telemetry/CLAUDE.md")]
        child_path = "src/telemetry/CLAUDE.md"
        staged = _child_content("2026-03-22", "claude-sync-hook-2", "Attempted review marker")
        errors = build_validation_errors(
            staged_paths=["src/telemetry/run_metrics.py", child_path],
            routes=routes,
            staged_contents={child_path: staged},
            head_contents={child_path: None},
        )
        self.assertEqual(len(errors), 1)
        self.assertIn("lowercase hex SHA", errors[0])

    def test_last_reviewed_commit_accepts_valid_sha(self) -> None:
        routes = [Route(path="src/telemetry/", claude="src/telemetry/CLAUDE.md")]
        child_path = "src/telemetry/CLAUDE.md"
        staged = _child_content(
            "2026-03-22",
            "816390e42de2ffc54ef62d2e7dec42477a918e06",
            "Concrete SHA accepted",
        )
        errors = build_validation_errors(
            staged_paths=["src/telemetry/run_metrics.py", child_path],
            routes=routes,
            staged_contents={child_path: staged},
            head_contents={child_path: None},
        )
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
