from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

PARENT_CLAUDE_PATH = "CLAUDE.md"
MANIFEST_START = "<!-- CLAUDE_ROUTING_MANIFEST_START -->"
MANIFEST_END = "<!-- CLAUDE_ROUTING_MANIFEST_END -->"
REQUIRED_HEADERS = (
    "Last-Reviewed-Date",
    "Last-Reviewed-Commit",
    "Review-Note",
)
COMMIT_HASH_RE = re.compile(r"^[0-9a-f]{7,40}$")


@dataclass(frozen=True)
class Route:
    path: str
    claude: str


def _extract_manifest_block(parent_text: str) -> str:
    pattern = re.compile(
        re.escape(MANIFEST_START) + r"(.*?)" + re.escape(MANIFEST_END),
        re.DOTALL,
    )
    match = pattern.search(parent_text)
    if match is None:
        raise ValueError("routing manifest markers were not found in parent CLAUDE.md")
    return match.group(1)


def parse_routes_from_parent(parent_text: str) -> list[Route]:
    block = _extract_manifest_block(parent_text)
    routes: list[Route] = []
    current_path: str | None = None
    current_claude: str | None = None

    for raw_line in block.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line in {"```yaml", "```"}:
            continue
        if line.startswith("#"):
            continue
        if line in {"routing_manifest:", "routes:"}:
            continue
        if line.startswith("version:"):
            continue

        path_match = re.match(r"^-\s*path:\s*['\"]?([^'\"]+)['\"]?\s*$", line)
        if path_match is not None:
            if current_path is not None:
                if current_claude is None:
                    raise ValueError(f"route for path '{current_path}' is missing claude target")
                routes.append(Route(path=current_path, claude=current_claude))
            current_path = path_match.group(1).strip()
            current_claude = None
            continue

        claude_match = re.match(r"^claude:\s*['\"]?([^'\"]+)['\"]?\s*$", line)
        if claude_match is not None:
            if current_path is None:
                raise ValueError("manifest has 'claude' entry before any 'path' entry")
            current_claude = claude_match.group(1).strip()
            continue

        raise ValueError(f"unsupported manifest line: {raw_line}")

    if current_path is not None:
        if current_claude is None:
            raise ValueError(f"route for path '{current_path}' is missing claude target")
        routes.append(Route(path=current_path, claude=current_claude))

    if not routes:
        raise ValueError("no routes found in parent routing manifest")
    return routes


def _resolve_route(path: str, routes: list[Route]) -> Route | None:
    matches = [route for route in routes if path.startswith(route.path)]
    if not matches:
        return None
    return max(matches, key=lambda route: len(route.path))


def resolve_required_child_paths(staged_paths: list[str], routes: list[Route]) -> set[str]:
    required: set[str] = set()
    for path in staged_paths:
        route = _resolve_route(path, routes)
        if route is None:
            continue
        required.add(route.claude)
    return required


def _parse_headers(content: str) -> dict[str, str]:
    headers: dict[str, str] = {}
    for line in content.splitlines():
        for key in REQUIRED_HEADERS:
            prefix = f"{key}:"
            if line.startswith(prefix):
                headers[key] = line.split(":", 1)[1].strip()
    return headers


def _extract_body(content: str) -> str:
    body_lines = []
    for line in content.splitlines():
        if any(line.startswith(f"{key}:") for key in REQUIRED_HEADERS):
            continue
        body_lines.append(line.rstrip())
    return "\n".join(body_lines).strip()


def validate_child_document_change(
    child_path: str,
    staged_content: str,
    head_content: str | None,
) -> list[str]:
    errors: list[str] = []
    staged_headers = _parse_headers(staged_content)

    missing_headers = [key for key in REQUIRED_HEADERS if not staged_headers.get(key)]
    if missing_headers:
        errors.append(
            f"{child_path}: missing required review headers: {', '.join(missing_headers)}"
        )
        return errors

    commit_ref = staged_headers["Last-Reviewed-Commit"]
    if COMMIT_HASH_RE.fullmatch(commit_ref) is None:
        errors.append(
            f"{child_path}: Last-Reviewed-Commit must be a lowercase hex SHA (7-40 chars), got '{commit_ref}'"
        )
        return errors

    if head_content is None:
        return errors

    head_headers = _parse_headers(head_content)
    headers_changed = any(staged_headers.get(key) != head_headers.get(key) for key in REQUIRED_HEADERS)
    if not headers_changed and _extract_body(staged_content) == _extract_body(head_content):
        errors.append(
            f"{child_path}: file is staged but neither review headers nor body changed"
        )
    return errors


def build_validation_errors(
    staged_paths: list[str],
    routes: list[Route],
    staged_contents: dict[str, str | None],
    head_contents: dict[str, str | None],
) -> list[str]:
    errors: list[str] = []
    required_children = resolve_required_child_paths(staged_paths, routes)
    staged_set = set(staged_paths)

    for child_path in sorted(required_children):
        if child_path not in staged_set:
            errors.append(
                f"{child_path}: required child CLAUDE.md is not staged for routed changes"
            )
            continue

        staged_content = staged_contents.get(child_path)
        if staged_content is None:
            errors.append(f"{child_path}: failed to read staged content")
            continue

        errors.extend(
            validate_child_document_change(
                child_path=child_path,
                staged_content=staged_content,
                head_content=head_contents.get(child_path),
            )
        )

    return errors


def _git_output(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout


def _try_git_show(spec: str) -> str | None:
    result = subprocess.run(
        ["git", "show", spec],
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout


def main() -> int:
    try:
        parent_text = Path(PARENT_CLAUDE_PATH).read_text(encoding="utf-8")
    except FileNotFoundError:
        print("[claude-sync] parent CLAUDE.md not found", file=sys.stderr)
        return 1

    try:
        routes = parse_routes_from_parent(parent_text)
    except ValueError as exc:
        print(f"[claude-sync] {exc}", file=sys.stderr)
        return 1

    staged_paths_raw = _git_output("diff", "--cached", "--name-only", "--diff-filter=ACMR")
    staged_paths = [line.strip() for line in staged_paths_raw.splitlines() if line.strip()]
    if not staged_paths:
        return 0

    required_children = resolve_required_child_paths(staged_paths, routes)
    staged_set = set(staged_paths)
    staged_contents = {
        child: _try_git_show(f":{child}")
        for child in required_children
        if child in staged_set
    }
    head_contents = {
        child: _try_git_show(f"HEAD:{child}") for child in required_children if child in staged_set
    }

    errors = build_validation_errors(
        staged_paths=staged_paths,
        routes=routes,
        staged_contents=staged_contents,
        head_contents=head_contents,
    )
    if not errors:
        return 0

    print("[claude-sync] commit blocked")
    for error in errors:
        print(f"- {error}")

    print()
    print("Fix guidance:")
    print("1. Update the required child CLAUDE.md file(s).")
    print("2. Update review headers: Last-Reviewed-Date, Last-Reviewed-Commit, Review-Note.")
    print("3. Stage changes with git add and commit again.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
