from __future__ import annotations

import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from datetime import date
from typing import Any

from src._config import (
    NotebookLMConfig,
    OpenRouterConfig,
    notebooklm_config_from_env,
    openrouter_config_from_env,
)
from src._failures import (
    ARTICLE_EXTRACT_TOO_SHORT,
    HTTP_BLOCKED,
    NETWORK_ERROR,
    PDF_EXTRACT_FAILED,
    TLS_ERROR,
)
from src._prompts import load_prompt
from src.summarization.notebooklm_backend import summarize_url as summarize_url_with_notebooklm
from src.summarization.notebooklm_backend import summarize_youtube as summarize_youtube_with_notebooklm
from src.summarization.common import (
    Summarizer,
    _clamp_concurrency,
    _source_output_path,
    _timeout_result,
    summarize_failed_article_item,
    summarize_item,
)
from src.summarization.openrouter_backend import OpenRouterSummarizer, _order_models

LOGGER = logging.getLogger(__name__)

_MAX_BACKEND_CONCURRENCY = 3
_FUTURE_TIMEOUT_SECONDS = 600

_ARTICLE_FETCH_FAILURE_REASONS = {
    ARTICLE_EXTRACT_TOO_SHORT,
    HTTP_BLOCKED,
    NETWORK_ERROR,
    PDF_EXTRACT_FAILED,
    TLS_ERROR,
}


def _is_article_fallback_candidate(item: dict[str, Any], fallback_enabled: bool) -> bool:
    if not fallback_enabled:
        return False
    if item.get("status") != "failed" or item.get("kind") != "article":
        return False
    reason = item.get("reason")
    return isinstance(reason, str) and reason in _ARTICLE_FETCH_FAILURE_REASONS


class _NoopSummarizer:
    def summarize_article(self, url: str, content: str) -> str:
        raise RuntimeError("No article summarizer configured")

    def summarize_article_from_url(self, url: str) -> str:
        raise RuntimeError("No article URL fallback configured")

    def summarize_youtube(self, url: str) -> str:
        raise RuntimeError("No youtube summarization candidates")


class _PipelineSummarizer:
    def __init__(
        self,
        article_summarizer: OpenRouterSummarizer | None,
        youtube_prompt: str,
        article_fallback_prompt: str,
    ) -> None:
        self.article_summarizer = article_summarizer
        self._youtube_prompt = youtube_prompt
        self._article_fallback_prompt = article_fallback_prompt

    def summarize_article(self, url: str, content: str) -> str:
        if self.article_summarizer is None:
            raise RuntimeError("No article summarizer configured")
        return self.article_summarizer.summarize_article(url=url, content=content)

    def summarize_article_from_url(self, url: str) -> str:
        return summarize_url_with_notebooklm(url=url, prompt=self._article_fallback_prompt)

    def summarize_youtube(self, url: str) -> str:
        return summarize_youtube_with_notebooklm(url=url, prompt=self._youtube_prompt)


def _build_pipeline_summarizer(
    or_config: OpenRouterConfig | None,
    nlm_config: NotebookLMConfig,
    has_notebooklm: bool,
    notebooklm_work_types: set[str],
) -> Summarizer:
    article_summarizer: OpenRouterSummarizer | None = None
    if or_config is not None:
        article_summarizer = OpenRouterSummarizer.from_config(or_config)

    youtube_prompt = ""
    article_fallback_prompt = ""
    if has_notebooklm:
        if "youtube" in notebooklm_work_types:
            youtube_prompt = load_prompt(nlm_config.youtube_prompt_path)
        if "article_fallback" in notebooklm_work_types:
            article_fallback_prompt = load_prompt(nlm_config.article_fallback_prompt_path)

    summarizer: Summarizer = _PipelineSummarizer(
        article_summarizer=article_summarizer,
        youtube_prompt=youtube_prompt,
        article_fallback_prompt=article_fallback_prompt,
    )
    return summarizer


def summarize_items(
    items: list[dict[str, Any]],
    run_date: date,
    sources_base_dir: str = "data/sources",
    failed_base_dir: str = "data/failed",
) -> list[dict[str, Any]]:
    batch_start = time.monotonic()

    nlm_config = notebooklm_config_from_env()

    article_work: list[tuple[int, dict[str, Any]]] = []
    notebooklm_work: list[tuple[int, dict[str, Any], str]] = []
    passthrough: list[tuple[int, dict[str, Any]]] = []

    for idx, item in enumerate(items):
        if item.get("status") == "ok" and item.get("kind") == "article":
            article_work.append((idx, item))
        elif item.get("status") == "ok" and item.get("kind") == "youtube":
            notebooklm_work.append((idx, item, "youtube"))
        elif _is_article_fallback_candidate(item, nlm_config.article_fallback_enabled):
            notebooklm_work.append((idx, item, "article_fallback"))
        else:
            passthrough.append((idx, item))

    has_articles = len(article_work) > 0
    has_notebooklm = len(notebooklm_work) > 0

    if not has_articles and not has_notebooklm:
        noop = _NoopSummarizer()
        return [
            summarize_item(
                item=item,
                summarizer=noop,
                run_date=run_date,
                sources_base_dir=sources_base_dir,
                failed_base_dir=failed_base_dir,
            )
            for item in items
        ]

    or_config: OpenRouterConfig | None = None
    if has_articles:
        or_config = openrouter_config_from_env()

    work_types = {work_type for _, _, work_type in notebooklm_work}
    summarizer = _build_pipeline_summarizer(
        or_config=or_config,
        nlm_config=nlm_config,
        has_notebooklm=has_notebooklm,
        notebooklm_work_types=work_types,
    )

    openrouter_max = _clamp_concurrency(
        os.environ.get("OPENROUTER_MAX_CONCURRENCY", "1"),
        default=1,
        max_allowed=_MAX_BACKEND_CONCURRENCY,
    )
    notebooklm_max = _clamp_concurrency(
        os.environ.get("NOTEBOOKLM_MAX_CONCURRENCY", "1"),
        default=1,
        max_allowed=_MAX_BACKEND_CONCURRENCY,
    )

    results: list[dict[str, Any] | None] = [None] * len(items)

    for idx, item in passthrough:
        results[idx] = summarize_item(
            item=item,
            summarizer=summarizer,
            run_date=run_date,
            sources_base_dir=sources_base_dir,
            failed_base_dir=failed_base_dir,
        )

    def _timed_summarize(idx: int, item: dict[str, Any], work_type: str) -> tuple[int, dict[str, Any]]:
        item_start = time.monotonic()
        if work_type == "article_fallback":
            result = summarize_failed_article_item(
                item=item,
                summarizer=summarizer,
                run_date=run_date,
                sources_base_dir=sources_base_dir,
                failed_base_dir=failed_base_dir,
            )
        else:
            result = summarize_item(
                item=item,
                summarizer=summarizer,
                run_date=run_date,
                sources_base_dir=sources_base_dir,
                failed_base_dir=failed_base_dir,
            )
        elapsed = time.monotonic() - item_start
        url = item.get("url", "?")
        kind = item.get("kind", "?")
        status = result.get("status", "?")
        LOGGER.info(
            "summarize_item kind=%s work_type=%s status=%s elapsed=%.2fs url=%s",
            kind,
            work_type,
            status,
            elapsed,
            url,
        )
        return (idx, result)

    timed_out = False
    or_pool = ThreadPoolExecutor(max_workers=openrouter_max, thread_name_prefix="openrouter") if has_articles else None
    notebooklm_pool = ThreadPoolExecutor(max_workers=notebooklm_max, thread_name_prefix="notebooklm") if has_notebooklm else None
    try:
        article_futures = [
            (or_pool.submit(_timed_summarize, idx, item, "article"), idx, item)
            for idx, item in article_work
        ] if or_pool else []
        notebooklm_futures = [
            (notebooklm_pool.submit(_timed_summarize, idx, item, work_type), idx, item)
            for idx, item, work_type in notebooklm_work
        ] if notebooklm_pool else []

        for future, idx, item in article_futures:
            try:
                result_idx, result = future.result(timeout=_FUTURE_TIMEOUT_SECONDS)
                results[result_idx] = result
            except FutureTimeoutError:
                timed_out = True
                future.cancel()
                results[idx] = _timeout_result(
                    item=item,
                    failed_base_dir=failed_base_dir,
                    timeout_seconds=_FUTURE_TIMEOUT_SECONDS,
                )

        for future, idx, item in notebooklm_futures:
            try:
                result_idx, result = future.result(timeout=_FUTURE_TIMEOUT_SECONDS)
                results[result_idx] = result
            except FutureTimeoutError:
                timed_out = True
                future.cancel()
                results[idx] = _timeout_result(
                    item=item,
                    failed_base_dir=failed_base_dir,
                    timeout_seconds=_FUTURE_TIMEOUT_SECONDS,
                )
    finally:
        if or_pool:
            or_pool.shutdown(wait=not timed_out, cancel_futures=timed_out)
        if notebooklm_pool:
            notebooklm_pool.shutdown(wait=not timed_out, cancel_futures=timed_out)

    batch_elapsed = time.monotonic() - batch_start
    ok_count = sum(1 for r in results if r and r.get("status") == "ok")
    fail_count = sum(1 for r in results if r and r.get("status") == "failed")
    notebooklm_article_count = sum(1 for _, _, work_type in notebooklm_work if work_type == "article_fallback")
    youtube_count = sum(1 for _, _, work_type in notebooklm_work if work_type == "youtube")
    LOGGER.info(
        "summarize_batch total=%d ok=%d failed=%d articles=%d article_fallbacks=%d youtube=%d "
        "openrouter_concurrency=%d notebooklm_concurrency=%d elapsed=%.2fs",
        len(items),
        ok_count,
        fail_count,
        len(article_work),
        notebooklm_article_count,
        youtube_count,
        openrouter_max,
        notebooklm_max,
        batch_elapsed,
    )

    return [r for r in results if r is not None]
