from __future__ import annotations

import json
import urllib.request
from typing import Any, Optional


class GitHubActionsClient:
    def __init__(self, repo: str, token: Optional[str]) -> None:
        self.repo = repo
        self.token = token or ""
        self._api_base = f"https://api.github.com/repos/{repo}"

    def _request_json(self, url: str) -> dict[str, Any]:
        request = urllib.request.Request(url, headers=self._headers())
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))

    def _request_bytes(self, url: str) -> bytes:
        request = urllib.request.Request(url, headers=self._headers())
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read()

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "tldr-bot-run-history",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def list_workflow_runs(self, workflow_file: str, per_page: int = 30) -> list[dict[str, Any]]:
        url = f"{self._api_base}/actions/workflows/{workflow_file}/runs?per_page={per_page}"
        payload = self._request_json(url)
        return payload.get("workflow_runs", [])

    def download_run_logs_zip(self, run_id: int) -> bytes:
        url = f"{self._api_base}/actions/runs/{run_id}/logs"
        return self._request_bytes(url)

