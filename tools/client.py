"""Shared HTTP helpers for the image and video tools.

Kept out of the tool classes so both share one retry policy, one set of error messages
and one place where the long-job timeouts live.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Mapping
from urllib.parse import urlparse

import requests

DEFAULT_BASE_URL = "https://apimaster.ai/v1"

# Documented client-side read timeouts per resolution tier. Anything shorter aborts a
# job that has already been billed.
IMAGE_TIMEOUT = {"1k": 200, "2k": 320, "4k": 620}

HINTS = {
    400: "Bad request. Check the model id and parameters.",
    401: "Unauthorized. The key is wrong, expired, or was copied with whitespace.",
    402: "Insufficient balance.",
    403: "Forbidden. This key may not be allowed to use this model.",
    404: "Not found. The Base URL should end with /v1.",
    408: "Generation timed out. Lower the resolution, or switch the tool to async mode.",
    429: "Rate limited. Try again shortly.",
}


class APIMasterError(RuntimeError):
    def __init__(self, status: int | None, detail: str = ""):
        hint = HINTS.get(status or 0, "Request failed.")
        prefix = f"HTTP {status}: " if status else ""
        super().__init__(f"{prefix}{hint} {detail}".strip())
        self.status = status


def base_url(credentials: Mapping[str, Any]) -> str:
    return str(credentials.get("base_url") or DEFAULT_BASE_URL).rstrip("/")


def headers(credentials: Mapping[str, Any]) -> dict[str, str]:
    key = str(credentials.get("api_key") or "").strip()
    if not key:
        raise APIMasterError(None, "No API key configured for this tool provider.")
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def post(credentials: Mapping[str, Any], path: str, body: dict, timeout: int) -> dict:
    response = requests.post(
        f"{base_url(credentials)}{path}", headers=headers(credentials), json=body, timeout=timeout
    )
    if not response.ok:
        raise APIMasterError(response.status_code, response.text[:200])
    return response.json()


def get(credentials: Mapping[str, Any], path: str, timeout: int = 30, params: dict | None = None) -> dict:
    response = requests.get(
        f"{base_url(credentials)}{path}", headers=headers(credentials), params=params, timeout=timeout
    )
    if not response.ok:
        raise APIMasterError(response.status_code, response.text[:200])
    return response.json()


def poll(
    read: Callable[[], dict],
    is_done: Callable[[dict], bool],
    is_failed: Callable[[dict], bool],
    initial_delay: float,
    label: str,
    interval: float = 4.0,
    max_seconds: float = 900.0,
) -> dict:
    """The first read is delayed because these jobs are never ready immediately."""
    deadline = time.time() + max_seconds
    time.sleep(initial_delay)
    while time.time() < deadline:
        payload = read()
        if is_done(payload):
            return payload
        if is_failed(payload):
            raise APIMasterError(None, f"{label} job failed: {str(payload)[:200]}")
        time.sleep(interval)
    raise APIMasterError(None, f"{label} job did not finish within {int(max_seconds)}s.")


def download(credentials: Mapping[str, Any], url: str, timeout: int = 600) -> bytes:
    # Compare hosts, not path prefixes: generated media comes back from the same domain
    # but outside /v1, while an upstream CDN rejects an unknown Authorization header.
    same_host = urlparse(url).netloc == urlparse(base_url(credentials)).netloc
    response = requests.get(
        url,
        headers={"Authorization": headers(credentials)["Authorization"]} if same_host else {},
        timeout=timeout,
        allow_redirects=True,
    )
    if not response.ok:
        raise APIMasterError(response.status_code, f"Download failed for {url}")
    return response.content
