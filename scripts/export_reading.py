"""Export the opinion text for each queued case to data/review/reading/<id>.txt (gitignored),
with the queue entry's metadata on top, so reading sessions work from files.

Usage: uv run python scripts/export_reading.py SLUG [SLUG ...]
"""

import json
import sys

sys.path.insert(0, ".")
from src import config, db  # noqa: E402


def main(slugs: list[str]) -> None:
    settings = config.load()
    conn = db.connect(settings.path("database"))
    out = settings.path("review") / "reading"
    out.mkdir(parents=True, exist_ok=True)
    for slug in slugs:
        queue = settings.path("review") / "queue" / f"{slug}__search_seizure.jsonl"
        n = 0
        for line in queue.read_text().splitlines():
            entry = json.loads(line)
            text = conn.execute("SELECT text FROM opinions WHERE cl_opinion_id = ?",
                                (entry["cl_opinion_id"],)).fetchone()[0]
            head = "\n".join(f"{k}: {v}" for k, v in sorted(entry.items()))
            (out / f"{entry['cl_opinion_id']}.txt").write_text(f"{head}\n----\n{text}")
            n += 1
        print(f"{slug}: {n} opinions exported")


if __name__ == "__main__":
    main(sys.argv[1:])
