"""Cut the header plus the first N records of a bulk CSV, byte-for-byte.

Keeps the snapshot's real quoting and backslash escapes so tests exercise the
same format as the full files.

Usage: uv run python scripts/cut_bulk_fixture.py SRC.csv.bz2 DEST.csv.bz2 N
"""

import bz2
import csv
import sys

sys.path.insert(0, ".")
from src.bulk import PostgresCSV, open_text  # noqa: E402


def main(src: str, dest: str, n: int) -> None:
    lines: list[str] = []
    with open_text(src) as fh:
        # Physical lines, so a record's raw text is preserved exactly.
        for line in fh:
            lines.append(line)
            if len(lines) > 200_000:
                break
            if line.startswith('"') and len(lines) % 50 == 0 or len(lines) < 400:
                reader = csv.reader(iter(lines), dialect=PostgresCSV)
                # One extra record beyond what we keep, so the kept ones are complete.
                if sum(1 for _ in reader) >= n + 2:
                    break
    # Trim to the exact physical lines of header + n records.
    reader = csv.reader(iter(lines), dialect=PostgresCSV)
    for _ in range(n + 1):
        next(reader)
    raw = "".join(lines[: reader.line_num])
    with bz2.open(dest, "wt", encoding="utf-8", newline="") as out:
        out.write(raw)
    print(f"Wrote {n} records ({len(raw)} chars) to {dest}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]))
