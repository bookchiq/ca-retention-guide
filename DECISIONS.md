# Decisions log

Every change to rules, scope, keywords, or method, with date and reason (SPEC.md preamble). Newest entries at the bottom of each section.

## 2026-10-17: Project bootstrap

**Repo.** The project root is this folder (`judges/`), not a nested `retention-guide/`. The repo is public from the first commit at `github.com/bookchiq/ca-retention-guide`, so every push is publication. Owner decisions, 2026-10-17.

**Licenses.** MIT for code; CC BY 4.0 for the guide's prose and data exports (see `LICENSE`, `LICENSE-CONTENT`). Owner decision, 2026-10-17.

**Plan.** Phase 1 implementation plan: `docs/plans/2026-10-17-2059-feat-ca-retention-guide-phase1-plan.md`.

### Spec deviations

| Spec section | Spec says | Project does | Reason |
|---|---|---|---|
| §5.1 | API at about 1 request/second; overnight bulk run | CourtListener quarterly bulk snapshot (2026-09-30) as primary source; API only for the 2026-10-01-onward gap, samples, and checks | Since 2026-05-07, free authenticated accounts are limited to 5 requests/min, 50/hour, 125/day (https://wiki.free.law/c/courtlistener/help/api/rest/v4/overview, checked 2026-10-17). 40,000 opinions at ~20 per page would take ~16 days. |
| §6.2 | `retention-guide/` root; `case_notes.jsonl` tracked including drafts | `judges/` root; drafts live in gitignored `data/drafts/`; tracked `data/case_notes.jsonl` holds promoted (verified and second-checked) records only | Owner decisions: folder choice and public repo from day one |
| §6.2 | `.gitignore` lists `.env`, `data/raw/`, `data/*.sqlite` | Also `data/drafts/`, `data/review/` | Public repo: no unverified content may be committed |
| §7.1 | Single `appellate_start_date`, district, division | Adds `data/service_periods.csv` and `data/other_justices.csv` | Elevations, transfers, and non-ballot panel members |
| §7.3.8 | 200-opinion sample, overall thresholds | Same pooled gate, plus 4th District (≥60) and Supreme Court (≥30) strata gated on their own | Detect a parser failure concentrated in the San Diego courts |
| §8.5 | Case record schema | Adds `listing_decision`, `exclusion_reason`, `second_check` | Recorded exclusions; per-record second check |
| §9.1 step 4 | Random 15% overall | 15% per justice (min 1), listed and excluded records | A small justice could otherwise get no sample |
| §13 | "Every link resolves" | Cluster existence proven by bulk data, plus a browser spot check of the owner's sample | Anonymous scraping returns 202; authenticated checks would spend the daily API budget |

### First-session checks (SPEC §17)

- `COURTLISTENER_TOKEN`: not yet set at bootstrap; owner is adding it to `.env`.
- Supreme Court court ID: `cal` confirmed via `GET /api/rest/v4/courts/cal/` (2026-10-17).
- Anonymous access to opinions/clusters/dockets returns 401 (API v4.3+); token required.
- Bulk snapshot 2026-09-30 sizes (S3 listing, 2026-10-17): opinions 55,252,643,429 B; dockets 5,144,011,100 B; opinion-clusters 2,467,613,433 B.
- SOS ballot re-check: pending (U2).

## Changelog
