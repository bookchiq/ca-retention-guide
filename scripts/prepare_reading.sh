#!/usr/bin/env bash
# Scaffold draft records and export opinion texts for the given justices.
# Usage: scripts/prepare_reading.sh SLUG [SLUG ...]
set -euo pipefail

main() {
	local slug
	for slug in "$@"; do
		uv run python -m src.review new --justice "${slug}"
	done
	uv run python scripts/export_reading.py "$@"
}

main "$@"
