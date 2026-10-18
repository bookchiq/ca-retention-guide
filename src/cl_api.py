"""CourtListener REST API v4 client (U4).

Built for small volumes (the October gap after the bulk snapshot, plus a few
checks): a fixed interval between requests keeps a run under the documented
limits (5/min, 50/hour, 125/day for free accounts). Every 200 response is
cached in SQLite by URL, so reruns cost nothing. Cursor pagination resumes
from the last completed page.

The token is sent only in the Authorization header and is never logged.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from typing import Any

import requests

from src.config import Settings

log = logging.getLogger(__name__)

NETWORK_ATTEMPTS = 4
RETRYABLE_STATUS = {500, 502, 503, 504}


class StopRun(RuntimeError):
    """Raised when continuing would break the rate limits or need a long wait."""


class Client:
    def __init__(
        self,
        settings: Settings,
        conn: sqlite3.Connection,
        session: Any | None = None,
        now: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ):
        api = settings.raw.get("api", {})
        project = settings.raw.get("project", {})
        self.settings = settings
        self.conn = conn
        self.session = session or requests.Session()
        self.now = now
        self.sleep = sleep
        self.base = api.get("base", "https://www.courtlistener.com/api/rest/v4/")
        self.interval = float(api.get("min_interval_seconds", 75))
        self.max_wait = float(api.get("max_retry_after_seconds", 3600))
        contact = settings.contact_email or "no-contact-configured"
        self.user_agent = (
            f"{project.get('name', 'ca-retention-guide')}/0.1 "
            f"(+{project.get('repo_url', '')}; {contact})"
        )
        self._last_request: float | None = None

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Token {self.settings.api_token()}",
            "User-Agent": self.user_agent,
            "Accept": "application/json",
        }

    def _pace(self) -> None:
        if self._last_request is not None:
            wait = self._last_request + self.interval - self.now()
            if wait > 0:
                self.sleep(wait)
        self._last_request = self.now()

    def _cached(self, url: str) -> Any | None:
        row = self.conn.execute("SELECT body FROM http_cache WHERE url = ?", (url,)).fetchone()
        return json.loads(row["body"]) if row else None

    def _store(self, url: str, status: int, body: Any) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO http_cache (url, status, body, fetched_at) VALUES (?, ?, ?, ?)",
            (url, status, json.dumps(body), datetime.now(UTC).isoformat()),
        )
        self.conn.commit()

    def get(self, url: str) -> Any:
        """GET a full URL, using the cache when possible."""
        cached = self._cached(url)
        if cached is not None:
            return cached
        headers = self._headers()  # raises before any network call if no token

        for attempt in range(1, NETWORK_ATTEMPTS + 1):
            self._pace()
            try:
                resp = self.session.get(url, headers=headers, timeout=60)
            except (requests.RequestException, ConnectionError) as exc:
                log.warning("GET %s failed (%s), attempt %d", url, type(exc).__name__, attempt)
                if attempt == NETWORK_ATTEMPTS:
                    raise
                self.sleep(2**attempt * 5)
                continue

            if resp.status_code == 429:
                retry_after = float(resp.headers.get("Retry-After", self.max_wait + 1))
                if retry_after > self.max_wait:
                    raise StopRun(
                        f"Rate limited: Retry-After {retry_after:.0f}s exceeds the "
                        f"configured maximum of {self.max_wait:.0f}s. Rerun later; "
                        "completed pages are cached."
                    )
                log.warning("429 on %s; waiting %.0fs per Retry-After", url, retry_after)
                self.sleep(retry_after)
                continue
            if resp.status_code in RETRYABLE_STATUS and attempt < NETWORK_ATTEMPTS:
                log.warning("HTTP %d on %s, attempt %d", resp.status_code, url, attempt)
                self.sleep(2**attempt * 5)
                continue
            if resp.status_code != 200:
                raise StopRun(f"HTTP {resp.status_code} on {url}: {resp.text[:300]}")

            body = resp.json()
            self._store(url, resp.status_code, body)
            return body

        raise StopRun(f"Gave up on {url} after {NETWORK_ATTEMPTS} attempts")

    def paginate(self, job: str, first_url: str) -> Iterator[dict[str, Any]]:
        """Yield results across cursor pages, resuming job `job` where it stopped."""
        row = self.conn.execute(
            "SELECT next_url, done FROM api_cursors WHERE job = ?", (job,)
        ).fetchone()
        if row and row["done"]:
            return
        url = row["next_url"] if row and row["next_url"] else first_url

        while url:
            page = self.get(url)
            yield from page.get("results", [])
            url = page.get("next")
            self.conn.execute(
                "INSERT OR REPLACE INTO api_cursors (job, next_url, done) VALUES (?, ?, ?)",
                (job, url, 0 if url else 1),
            )
            self.conn.commit()
