"""Pull a stratified sample of California opinions straight from the bulk file
(works on a partially downloaded file) for parser development.

Writes one text file per opinion to data/review/samples/ (gitignored):
<docket-prefix>_<cl_opinion_id>.txt, with a small header of known metadata.

Usage: uv run python scripts/sample_opinions.py [per_prefix=5]
"""

import sys
from collections import Counter

sys.path.insert(0, ".")
from src import bulk, config, db, textutil  # noqa: E402

PREFIXES = ["A", "B", "C", "D", "E", "F", "G", "H", "S"]


def main(per_prefix: int) -> None:
    settings = config.load()
    conn = db.connect(settings.path("database"))
    clusters = {
        r["cl_cluster_id"]: r
        for r in conn.execute(
            "SELECT cl_cluster_id, court, docket_number, date_filed, precedential_status, "
            "case_name FROM clusters WHERE source LIKE 'bulk%'"
        )
    }
    out = settings.path("review") / "samples"
    out.mkdir(parents=True, exist_ok=True)
    got: Counter = Counter()
    snap = settings.raw["bulk"]["snapshot"]
    try:
        for row in bulk.read_rows(settings.path("bulk") / f"opinions-{snap}.csv.bz2"):
            c = clusters.get(int(row["cluster_id"]))
            if not c:
                continue
            prefix = "S" if c["court"] == "cal" else (c["docket_number"] or "?")[:1].upper()
            if prefix not in PREFIXES or got[prefix] >= per_prefix:
                continue
            text, field = textutil.choose_text(row)
            if len(text) < 2000:
                continue
            header = (
                f"cl_opinion_id: {row['id']}\ncluster: {c['cl_cluster_id']}\n"
                f"docket: {c['docket_number']}\ndate: {c['date_filed']}\n"
                f"status: {c['precedential_status']}\ntype: {row['type']}\nfield: {field}\n"
                f"case: {c['case_name']}\n----\n"
            )
            (out / f"{prefix}_{row['id']}.txt").write_text(header + text)
            got[prefix] += 1
            if all(got[p] >= per_prefix for p in PREFIXES):
                break
    except (EOFError, OSError) as exc:  # partial file: stop at the end of what exists
        print(f"Stopped at end of available data: {type(exc).__name__}")
    print(dict(got))


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 5)
