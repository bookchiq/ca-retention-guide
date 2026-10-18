"""U4: CourtListener API client — pacing, Retry-After, caching, cursor resume,
and keeping the token out of logs."""

import json
import logging

import pytest

from src import cl_api, db
from src.config import Settings

FAKE_TOKEN = "abcdefabcdefabcdefabcdefabcdefabcdefabcd"  # gitleaks:allow (test value)


class FakeResponse:
    def __init__(self, status, body=None, headers=None):
        self.status_code = status
        self._body = body if body is not None else {}
        self.headers = headers or {}
        self.text = json.dumps(self._body)

    def json(self):
        return self._body


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, headers=None, timeout=None):
        self.calls.append({"url": url, "headers": headers})
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class FakeClock:
    def __init__(self):
        self.now = 1000.0
        self.sleeps = []

    def time(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def make_settings(tmp_path, token=FAKE_TOKEN, interval=10, max_wait=600):
    raw = {
        "project": {"name": "ca-retention-guide", "repo_url": "https://example.org/repo"},
        "api": {
            "base": "https://cl.example/api/rest/v4/",
            "min_interval_seconds": interval,
            "max_retry_after_seconds": max_wait,
        },
    }
    return Settings(raw=raw, repo_root=tmp_path, contact_email="a@b.org", _token=token)


def make_client(tmp_path, responses, **kw):
    session = FakeSession(responses)
    clock = FakeClock()
    conn = db.connect(":memory:")
    client = cl_api.Client(
        make_settings(tmp_path, **kw), conn, session=session, now=clock.time, sleep=clock.sleep
    )
    return client, session, clock, conn


def test_second_request_waits_for_interval(tmp_path):
    client, session, clock, _ = make_client(
        tmp_path, [FakeResponse(200, {"a": 1}), FakeResponse(200, {"b": 2})]
    )
    client.get("https://cl.example/api/rest/v4/x/")
    client.get("https://cl.example/api/rest/v4/y/")
    assert len(session.calls) == 2
    assert sum(clock.sleeps) >= 10


def test_retry_after_is_honored(tmp_path):
    client, session, clock, _ = make_client(
        tmp_path,
        [FakeResponse(429, headers={"Retry-After": "120"}), FakeResponse(200, {"ok": True})],
    )
    assert client.get("https://cl.example/api/rest/v4/x/") == {"ok": True}
    assert max(clock.sleeps) >= 120
    assert len(session.calls) == 2


def test_retry_after_above_max_stops_run(tmp_path):
    client, session, _, _ = make_client(
        tmp_path, [FakeResponse(429, headers={"Retry-After": "86400"})], max_wait=600
    )
    with pytest.raises(cl_api.StopRun, match="Retry-After"):
        client.get("https://cl.example/api/rest/v4/x/")
    assert len(session.calls) == 1


def test_cached_url_served_without_network(tmp_path):
    client, session, clock, _ = make_client(tmp_path, [FakeResponse(200, {"n": 1})])
    first = client.get("https://cl.example/api/rest/v4/x/?a=1")
    clock.sleeps.clear()
    second = client.get("https://cl.example/api/rest/v4/x/?a=1")
    assert first == second == {"n": 1}
    assert len(session.calls) == 1
    assert clock.sleeps == []


def test_missing_token_stops_before_network(tmp_path):
    client, session, _, _ = make_client(tmp_path, [], token=None)
    with pytest.raises(RuntimeError, match="COURTLISTENER_TOKEN"):
        client.get("https://cl.example/api/rest/v4/x/")
    assert session.calls == []


def test_error_log_never_contains_token(tmp_path, caplog):
    caplog.set_level(logging.DEBUG)
    client, session, _, _ = make_client(
        tmp_path, [ConnectionError("boom")] * 5
    )
    with pytest.raises(ConnectionError):
        client.get("https://cl.example/api/rest/v4/x/")
    assert FAKE_TOKEN not in caplog.text
    assert "Authorization" not in caplog.text


def test_headers_carry_token_and_user_agent(tmp_path):
    client, session, _, _ = make_client(tmp_path, [FakeResponse(200, {})])
    client.get("https://cl.example/api/rest/v4/x/")
    headers = session.calls[0]["headers"]
    assert headers["Authorization"] == f"Token {FAKE_TOKEN}"
    assert "ca-retention-guide" in headers["User-Agent"]
    assert "a@b.org" in headers["User-Agent"]


def test_paginate_follows_next_and_resumes_from_cursor(tmp_path):
    page1 = {"results": [{"id": 1}], "next": "https://cl.example/api/rest/v4/o/?cursor=2"}
    page2 = {"results": [{"id": 2}], "next": "https://cl.example/api/rest/v4/o/?cursor=3"}
    client, session, _, conn = make_client(
        tmp_path, [FakeResponse(200, page1)] + [ConnectionError("down")] * 4
    )
    seen = []
    with pytest.raises(ConnectionError):
        for row in client.paginate("job1", "https://cl.example/api/rest/v4/o/"):
            seen.append(row["id"])
    assert seen == [1]

    page3 = {"results": [{"id": 3}], "next": None}
    session2 = FakeSession([FakeResponse(200, page2), FakeResponse(200, page3)])
    clock = FakeClock()
    client2 = cl_api.Client(
        make_settings(tmp_path), conn, session=session2, now=clock.time, sleep=clock.sleep
    )
    seen2 = [row["id"] for row in client2.paginate("job1", "https://cl.example/api/rest/v4/o/")]
    assert seen2 == [2, 3]
    assert session2.calls[0]["url"].endswith("cursor=2")
    # A finished job yields nothing more on rerun.
    assert list(client2.paginate("job1", "https://cl.example/api/rest/v4/o/")) == []
