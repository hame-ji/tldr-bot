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
    write_failure_record,
)
from src._prompts import load_prompt
from src.summarization.notebooklm_backend import (
    NOTEBOOKLM_AUTH_EXPIRED,
    NOTEBOOKLM_PREFLIGHT_AUTH_EXPIRED,
    NOTEBOOKLM_PREFLIGHT_MISCONFIGURED,
    NOTEBOOKLM_PREFLIGHT_SKIPPED,
    YOUTUBE_AUTH_EXPIRED,
    check_notebooklm_auth,
)
from src.summarization.replay_queue import enqueue_notebooklm_auth_failure
from src.summarization.notebooklm_backend import (
    summarize_url as summarize_url_with_notebooklm,
)
from src.summarization.notebooklm_backend import (
    summarize_youtube as summarize_youtube_with_notebooklm,
)
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
_NOTEBOOKLM_ENFORCE_SERIAL_CONCURRENCY = 1
_ARTICLE_FETCH_FAILURE_REASONS = {
    ARTICLE_EXTRACT_TOO_SHORT,
    HTTP_BLOCKED,
    NETWORK_ERROR,
    PDF_EXTRACT_FAILED,
    TLS_ERROR,
}


def _is_article_fallback_candidate(
    item: dict[str, Any], fallback_enabled: bool
) -> bool:
    if not fallback_enabled:
        return False
    if item.get("status") != "failed" or item.get("kind") != "article":
        return False
    reason = item.get("reason")
    return isinstance(reason, str) and reason in _ARTICLE_FETCH_FAILURE_REASONS


def _is_preflight_auth_failure(status: str) -> bool:
    return status in {
        NOTEBOOKLM_PREFLIGHT_AUTH_EXPIRED,
        NOTEBOOKLM_PREFLIGHT_MISCONFIGURED,
    }


def _preflight_error_message(preflight_status: str) -> str:
    if preflight_status == NOTEBOOKLM_PREFLIGHT_MISCONFIGURED:
        return (
            "NotebookLM credential preflight failed: NOTEBOOKLM storage state is missing or invalid; "
            "refresh NOTEBOOKLM_STORAGE_STATE."
        )
    return (
        "NotebookLM credential preflight failed: authentication expired or invalid; "
        "run `notebooklm login` locally and refresh NOTEBOOKLM_STORAGE_STATE."
    )


def _preflight_failure_result(
    *,
    item: dict[str, Any],
    work_type: str,
    failed_base_dir: str,
    preflight_status: str,
) -> dict[str, Any]:
    url = str(item.get("url", ""))
    reason = YOUTUBE_AUTH_EXPIRED if work_type == "youtube" else NOTEBOOKLM_AUTH_EXPIRED
    error = _preflight_error_message(preflight_status)
    failure = write_failure_record(
        url=url,
        error=error,
        base_dir=failed_base_dir,
        reason=reason,
    )
    result: dict[str, Any] = {
        "status": "failed",
        "kind": item.get("kind", "article"),
        "url": url,
        "error": error,
        "failure_path": str(failure),
        "reason": reason,
    }
    upstream_reason = item.get("reason")
    if (
        work_type == "article_fallback"
        and isinstance(upstream_reason, str)
        and upstream_reason
    ):
        result["upstream_reason"] = upstream_reason
    return result


def _runtime_auth_circuit_breaker_result(
    *,
    item: dict[str, Any],
    work_type: str,
    failed_base_dir: str,
) -> dict[str, Any]:
    url = str(item.get("url", ""))
    reason = YOUTUBE_AUTH_EXPIRED if work_type == "youtube" else NOTEBOOKLM_AUTH_EXPIRED
    error = "NotebookLM auth circuit breaker: skipped after earlier auth failure in this run"
    failure = write_failure_record(
        url=url,
        error=error,
        base_dir=failed_base_dir,
        reason=reason,
    )
    return {
        "status": "failed",
        "kind": item.get("kind", "article"),
        "url": url,
        "error": error,
        "failure_path": str(failure),
        "reason": reason,
    }


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
        return summarize_url_with_notebooklm(
            url=url, prompt=self._article_fallback_prompt
        )

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
            article_fallback_prompt = load_prompt(
                nlm_config.article_fallback_prompt_path
            )

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
    diagnostics: dict[str, Any] | None = None,
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
    diagnostics_out = diagnostics if diagnostics is not None else {}
    diagnostics_out["notebooklm_work_item_count"] = len(notebooklm_work)
    diagnostics_out["notebooklm_preflight_status"] = NOTEBOOKLM_PREFLIGHT_SKIPPED
    preflight_mode = nlm_config.preflight_mode

    if not has_articles and not has_notebooklm:
        noop = _NoopSummarizer()
        final_results = [
            summarize_item(
                item=item,
                summarizer=noop,
                run_date=run_date,
                sources_base_dir=sources_base_dir,
                failed_base_dir=failed_base_dir,
            )
            for item in items
        ]
        diagnostics_out["summary_ok_count"] = sum(
            1 for result in final_results if result.get("status") == "ok"
        )
        diagnostics_out["summary_failed_count"] = sum(
            1 for result in final_results if result.get("status") == "failed"
        )
        diagnostics_out["youtube_auth_failure_count"] = 0
        diagnostics_out["notebooklm_auth_failure_count"] = 0
        diagnostics_out["notebooklm_circuit_breaker_skipped_count"] = 0
        diagnostics_out["replay_queued_count"] = 0
        return final_results

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
    if preflight_mode == "enforce":
        notebooklm_max = _NOTEBOOKLM_ENFORCE_SERIAL_CONCURRENCY

    results: list[dict[str, Any] | None] = [None] * len(items)
    notebooklm_work_to_run = notebooklm_work

    if has_notebooklm and preflight_mode != "off":
        preflight_status = check_notebooklm_auth()
        diagnostics_out["notebooklm_preflight_status"] = preflight_status
        if preflight_mode == "enforce" and _is_preflight_auth_failure(preflight_status):
            for idx, item, work_type in notebooklm_work:
                results[idx] = _preflight_failure_result(
                    item=item,
                    work_type=work_type,
                    failed_base_dir=failed_base_dir,
                    preflight_status=preflight_status,
                )
            notebooklm_work_to_run = []

    for idx, item in passthrough:
        results[idx] = summarize_item(
            item=item,
            summarizer=summarizer,
            run_date=run_date,
            sources_base_dir=sources_base_dir,
            failed_base_dir=failed_base_dir,
        )

    def _timed_summarize(
        idx: int, item: dict[str, Any], work_type: str
    ) -> tuple[int, dict[str, Any]]:
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

    def _await_future_result(
        future: Any,
        *,
        idx: int,
        item: dict[str, Any],
        submitted_at: float,
    ) -> tuple[int, dict[str, Any]]:
        if future.done():
            return future.result()
        remaining_timeout = _FUTURE_TIMEOUT_SECONDS - (time.monotonic() - submitted_at)
        if remaining_timeout <= 0:
            raise FutureTimeoutError()
        return future.result(timeout=remaining_timeout)

    timed_out = False
    notebooklm_circuit_open = False
    notebooklm_circuit_breaker_skipped_count = 0
    or_pool = (
        ThreadPoolExecutor(max_workers=openrouter_max, thread_name_prefix="openrouter")
        if has_articles
        else None
    )
    notebooklm_pool = (
        ThreadPoolExecutor(max_workers=notebooklm_max, thread_name_prefix="notebooklm")
        if notebooklm_work_to_run and preflight_mode != "enforce"
        else None
    )
    try:
        article_futures = (
            [
                (
                    or_pool.submit(_timed_summarize, idx, item, "article"),
                    idx,
                    item,
                    time.monotonic(),
                )
                for idx, item in article_work
            ]
            if or_pool
            else []
        )
        notebooklm_futures = (
            [
                (
                    notebooklm_pool.submit(_timed_summarize, idx, item, work_type),
                    idx,
                    item,
                    work_type,
                    time.monotonic(),
                )
                for idx, item, work_type in notebooklm_work_to_run
            ]
            if notebooklm_pool
            else []
        )

        if preflight_mode == "enforce":
            for idx, item, work_type in notebooklm_work_to_run:
                if notebooklm_circuit_open:
                    results[idx] = _runtime_auth_circuit_breaker_result(
                        item=item,
                        work_type=work_type,
                        failed_base_dir=failed_base_dir,
                    )
                    notebooklm_circuit_breaker_skipped_count += 1
                    continue

                enforce_pool = ThreadPoolExecutor(
                    max_workers=1, thread_name_prefix="notebooklm"
                )
                try:
                    future = enforce_pool.submit(_timed_summarize, idx, item, work_type)
                    try:
                        result_idx, result = future.result(
                            timeout=_FUTURE_TIMEOUT_SECONDS
                        )
                        results[result_idx] = result
                    except FutureTimeoutError:
                        timed_out = True
                        future.cancel()
                        results[idx] = _timeout_result(
                            item=item,
                            failed_base_dir=failed_base_dir,
                            timeout_seconds=_FUTURE_TIMEOUT_SECONDS,
                        )
                        continue
                finally:
                    enforce_pool.shutdown(wait=not timed_out, cancel_futures=timed_out)

                reason = result.get("reason")
                if result.get("status") == "failed" and reason in {
                    YOUTUBE_AUTH_EXPIRED,
                    NOTEBOOKLM_AUTH_EXPIRED,
                }:
                    notebooklm_circuit_open = True
        else:
            for future, idx, item, _work_type, submitted_at in notebooklm_futures:
                try:
                    result_idx, result = _await_future_result(
                        future,
                        idx=idx,
                        item=item,
                        submitted_at=submitted_at,
                    )
                    results[result_idx] = result
                except FutureTimeoutError:
                    timed_out = True
                    future.cancel()
                    results[idx] = _timeout_result(
                        item=item,
                        failed_base_dir=failed_base_dir,
                        timeout_seconds=_FUTURE_TIMEOUT_SECONDS,
                    )

        for future, idx, item, submitted_at in article_futures:
            try:
                result_idx, result = _await_future_result(
                    future,
                    idx=idx,
                    item=item,
                    submitted_at=submitted_at,
                )
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

    final_results = [r for r in results if r is not None]

    batch_elapsed = time.monotonic() - batch_start
    ok_count = 0
    fail_count = 0
    youtube_auth_failure_count = 0
    notebooklm_auth_failure_count = 0
    _auth_reasons = {YOUTUBE_AUTH_EXPIRED, NOTEBOOKLM_AUTH_EXPIRED}
    for r in final_results:
        status = r.get("status")
        if status == "ok":
            ok_count += 1
        elif status == "failed":
            fail_count += 1
            reason = r.get("reason")
            if reason == YOUTUBE_AUTH_EXPIRED:
                youtube_auth_failure_count += 1
            if reason in _auth_reasons:
                notebooklm_auth_failure_count += 1
    notebooklm_article_count = sum(
        1 for _, _, work_type in notebooklm_work if work_type == "article_fallback"
    )
    youtube_count = sum(
        1 for _, _, work_type in notebooklm_work if work_type == "youtube"
    )

    diagnostics_out["summary_ok_count"] = ok_count
    diagnostics_out["summary_failed_count"] = fail_count
    diagnostics_out["youtube_auth_failure_count"] = youtube_auth_failure_count
    diagnostics_out["notebooklm_auth_failure_count"] = notebooklm_auth_failure_count
    diagnostics_out["notebooklm_circuit_breaker_skipped_count"] = (
        notebooklm_circuit_breaker_skipped_count
    )

    replay_queued_count = 0
    for result in final_results:
        if result.get("status") != "failed":
            continue
        reason = result.get("reason")
        if not isinstance(reason, str):
            continue
        if reason not in {YOUTUBE_AUTH_EXPIRED, NOTEBOOKLM_AUTH_EXPIRED}:
            continue
        if enqueue_notebooklm_auth_failure(
            run_date=run_date,
            url=str(result.get("url", "")),
            kind=str(result.get("kind", "unknown")),
            reason=reason,
            source_failure_path=str(result.get("failure_path", "")),
        ):
            replay_queued_count += 1
    diagnostics_out["replay_queued_count"] = replay_queued_count

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
    if notebooklm_circuit_open:
        LOGGER.warning(
            "notebooklm_auth_circuit_open skipped=%d",
            notebooklm_circuit_breaker_skipped_count,
        )

    return final_results
