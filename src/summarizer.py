import os
import time
from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional

from slugify import slugify

try:
    from content_fetcher import write_failure_record
except Exception:  # noqa: BLE001
    from src.content_fetcher import write_failure_record


class GeminiSummarizer:
    def __init__(
        self,
        api_key: str,
        prompt_path: str = "prompts/summarize.txt",
        model: str = "gemini-2.0-flash",
        min_spacing_seconds: float = 1.0,
    ) -> None:
        from google import genai

        self.client = genai.Client(api_key=api_key)
        self.prompt_path = prompt_path
        self.model = model
        self.min_spacing_seconds = min_spacing_seconds

    def _load_prompt(self) -> str:
        path = Path(self.prompt_path)
        if not path.exists():
            raise RuntimeError("Missing summarize prompt file: " + self.prompt_path)
        return path.read_text(encoding="utf-8").strip()

    def _generate_with_retry(self, contents: list[str], retries: int = 3) -> str:
        prompt = self._load_prompt()
        last_error: Optional[Exception] = None

        for attempt in range(retries):
            if attempt > 0:
                time.sleep(60)

            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=[prompt] + contents,
                )
                text = getattr(response, "text", None)
                if not text:
                    raise RuntimeError("Gemini response contained no text")
                time.sleep(self.min_spacing_seconds)
                return str(text).strip()
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if "429" not in str(exc):
                    break

        raise RuntimeError("Gemini summarization failed") from last_error

    def summarize_article(self, url: str, content: str) -> str:
        return self._generate_with_retry(["URL: " + url, content])

    def summarize_youtube(self, url: str) -> str:
        return self._generate_with_retry(["YouTube URL: " + url])


def _source_output_path(url: str, run_date: date, base_dir: str = "data/sources") -> Path:
    from urllib.parse import urlparse

    parsed = urlparse(url)
    slug_seed = (parsed.netloc + parsed.path).strip("/") or "source"
    slug = slugify(slug_seed)[:80] or "source"
    day = run_date.isoformat()
    out_dir = Path(base_dir) / day
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / (slug + ".md")


def summarize_item(
    item: Dict[str, Any],
    summarizer: GeminiSummarizer,
    run_date: date,
    sources_base_dir: str = "data/sources",
    failed_base_dir: str = "data/failed",
) -> Dict[str, Any]:
    url = item["url"]
    if item.get("status") != "ok":
        return item

    try:
        if item["kind"] == "article":
            summary = summarizer.summarize_article(url=url, content=item["content"])
        else:
            summary = summarizer.summarize_youtube(url=url)
    except Exception as exc:  # noqa: BLE001
        failure = write_failure_record(url=url, error=str(exc), base_dir=failed_base_dir)
        return {
            "status": "failed",
            "kind": item["kind"],
            "url": url,
            "error": str(exc),
            "failure_path": str(failure),
        }

    output_path = _source_output_path(url=url, run_date=run_date, base_dir=sources_base_dir)
    output_path.write_text(summary + "\n", encoding="utf-8")
    return {
        "status": "ok",
        "kind": item["kind"],
        "url": url,
        "summary_path": str(output_path),
    }


def summarize_items(
    items: list[Dict[str, Any]],
    run_date: date,
    sources_base_dir: str = "data/sources",
    failed_base_dir: str = "data/failed",
) -> list[Dict[str, Any]]:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing GEMINI_API_KEY environment variable")

    model = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
    summarizer = GeminiSummarizer(api_key=api_key, model=model)

    results = []
    for item in items:
        results.append(
            summarize_item(
                item=item,
                summarizer=summarizer,
                run_date=run_date,
                sources_base_dir=sources_base_dir,
                failed_base_dir=failed_base_dir,
            )
        )
    return results
