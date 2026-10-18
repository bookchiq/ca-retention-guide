# California Appellate Justice Retention Guide (Nov 3, 2026)

A nonpartisan, source-linked record of the California Supreme Court and Court of Appeal justices on the November 3, 2026 retention ballot. The guide describes what each justice did, with links to the opinions. It does not grade, rank, or recommend.

- **Spec:** [SPEC.md](SPEC.md) (source of truth) and [DECISIONS.md](DECISIONS.md) (every change to rules or method)
- **Plan:** [docs/plans/](docs/plans/)
- **Guide output:** `guide/` (generated; published after verification)

## Data

Opinion data comes from [CourtListener](https://www.courtlistener.com/), a project of the Free Law Project: its quarterly bulk snapshot, plus the API for opinions filed since the snapshot. Raw downloads and the working database are never committed.

## Setup

```bash
uv sync
uv run pre-commit install
cp .env.example .env   # then add your CourtListener token
```

The repo is public. The pre-commit and pre-push hooks run `src/guard.py` and gitleaks to keep secrets, raw data, and unverified case records out of git. Install them before your first commit.

## Licenses

Code: MIT ([LICENSE](LICENSE)). Guide prose and data: CC BY 4.0 ([LICENSE-CONTENT](LICENSE-CONTENT)). Court opinions are public domain.
