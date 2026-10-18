"""Phase 1 ship gate (U12, SPEC §13).

    python -m src.acceptance                  # run every automatable check
    python -m src.acceptance owner-sample --seed N   # draw the owner's 10 summaries

Runs the checks that existing gates don't already cover, plus those gates
themselves, and prints PASS/FAIL per item. Items needing a person (owner spot
check, browser link check) are listed as manual.
"""

from __future__ import annotations

import json
import random
import subprocess
import sys
from pathlib import Path

from src import render

OWNER_SAMPLE_SIZE = 10


def check_pages(guide: Path) -> list[str]:
    failures = []
    for page in sorted((guide / "justices").glob("*.md")):
        text = page.read_text()
        name = page.relative_to(guide)
        for needle, label in (("## Limitations", "Limitations note"),
                              ("Data window:", "data window"), ("Last updated:", "last-updated")):
            if needle not in text:
                failures.append(f"{name}: missing {label}")
    for page in sorted(guide.rglob("*.md")):
        text = page.read_text()
        name = page.relative_to(guide)
        if render.PLACEHOLDER in text:
            failures.append(f"{name}: owner-decision placeholder not filled")
        if "draft (no release date set)" in text:
            failures.append(f"{name}: no release date set (render.snapshot_date)")
    return failures


def owner_sample(case_notes: Path, seed: int) -> list[dict]:
    records = [json.loads(line) for line in case_notes.read_text().splitlines() if line.strip()]
    listed = sorted((r for r in records if r.get("listing_decision") == "listed"),
                    key=lambda r: (r["justice_slug"], r["topic"], r["cl_opinion_id"]))
    return random.Random(seed).sample(listed, min(OWNER_SAMPLE_SIZE, len(listed)))


def _run(cmd: list[str], cwd: Path) -> bool:
    return subprocess.run(cmd, cwd=cwd, capture_output=True).returncode == 0


def main(argv: list[str] | None = None) -> int:
    import argparse

    from src import config

    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("owner-sample").add_argument("--seed", type=int, required=True)
    args = parser.parse_args(argv)
    settings = config.load()
    root = settings.repo_root

    if args.cmd == "owner-sample":
        picks = owner_sample(settings.path("case_notes"), args.seed)
        lines = [f"# Owner spot check (seed {args.seed})", "",
                 "Read each summary against the opinion; tick when it matches.", ""]
        lines += [f"- [ ] {r['justice_slug']}: *{r.get('case_name')}* — {r.get('summary')} "
                  f"[opinion]({r.get('opinion_url')})" for r in picks]
        out = settings.path("review") / "owner_check.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("\n".join(lines) + "\n")
        print(f"wrote {out}")
        return 0

    vdir = settings.path("validation")
    status = json.loads((vdir / "status.json").read_text()) if (vdir / "status.json").exists() \
        else {}
    decisions = (root / "DECISIONS.md").read_text()
    results = [
        ("Ballot re-checked against the SOS PDF", "SOS ballot re-check" in decisions),
        ("Parsing validation gate passed", bool(status.get("pooled"))),
        ("Tier 1 tagging precision ≥ 85%", (vdir / "report_tags.md").exists()
         and "target ≥ 85%: pass" in (vdir / "report_tags.md").read_text()),
        ("Public-repo guard (verified records, no secrets or raw data)",
         _run([sys.executable, "-m", "src.guard"], root)),
        ("Render: banned-word lint and baselines",
         _run([sys.executable, "-m", "src.render"], root)),
        ("Secret scan of full git history",
         _run(["gitleaks", "git", "--redact", "--no-banner", "--config", ".gitleaks.toml"], root)),
    ]
    page_failures = check_pages(settings.path("guide"))
    results.append(("Every page: window, last updated, limitations; placeholders filled",
                    not page_failures))
    for label, ok in results:
        print(f"{'PASS' if ok else 'FAIL'}  {label}")
    for f in page_failures:
        print(f"        {f}")
    print("MANUAL  Owner spot check of 10 summaries (python -m src.acceptance owner-sample)")
    print("MANUAL  Browser check of the 10 sampled CourtListener links")
    return 0 if all(ok for _, ok in results) else 1


if __name__ == "__main__":
    sys.exit(main())
