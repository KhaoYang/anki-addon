from __future__ import annotations

import json
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class NetworkError(Exception):
    pass


def request_json(url: str, *, payload: dict | None = None, headers: dict[str, str] | None = None, timeout: float = 20, retries: int = 2) -> dict:
    body = json.dumps(payload).encode() if payload is not None else None
    default_headers = {"User-Agent": "AnkiContextExplanations/1.0 (educational add-on)", "Accept": "application/json"}
    if body is not None:
        default_headers["Content-Type"] = "application/json"
    default_headers.update(headers or {})
    for attempt in range(retries + 1):
        try:
            req = Request(url, data=body, headers=default_headers, method="POST" if body is not None else "GET")
            with urlopen(req, timeout=timeout) as response:
                data = json.load(response)
            if not isinstance(data, dict):
                raise NetworkError("Unexpected API response")
            return data
        except HTTPError as exc:
            if exc.code in (429, 500, 502, 503, 504) and attempt < retries:
                delay = min(float(exc.headers.get("Retry-After", 0) or 0), 5) if exc.code == 429 else 0
                time.sleep(max(delay, 0.5 * (2 ** attempt)))
                continue
            if exc.code == 429:
                raise NetworkError("API rate limit reached; retry later") from exc
            if exc.code in (401, 403):
                raise NetworkError("API authentication failed; check the key and provider") from exc
            raise NetworkError(f"API returned HTTP {exc.code}") from exc
        except (URLError, TimeoutError, OSError) as exc:
            if attempt < retries:
                time.sleep(0.5 * (2 ** attempt))
                continue
            raise NetworkError("Network request timed out or failed") from exc
    raise NetworkError("Network request failed")
