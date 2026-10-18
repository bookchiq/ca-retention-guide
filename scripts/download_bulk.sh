#!/usr/bin/env bash
# Download CourtListener's quarterly bulk snapshot into data/raw/bulk/.
# Resumable: rerunning continues partial files and skips complete ones.
# Usage: scripts/download_bulk.sh [snapshot-date]   (default 2026-09-30)
set -euo pipefail

main() {
	local snapshot="${1:-2026-09-30}"
	local base="https://com-courtlistener-storage.s3.us-west-2.amazonaws.com/bulk-data"
	local repo_root
	repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
	local dest="${repo_root}/data/raw/bulk"
	mkdir -p "${dest}"

	# Smallest first so the schema and courts are available immediately.
	local name
	for name in "schema-${snapshot}.sql" "courts-${snapshot}.csv.bz2" \
		"opinion-clusters-${snapshot}.csv.bz2" "dockets-${snapshot}.csv.bz2" \
		"opinions-${snapshot}.csv.bz2"; do
		fetch_one "${base}/${name}" "${dest}/${name}"
	done
	echo "All bulk files present in ${dest}"
}

fetch_one() {
	local url="$1"
	local out="$2"
	local expected
	expected="$(curl -fsSI "${url}" | awk 'tolower($1)=="content-length:" {gsub("\r",""); print $2}')"
	if [[ -f "${out}" ]] && [[ "$(stat -f%z "${out}")" == "${expected}" ]]; then
		echo "Complete: $(basename "${out}") (${expected} bytes)"
		return 0
	fi
	echo "Downloading $(basename "${out}") (${expected} bytes)"
	local attempt
	for attempt in 1 2 3 4 5 6 7 8 9 10; do
		if curl -fsSL --retry 5 --retry-delay 10 -C - -o "${out}" "${url}"; then
			break
		fi
		echo "Attempt ${attempt} failed; retrying in 30s" >&2
		sleep 30
	done
	local actual
	actual="$(stat -f%z "${out}")"
	if [[ "${actual}" != "${expected}" ]]; then
		echo "Size mismatch for ${out}: got ${actual}, expected ${expected}" >&2
		return 1
	fi
	echo "Done: $(basename "${out}")"
}

main "$@"
