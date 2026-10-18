"""Public-repo guard.

Blocks anything that must never be published: secrets, raw caches, databases,
working drafts, unverified case records, and guide pages citing opinions that
were not promoted. Runs as a pre-commit hook (index), a pre-push hook (every
outgoing commit), and in CI.

Usage:
    python -m src.guard                     # check the index (staged + tracked)
    python -m src.guard --push              # check commits being pushed
        [--from-ref SHA --to-ref SHA]       # (defaults from pre-commit env vars)

Never prints the token value.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable, Iterable
from pathlib import Path

from dotenv import dotenv_values

CASE_NOTES = "data/case_notes.jsonl"
ALLOWED_SECOND_CHECK = {"passed", "not_sampled"}
OPINION_URL = re.compile(r"courtlistener\.com/opinion/(\d+)/")
ZERO_SHA = "0" * 40
MIN_TOKEN_LENGTH = 20

FORBIDDEN_PREFIXES = ("data/raw/", "data/drafts/", "data/review/")
FORBIDDEN_SUFFIXES = (".sqlite", ".sqlite-journal", ".sqlite-wal", ".sqlite-shm")


def is_forbidden_path(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    if name == ".env" or (name.startswith(".env.") and name != ".env.example"):
        return True
    if path.startswith(FORBIDDEN_PREFIXES):
        return True
    return path.endswith(FORBIDDEN_SUFFIXES)


def check_tree(paths: Iterable[str], read: Callable[[str], bytes], token: str | None) -> list[str]:
    """Return a list of violation messages for one tree (index or commit)."""
    paths = list(paths)
    problems: list[str] = []

    for path in paths:
        if is_forbidden_path(path):
            problems.append(f"{path}: must never be committed")

    promoted_ids: set[str] = set()
    if CASE_NOTES in paths:
        text = read(CASE_NOTES).decode("utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                problems.append(f"{CASE_NOTES}:{lineno}: not valid JSON")
                continue
            label = f"{CASE_NOTES}:{lineno} (cl_opinion_id {rec.get('cl_opinion_id')})"
            if rec.get("verified") is not True:
                problems.append(f"{label}: record is not verified")
            if rec.get("second_check") not in ALLOWED_SECOND_CHECK:
                problems.append(
                    f"{label}: second_check is {rec.get('second_check')!r}, "
                    f"needs one of {sorted(ALLOWED_SECOND_CHECK)}"
                )
            match = OPINION_URL.search(str(rec.get("opinion_url", "")))
            if match:
                promoted_ids.add(match.group(1))

    for path in paths:
        if not path.startswith("guide/"):
            continue
        text = read(path).decode("utf-8", errors="replace")
        for cited in sorted(set(OPINION_URL.findall(text))):
            if cited not in promoted_ids:
                problems.append(f"{path}: cites opinion {cited}, which is not in {CASE_NOTES}")

    if token:
        needle = token.encode()
        for path in paths:
            if needle in read(path):
                problems.append(f"{path}: contains the COURTLISTENER_TOKEN value")

    return problems


def git(repo: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True
    ).stdout


def index_tree(repo: Path) -> tuple[list[str], Callable[[str], bytes]]:
    paths = git(repo, "ls-files", "-z").decode().split("\0")
    paths = [p for p in paths if p]
    return paths, lambda p: git(repo, "show", f":{p}")


def commit_tree(repo: Path, sha: str) -> tuple[list[str], Callable[[str], bytes]]:
    paths = git(repo, "ls-tree", "-r", "-z", "--name-only", sha).decode().split("\0")
    paths = [p for p in paths if p]
    return paths, lambda p: git(repo, "show", f"{sha}:{p}")


def outgoing_commits(repo: Path, from_ref: str | None, to_ref: str) -> list[str]:
    if from_ref and from_ref != ZERO_SHA:
        spec = [f"{from_ref}..{to_ref}"]
    else:
        spec = [to_ref, "--not", "--remotes"]
    out = git(repo, "rev-list", *spec).decode().split()
    return out


def load_token(repo: Path) -> str | None:
    token = os.environ.get("COURTLISTENER_TOKEN") or dotenv_values(repo / ".env").get(
        "COURTLISTENER_TOKEN"
    )
    if token and len(token.strip()) >= MIN_TOKEN_LENGTH:
        return token.strip()
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", default=".", help="repository root")
    parser.add_argument("--push", action="store_true", help="check commits being pushed")
    parser.add_argument("--from-ref", default=os.environ.get("PRE_COMMIT_FROM_REF"))
    parser.add_argument("--to-ref", default=os.environ.get("PRE_COMMIT_TO_REF", "HEAD"))
    args = parser.parse_args(argv)

    repo = Path(args.repo).resolve()
    token = load_token(repo)
    problems: list[str] = []

    if args.push:
        for sha in outgoing_commits(repo, args.from_ref, args.to_ref):
            paths, read = commit_tree(repo, sha)
            problems += [f"commit {sha[:10]}: {p}" for p in check_tree(paths, read, token)]
    else:
        paths, read = index_tree(repo)
        problems += check_tree(paths, read, token)

    if problems:
        print("Public-repo guard failed:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
