"""Tests for the public-repo guard (src/guard.py).

Each test builds a throwaway git repo, stages files, and runs the guard the
way the pre-commit hook does.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
FAKE_TOKEN = "0123456789abcdef0123456789abcdef01234567"  # gitleaks:allow (test value)


def git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init", "-q", "-b", "main")
    git(tmp_path, "config", "user.email", "test@example.com")
    git(tmp_path, "config", "user.name", "Test")
    return tmp_path


def write(repo, rel, text):
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    git(repo, "add", "-f", rel)


def record(**overrides):
    base = {
        "cl_opinion_id": 1,
        "justice_slug": "dato",
        "listing_decision": "listed",
        "opinion_url": "https://www.courtlistener.com/opinion/111/people-v-x/",
        "verified": True,
        "second_check": "passed",
    }
    base.update(overrides)
    return json.dumps(base)


def run_guard(repo, env_token=None, *extra):
    env = {"PATH": "/usr/bin:/bin:/opt/homebrew/bin", "HOME": str(repo)}
    if env_token is not None:
        env["COURTLISTENER_TOKEN"] = env_token
    return subprocess.run(
        [sys.executable, "-m", "src.guard", "--repo", str(repo), *extra],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )


def test_passes_on_empty_repo(repo):
    result = run_guard(repo)
    assert result.returncode == 0, result.stdout + result.stderr


def test_passes_on_verified_records(repo):
    lines = [record(), record(cl_opinion_id=2, second_check="not_sampled")]
    write(repo, "data/case_notes.jsonl", "\n".join(lines) + "\n")
    result = run_guard(repo)
    assert result.returncode == 0, result.stdout + result.stderr


def test_fails_on_unverified_record(repo):
    write(repo, "data/case_notes.jsonl", record(cl_opinion_id=42, verified=False) + "\n")
    result = run_guard(repo)
    assert result.returncode == 1
    assert "42" in result.stdout


def test_fails_on_pending_second_check(repo):
    write(repo, "data/case_notes.jsonl", record(second_check="pending") + "\n")
    result = run_guard(repo)
    assert result.returncode == 1
    assert "second_check" in result.stdout


def test_fails_on_tracked_sqlite(repo):
    write(repo, "data/cases.sqlite", "not really sqlite")
    result = run_guard(repo)
    assert result.returncode == 1
    assert "data/cases.sqlite" in result.stdout


@pytest.mark.parametrize("path", [".env", ".env.local", "data/raw/x.csv", "data/drafts/a.jsonl"])
def test_fails_on_forbidden_paths(repo, path):
    write(repo, path, "x")
    result = run_guard(repo)
    assert result.returncode == 1
    assert path in result.stdout


def test_allows_env_example(repo):
    write(repo, ".env.example", "COURTLISTENER_TOKEN=\n")
    result = run_guard(repo)
    assert result.returncode == 0, result.stdout


def test_fails_when_guide_cites_unpromoted_opinion(repo):
    write(repo, "data/case_notes.jsonl", record() + "\n")
    page = "See [case](https://www.courtlistener.com/opinion/999/people-v-y/).\n"
    write(repo, "guide/justices/x.md", page)
    result = run_guard(repo)
    assert result.returncode == 1
    assert "999" in result.stdout


def test_passes_when_guide_cites_promoted_opinion(repo):
    write(repo, "data/case_notes.jsonl", record() + "\n")
    page = "See [case](https://www.courtlistener.com/opinion/111/people-v-x/).\n"
    write(repo, "guide/justices/x.md", page)
    result = run_guard(repo)
    assert result.returncode == 0, result.stdout


def test_fails_on_exact_token_value_without_printing_it(repo):
    write(repo, "src/client.py", f'HEADERS = {{"Authorization": "Token {FAKE_TOKEN}"}}\n')
    result = run_guard(repo, env_token=FAKE_TOKEN)
    assert result.returncode == 1
    assert "src/client.py" in result.stdout
    assert FAKE_TOKEN not in result.stdout + result.stderr


def test_push_mode_checks_each_outgoing_commit(repo):
    write(repo, "README.md", "hi\n")
    git(repo, "commit", "-q", "-m", "base")
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True
    ).stdout.strip()
    write(repo, "data/case_notes.jsonl", record(verified=False) + "\n")
    git(repo, "commit", "-q", "--no-verify", "-m", "sneaky")
    git(repo, "rm", "-q", "data/case_notes.jsonl")
    git(repo, "commit", "-q", "-m", "cleanup")
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True
    ).stdout.strip()
    result = run_guard(repo, None, "--push", "--from-ref", base, "--to-ref", head)
    assert result.returncode == 1
    assert "verified" in result.stdout
