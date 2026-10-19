"""Render the guide (U11): index, methodology, one page per justice, CSV exports.

    python -m src.render

Pages are built in memory, linted for banned words (R19), and written only if
the lint passes. Output is deterministic (KTD12): "last updated" comes from
config, never the clock, and every list has a stable sort.
"""

from __future__ import annotations

import csv
import io
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from src import lint, topic_validate

TEMPLATES = Path(__file__).parent / "templates"
PLACEHOLDER = "TBD: correction contact (owner decision before publication)"
LISTING_SHOWN = 25
ORDINALS = {"1": "First", "2": "Second", "3": "Third", "4": "Fourth", "5": "Fifth", "6": "Sixth"}
CAREER_LABELS = {
    "prosecutor": "prosecutor", "public_defender": "public defender",
    "private_criminal_defense": "private criminal defense",
    "civil_plaintiff": "civil plaintiffs' counsel", "civil_defense": "civil defense counsel",
    "government_counsel": "government counsel", "appellate_court_staff": "appellate court staff",
    "trial_judge": "trial judge", "academia": "academia",
    "policy_or_political_staff": "policy or political staff", "other": "other",
}
TOPIC_TITLES = {
    "search_seizure": "Search and seizure", "interrogation": "Interrogation",
    "counsel_fair_trial": "Right to counsel", "jury_selection": "Jury selection",
    "racial_justice_act": "Racial Justice Act", "police_records": "Police records",
    "immigration_pleas": "Immigration consequences of pleas", "resentencing": "Resentencing",
    "arbitration": "Arbitration", "employment": "Employment", "consumer": "Consumer protection",
    "landlord_tenant": "Landlord and tenant", "transparency": "Public records and open meetings",
    "anti_slapp": "Anti-SLAPP", "taxpayer": "Taxes and fees",
    "land_use_housing": "Land use and housing",
}
UNDERCOUNT_NOTE_MIN = 0.25
NOTE_FIELDS = [
    "justice_slug", "topic", "cl_opinion_id", "case_name", "citation_or_docket", "date_filed",
    "published", "listing_decision", "exclusion_reason", "role", "listing_rule", "issue_type",
    "posture", "trial_court_ruling", "result_on_issue", "outcome", "vote", "summary",
    "opinion_url", "verified", "verified_by", "verified_date", "verification_notes",
    "second_check", "second_check_by", "second_check_date", "second_check_note",
]

# GitHub Pages (Jekyll) settings, written next to the pages so guide/ is the whole site.
JEKYLL_CONFIG = """\
title: California appellate justices on the November 3, 2026 ballot
description: A source-linked guide to the justices on the retention ballot. An experiment.
# Project site: served at https://bookchiq.github.io/ca-retention-guide/
baseurl: /ca-retention-guide
theme: jekyll-theme-primer
markdown: kramdown
kramdown:
  input: GFM
plugins:
  - jekyll-relative-links
  - jekyll-optional-front-matter
  - jekyll-default-layout
  - jekyll-titles-from-headings
relative_links:
  enabled: true
  collections: false
"""


class LintFailure(RuntimeError):
    pass


@dataclass
class Inputs:
    justices: list[dict]
    metrics: list[dict]
    case_notes: list[dict]
    reviewed: dict
    topics: dict
    validated: set[str]
    sc_dissents: dict | None
    window_start: str
    window_end: str
    updated: str | None
    bulk_snapshot: str
    tier2_enabled: bool
    correction_contact: str | None
    validation_summary: str
    tag_summary: str
    extra: dict = field(default_factory=dict)
    credit: str = ""
    topic_validation: dict = field(default_factory=dict)


def _num(value):
    if value in (None, ""):
        return None
    return float(value)


def _int_text(value) -> str:
    v = _num(value)
    return "—" if v is None else str(int(v))


def _true(value) -> bool:
    return str(value).strip().lower() in ("true", "1", "yes")


def _court_label(j: dict) -> str:
    if j["court"] == "supreme":
        return "California Supreme Court"
    label = f"Court of Appeal, {ORDINALS.get(str(j['district']), j['district'])} District"
    return label + (f", Division {j['division']}" if j.get("division") else "")


def _baseline_label(j: dict) -> str:
    if j["court"] == "supreme":
        return "the Supreme Court as a whole"
    district = f"the {ORDINALS.get(str(j['district']), j['district'])} District"
    return f"Division {j['division']} of {district}" if j.get("division") else district


def _short_name(j: dict) -> str:
    parts = [p for p in j["display_name"].replace(",", "").split()
             if p not in ("II", "III", "Jr.", "Jr")]
    return f"Justice {parts[-1]}"


def _career(j: dict) -> str:
    cats = [c for c in (j.get("prior_career") or "").split(";") if c]
    return ", ".join(CAREER_LABELS.get(c, c) for c in cats)


def _retention(j: dict) -> str:
    raw = (j.get("prior_retention") or "").strip()
    if not raw or raw == "none":
        return "None; this is the first retention vote"
    out = []
    for item in raw.split(";"):
        year, _, pct = item.partition(":")
        out.append(f"{year}: {pct}% yes")
    return "; ".join(out)


def _discipline(j: dict) -> str:
    value = (j.get("cjp_public_discipline") or "").strip()
    if value == "none_found":
        return f"None found as of {j.get('cjp_search_date')}"
    return value or "Not checked"


def _pct(v: float | None) -> str:
    return "—" if v is None else f"{100 * v:.0f}%"


def _glance(slug: str, j: dict, metrics: dict) -> list[dict]:
    def m(name):
        return metrics.get((slug, name, ""), {})

    rows = []
    authored = _int_text(m("authored_total").get("value"))
    if j["court"] != "supreme" and m("authored_published"):
        authored += f" ({_int_text(m('authored_published').get('value'))} published)"
    rows.append({"label": "Majority opinions written", "value": authored, "baseline": "—"})
    rows.append({"label": "Panels sat on", "value": _int_text(m("panels").get("value")),
                 "baseline": "—"})
    if j["court"] != "supreme":
        r = m("publication_rate")
        rows.append({"label": "Share of written opinions published",
                     "value": _pct(_num(r.get("value"))),
                     "baseline": f"{_pct(_num(r.get('baseline')))} of "
                                 f"{_int_text(r.get('baseline_n'))} opinions"})
    for label, key in (("Dissents", "dissents"), ("Concurrences", "concurrences")):
        rows.append({"label": f"{label} written", "value": _int_text(m(key).get("value")),
                     "baseline": "—"})
        r = m(f"{key}_per_100_panels")
        v, b = _num(r.get("value")), _num(r.get("baseline"))
        rows.append({"label": f"{label} per 100 panels",
                     "value": "—" if v is None else f"{v:.1f}",
                     "baseline": "not available" if b is None else
                     f"{b:.1f} across {_int_text(r.get('baseline_n'))} panel seats"})
    return rows


_CA_SUFFIX = re.compile(r"\s+CA\d/\d$")
_MODIFIED_DOCKET = re.compile(r"^([A-HS]\d{6})[MA]$")


def _display_note(note: dict) -> dict:
    """Drop CourtListener's display suffixes: ' CA4/1' on unpublished case names and the
    'M' marking a modified opinion's docket. The stored record keeps both."""
    shown = dict(note)
    shown["case_name"] = _CA_SUFFIX.sub("", note.get("case_name") or "")
    shown["citation_or_docket"] = _MODIFIED_DOCKET.sub(r"\1", note.get("citation_or_docket")
                                                       or "")
    return shown


def _listing(slug: str, topic: str, inputs: Inputs) -> dict:
    reviewed = inputs.reviewed.get((slug, topic))
    if not reviewed:
        return {"status": "not_reviewed"}
    listed = sorted(
        (n for n in inputs.case_notes if n.get("justice_slug") == slug
         and n.get("topic") == topic and n.get("listing_decision") == "listed"),
        key=lambda n: (n["date_filed"], n["cl_opinion_id"]), reverse=True)
    if not listed:
        return {"status": "none", "queued": reviewed.get("queued", 0)}
    return {"status": "listed", "total": len(listed),
            "shown": [_display_note(n) for n in listed[:LISTING_SHOWN]]}


def _justice_context(j: dict, inputs: Inputs, metrics: dict) -> dict:
    slug = j["slug"]
    key = "supreme" if j["court"] == "supreme" else str(j["district"])
    limited = _true(j.get("limited_record"))
    ctx = dict(j)
    first_start = (j.get("appellate_start_date") or "")
    padded = "-".join((first_start.split("-") + ["01", "01"])[:3]) if first_start else ""
    ctx.update(
        court_label=_court_label(j), baseline_label=_baseline_label(j),
        short_name=_short_name(j), career_text=_career(j), retention_text=_retention(j),
        discipline_text=_discipline(j), limited_record=limited,
        not_yet_seated=bool(first_start) and first_start > inputs.window_end,
        validated=key in inputs.validated,
        window_start=max(inputs.window_start, padded) if padded else inputs.window_start,
        appointed_text=(f"{first_start[:4]}, Gov. {j['appointing_governor']}"
                        if first_start and j.get("appointing_governor") else first_start[:4]
                        or "—"),
    )
    ctx["glance"] = _glance(slug, j, metrics) if ctx["validated"] and not limited else []

    review_tiers = {1, 2} if inputs.tier2_enabled else {1}
    topics = []
    for topic, spec in sorted(inputs.topics.items(), key=lambda kv: (kv[1]["tier"], kv[0])):
        def tm(name, _topic=topic):
            return _int_text(metrics.get((slug, name, _topic), {}).get("value"))

        listing = None
        if spec["tier"] in review_tiers and _true(j.get("sd_ballot")):
            listing = _listing(slug, topic, inputs)
        elif spec["tier"] == 1:
            listing = {"status": "not_reviewed"}
        rounds = inputs.topic_validation.get(topic, {}).get("rounds", [])
        missed = rounds[-1].get("undercount_share") if rounds else None
        topics.append({
            "topic": topic, "title": TOPIC_TITLES.get(topic, topic),
            "validated": bool(spec.get("validated")),
            # Counts that likely miss a quarter or more of the topic get a visible caveat.
            "undercount_pct": (round(100 * missed) if missed is not None
                               and missed >= UNDERCOUNT_NOTE_MIN else None),
            "authored": tm("topic_authored"), "panels": tm("topic_panels"),
            "contested_majority": tm("contested_majority"),
            "contested_dissent": tm("contested_dissent"), "listing": listing,
        })
    # Owner decision 2026-10-18: counts from unchecked keyword rules stay off the pages (they
    # remain in metrics.csv, marked unvalidated). Hand-verified listings are always shown.
    ctx["topics"] = [t for t in topics if t["validated"] or t["listing"]]
    ctx["hidden_topics"] = len(topics) - len(ctx["topics"])

    sc = inputs.sc_dissents or {}
    if slug in sc.get("justices", {}):
        src = sc["source"]
        ctx["denial_dissents"] = {**sc["justices"][slug], "term": sc["term"],
                                  "author": src["author"], "publication_name": src["publication"],
                                  "title": src["title"], "url": src["url"], "date": src["date"]}
    else:
        ctx["denial_dissents"] = None

    tier1 = [t for t in topics if inputs.topics[t["topic"]]["tier"] == 1]
    if limited:
        ctx["record_status"] = "limited appellate record"
        ctx["index_listed"] = "—"
    elif _true(j.get("sd_ballot")) and tier1 and all(
            t["listing"]["status"] != "not_reviewed" for t in tier1):
        ctx["record_status"] = "verified"
        ctx["index_listed"] = str(sum(t["listing"].get("total", 0) for t in tier1))
    else:
        ctx["record_status"] = "metrics only"
        ctx["index_listed"] = "not yet reviewed"
    if ctx["validated"] and not limited:
        ctx["index_authored"] = _int_text(metrics.get((slug, "authored_total", ""), {})
                                          .get("value"))
        sep = sum(_num(metrics.get((slug, k, ""), {}).get("value")) or 0
                  for k in ("dissents", "concurrences"))
        ctx["index_separate"] = str(int(sep))
    else:
        ctx["index_authored"] = ctx["index_separate"] = "—"
    return ctx


def _sources(value) -> str:
    """' ([source](u))' for one URL, ' (sources: [1](u1), [2](u2))' for several."""
    urls = [u.strip() for u in str(value or "").split(";") if u.strip()]
    if not urls:
        return ""
    if len(urls) == 1:
        return f" ([source]({urls[0]}))"
    return " (sources: " + ", ".join(f"[{i}]({u})" for i, u in enumerate(urls, 1)) + ")"


def _tidy(md: str) -> str:
    """Blank line before every heading and blockquote; no runs of blank lines."""
    out: list[str] = []
    for line in md.splitlines():
        if line.startswith(("#", ">")) and out and out[-1].strip():
            out.append("")
        if not line.strip() and out and not out[-1].strip():
            continue
        out.append(line.rstrip())
    while out and not out[-1].strip():
        out.pop()
    return "\n".join(out) + "\n"


def _csv_text(rows: list[dict], fields: list[str]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in fields})
    return buf.getvalue()


def _review_stats(notes: list[dict]) -> dict:
    """Counts for the methodology page, computed from the published records."""
    sampled = [n for n in notes if n.get("second_check") in ("passed", "failed")]
    reasons: dict[str, int] = {}
    for n in notes:
        if n.get("listing_decision") == "excluded":
            key = n.get("exclusion_reason") or "unspecified"
            reasons[key] = reasons.get(key, 0) + 1
    return {
        "justices": len({n["justice_slug"] for n in notes}),
        "records": len(notes),
        "listed": sum(1 for n in notes if n.get("listing_decision") == "listed"),
        "excluded": sum(reasons.values()),
        "reasons": sorted(reasons.items(), key=lambda kv: (-kv[1], kv[0])),
        "sampled": len(sampled),
        "failed": sum(1 for n in sampled if n["second_check"] == "failed"),
    }


def _topic_rows(inputs: Inputs) -> list[dict]:
    """One row per topic for the methodology page: definition and latest validation round."""
    def pct(x):
        return "—" if x is None else f"{100 * x:.0f}%"

    order = list(TOPIC_TITLES)
    rows = []
    for topic in sorted(inputs.topics, key=lambda t: (order.index(t) if t in order else 99, t)):
        spec = inputs.topics[topic]
        rounds = inputs.topic_validation.get(topic, {}).get("rounds", [])
        last = rounds[-1] if rounds else None
        rows.append({
            "title": TOPIC_TITLES.get(topic, topic),
            "definition": " ".join((spec.get("definition") or "").split()),
            "precision": (f"{pct(last['precision'])} (N = {last['precision_n']})" if last
                          else "not yet checked"),
            "undercount": topic_validate.undercount_text(last) if last else "—",
            "shown": "yes" if spec.get("validated") else "no",
        })
    return rows


def build(inputs: Inputs) -> dict[str, str]:
    env = Environment(loader=FileSystemLoader(TEMPLATES), undefined=StrictUndefined,
                      keep_trailing_newline=True, trim_blocks=True, lstrip_blocks=True)
    env.filters["sources"] = _sources
    metrics = {(r["slug"], r["metric"], r.get("topic") or ""): r for r in inputs.metrics}
    updated = inputs.updated or "draft (no release date set)"
    contexts = [_justice_context(j, inputs, metrics) for j in inputs.justices]
    files: dict[str, str] = {}
    for ctx in contexts:
        files[f"justices/{ctx['slug']}.md"] = _tidy(env.get_template("justice.md.j2").render(
            j=ctx, window_end=inputs.window_end, updated=updated, credit=inputs.credit))
    correction = inputs.correction_contact or PLACEHOLDER
    files["index.md"] = _tidy(env.get_template("index.md.j2").render(
        justices=contexts, updated=updated, credit=inputs.credit, window_start=inputs.window_start,
        correction_contact=correction))
    files["methodology.md"] = _tidy(env.get_template("methodology.md.j2").render(
        updated=updated, bulk_snapshot=inputs.bulk_snapshot, window_start=inputs.window_start,
        validation_summary=inputs.validation_summary, tag_summary=inputs.tag_summary,
        correction_contact=correction, credit=inputs.credit,
        stats=_review_stats(inputs.case_notes), topic_rows=_topic_rows(inputs)))
    files["_config.yml"] = JEKYLL_CONFIG

    justice_fields = list(inputs.justices[0].keys()) if inputs.justices else []
    files["data/justices.csv"] = _csv_text(inputs.justices, justice_fields)
    metric_fields = ["slug", "metric", "topic", "value", "baseline", "baseline_n", "n",
                     "window_start", "window_end", "note"]
    unchecked = {t for t, spec in inputs.topics.items() if not spec.get("validated")}
    metric_rows = [dict(r, note="unvalidated keywords") if r.get("topic") in unchecked and not
                   r.get("note") else r for r in inputs.metrics]
    files["data/metrics.csv"] = _csv_text(
        sorted(metric_rows, key=lambda r: (r["slug"], r.get("topic") or "", r["metric"])),
        metric_fields)
    notes = sorted(inputs.case_notes, key=lambda n: (
        n["justice_slug"], n["topic"], n["date_filed"], n["cl_opinion_id"]))
    files["data/case_notes.csv"] = _csv_text(notes, NOTE_FIELDS)
    for slug in sorted({n["justice_slug"] for n in notes}):
        files[f"data/case_notes/{slug}.csv"] = _csv_text(
            [n for n in notes if n["justice_slug"] == slug], NOTE_FIELDS)
    return files


def render(inputs: Inputs, out_dir: Path) -> list[Path]:
    files = build(inputs)
    exceptions = lint.load_exceptions()
    hits = []
    for name, text in sorted(files.items()):
        if name.endswith(".md"):
            hits += lint.check_text(name, text, exceptions)
    if hits:
        raise LintFailure("Banned words found:\n" + "\n".join(
            f"  {name}:{line}: {term}" for name, line, term in hits))
    written = []
    for name, text in sorted(files.items()):
        path = out_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        written.append(path)
    return written


def main() -> int:
    import yaml

    from src import config, justices, review, tag

    settings = config.load()
    root = settings.repo_root
    vdir = settings.path("validation")
    status_file = vdir / "status.json"
    status = json.loads(status_file.read_text()) if status_file.exists() else {"districts": {}}
    metrics_file = settings.path("guide") / "data" / "metrics.csv"
    metrics = list(csv.DictReader(open(metrics_file))) if metrics_file.exists() else []
    ws = review.Workspace(settings.path("drafts"), settings.path("review") / "queue",
                          settings.path("case_notes"))
    notes = review._read_jsonl(ws.case_notes)
    report = vdir / "report_parse.md"
    tags = vdir / "report_tags.md"
    inputs = Inputs(
        justices=justices.load_justices(), metrics=metrics, case_notes=notes,
        reviewed=review.load_reviewed(ws), topics=tag.load_keywords(),
        validated={d for d, ok in status.get("districts", {}).items() if ok},
        sc_dissents=yaml.safe_load((root / "data" / "sc_denial_dissents.yaml").read_text()),
        window_start=settings.raw["window"]["start"],
        window_end=settings.raw["render"].get("snapshot_date") or "2026-10-27",
        updated=settings.raw["render"].get("snapshot_date"),
        bulk_snapshot=settings.raw["bulk"]["snapshot"],
        tier2_enabled=bool(settings.raw["phase"].get("tier2_enabled")),
        correction_contact=settings.raw["project"].get("correction_contact"),
        credit=settings.raw["project"].get("credit") or "",
        topic_validation=(json.loads((vdir / "topic_status.json").read_text())
                          if (vdir / "topic_status.json").exists() else {}),
        validation_summary=("Full results: [validation report](https://github.com/bookchiq/"
                            "ca-retention-guide/blob/main/data/validation/report_parse.md)."
                            if report.exists() else "Validation has not been run yet."),
        tag_summary=(tags.read_text().split("\n", 2)[-1].strip() if tags.exists()
                     else "Tag validation has not been run yet."),
    )
    try:
        written = render(inputs, settings.path("guide"))
    except LintFailure as exc:
        print(exc)
        return 1
    print(f"wrote {len(written)} files to {settings.path('guide')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
