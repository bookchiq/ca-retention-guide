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
- SOS ballot re-check (2026-10-17, against the SOS judicial candidates PDF): all 64 names, courts, districts, and divisions match SPEC §4, including presiding titles. `data/justices.csv` uses the SOS spellings; court-roster forms (e.g., "Stephen" Goorvitch, "Rodríguez", "Bermúdez", John Shepard Wiley Jr.) are kept in `notes` and `data/aliases.csv`. The ballot lists Lisa Rodriguez as "San Diego County Superior Court Judge", Frederick S. Chung as "Superior Court Judge", and David B. Sapp with no title.

## 2026-10-17: Limited appellate record

SPEC §4's list of short-tenure justices was incomplete. Applying the 12-month rule to sourced start dates flags 15 justices as `limited_record`: Rodriguez, Macaulay, Damrell, Sapp, Chung, and C. F. Adams (named in the spec), plus Bermudez, Servino, Goorvitch, Daum, Guerra, Sandhu, Lee, Scherb, and Harrell. Sapp, Chung, and Rodriguez take their seats only on 2027-01-04 if retained. Open question for the owner: Amy K. Guerra served pro tem at the Fifth District (Oct 2025–Jan 2026) before her 2026-05-22 confirmation; the data currently counts only the confirmed service.

Source conflicts resolved in favor of the official release date (noted per row): Chou (bio July 2023; release 2023-06-23), Boulware Eurie (bio Aug 4, 2022; release Aug 3, 2022), Simons (bio 2000; roster 2001).

## 2026-10-17: Data loaded; window decision pending (R6)

Loaded 43,674 opinions (2026-09-30 bulk snapshot plus 267 Court of Appeal opinions filed 2026-10-01 onward via the API; no new Supreme Court opinions in that gap). Full parse: 42,811 ok (98.0%), 423 unresolved, 285 without a signature, 1,883 superseded duplicates linked. 4th District: 99.3% ok.

Coverage (`data/validation/coverage.md`): 2021–2025 Court of Appeal years are complete (6,300–7,100 a year). **2020 is thin: 3,810 opinions, of which only 2,750 unpublished, against about 6,000 unpublished in later years.** Projected Tier 1 reading pool: 555 4th District opinions with a search-and-seizure anchor since 2020, 314 since 2023. Owner decision pending: keep 2020 onward (default) or cut to 2023 onward.

## 2026-10-17: Review queue rules (U9)

- L4 candidates include every queue-matching opinion with a dissent where the justice **wrote or joined** the majority. SPEC §8.3 says "joined"; the author is part of the majority too, and without this an unpublished pure affirmance a justice wrote over a colleague's dissent would reach no listing rule.
- Excluded records are promoted to the public `data/case_notes.jsonl` with their exclusion reason, so readers can audit which queued cases were not listed and why.
- "not_reached" is an *outcome* (SPEC §8.5), never an exclusion reason: a case nobody has read stays undecided and keeps its justice-topic at "Not yet reviewed".

## Changelog
