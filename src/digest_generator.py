from datetime import date
from pathlib import Path
from typing import Any


def _load_digest_prompt(prompt_path: str = "prompts/digest.txt") -> str:
    path = Path(prompt_path)
    if not path.exists():
        raise RuntimeError("Missing digest prompt file: " + prompt_path)
    return path.read_text(encoding="utf-8").strip()


def _render_digest(
    items: list[dict[str, Any]],
    run_date: date,
    prompt_path: str = "prompts/digest.txt",
) -> str:
    prompt = _load_digest_prompt(prompt_path=prompt_path)

    successful = [item for item in items if item.get("status") == "ok"]
    failed = [item for item in items if item.get("status") == "failed"]
    ignored = [item for item in items if item.get("status") == "ignored"]

    summary_blocks: list[str] = []
    for index, item in enumerate(successful, start=1):
        summary_path_raw = item.get("summary_path")
        if not isinstance(summary_path_raw, str):
            continue

        summary_path = Path(summary_path_raw)
        if not summary_path.exists():
            continue

        summary_text = summary_path.read_text(encoding="utf-8").strip()
        if not summary_text:
            continue

        summary_blocks.append(f"## Item {index}\n\nURL: {item['url']}\n\n{summary_text}")

    summaries_text = "\n\n".join(summary_blocks).strip()
    if not summaries_text:
        summaries_text = "No successful summaries were generated today."

    failed_lines = []
    for item in failed:
        url = item.get("url", "unknown")
        error = item.get("error")
        if isinstance(error, str) and error:
            failed_lines.append(f"- {url} ({error})")
        else:
            failed_lines.append(f"- {url}")

    failed_section = ""
    if failed_lines:
        failed_section = "## Failed URLs\n\n" + "\n".join(failed_lines)

    rendered = (
        prompt.replace("{{date}}", run_date.isoformat())
        .replace("{{summary_count}}", str(len(successful)))
        .replace("{{failure_count}}", str(len(failed)))
        .replace("{{ignored_count}}", str(len(ignored)))
        .replace("{{summaries}}", summaries_text)
        .replace("{{failed_urls_section}}", failed_section)
    ).strip()

    if failed_section and "## Failed URLs" not in rendered:
        rendered = (rendered + "\n\n" + failed_section).strip()

    return rendered + "\n"


def generate_digest(
    items: list[dict[str, Any]],
    run_date: date,
    prompt_path: str = "prompts/digest.txt",
    digests_base_dir: str = "data/digests",
) -> dict[str, str]:
    digest_text = _render_digest(items=items, run_date=run_date, prompt_path=prompt_path)

    out_dir = Path(digests_base_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{run_date.isoformat()}.md"
    out_path.write_text(digest_text, encoding="utf-8")

    return {
        "digest_path": str(out_path),
        "digest_text": digest_text,
    }
