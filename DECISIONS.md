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

## 2026-10-18: Validation round 1 and keyword change

**Parsing.** First 200-opinion sample, labeled by two sessions that saw only opinion text: the 4th District scored 100% on author, panel, and separate opinions; most other disagreements were name-comparison artifacts (fixed in scoring) plus three Supreme Court and one 1st District parser gaps (fixed). Because those fixes were made after seeing the sample, a **non-overlapping holdout** of 200 was drawn and labeled independently: author 100%, separate opinions 99.5%, panel **96.0%** (192/200; threshold 97%) — **gate not passed**. The seven real misses (lone assignment-star lines, blank-line signatures, a qualified "I concur" joiner, a "Justices" typo, a publication order read before the opinion, a parenthesized given name) were fixed test-first; a third fresh sample decides the gate. The two scored samples are not reused for the gate.

**Keyword change: `search_seizure` tag rule.** The anchor-or-3-broad rule measured **28% precision** (14 of 50 tagged opinions address a search or seizure claim; independent labels, KTD9 definition) with no misses among 60 untagged criminal opinions. Most false positives mention "search warrant" once in the facts. New rule for this topic only: at least 2 distinct anchor terms **and** at least 4 occurrences of core terms (Fourth Amendment, motion to suppress, section 1538.5, suppression). It tags 598 opinions instead of 2,305. The reading queue keeps the loose match (any anchor or broad term), so the stricter rule never shrinks what readers see. The rule was fit on that sample, so it is being re-validated on fresh samples: 50 newly tagged (precision) and 50 the old rule tagged but the new rule drops (recall loss).

## 2026-10-18: Parsing gate decided; review rule clarification

**Parsing gate (third independent sample, 200 opinions never used for a fix):** author 100%, panel 99.5%, separate opinions 100%. Pooled gate and all six Court of Appeal districts pass, including the 4th District. The Supreme Court stratum failed on one panel error (an assigned Court of Appeal justice printed "Fujisaki *"); fixed, and re-checked on a fresh Supreme Court-only sample of 40 opinions (none previously sampled): 0 errors on author, panel, and separate opinions. **The parsing gate (R9) passes for every district and the Supreme Court.**

**Reading rule clarification.** Two readers decided *People v. Brown* (S271877) differently: whether a ruling on continuing a suppression hearing puts the search issue "at issue." Ruled: yes. A ruling on how a suppression motion is litigated (timeliness, continuance, whether a hearing is required) rules on the claim the way a forfeiture ruling does. A case in several justices' queues must get the same at-issue call for each. New exclusion reason `no_rule_applies`: the issue is at issue but the justice's role meets no listing rule (for example, joined a dissent another justice wrote).

**Data quality.** CourtListener records 9940655 and 9940656 have swapped case names ("In re H.D." and "Bonds v. Superior Court"); both are excluded (no search or seizure claim decided). Guide pages drop CourtListener's " CA4/1" suffix on unpublished case names and the "M" marking a modified opinion's docket; the stored records keep both. CourtListener record 4531440 is filed under "Torres" but its text is *People v. Flores* (S116307). It was excluded (no search or seizure claim), so no listing is affected.

## 2026-10-18: Tier 1 review complete for the San Diego set

All 13 queued San Diego-ballot justices were read, verified by a separate session, and second-checked on a random 15% per justice (minimum 1), listed and excluded. Every sampled record passed, so none went back to verification. 27 cases appear in more than one justice's queue, and each got the same at-issue call for every justice. All 24 listed records match their opinion captions (docket and party name).

**Reading rule clarification.** Readers and checkers treated bail and pretrial-detention rulings (*In re Humphrey*) and "probable cause" to hold a defendant to answer (Pen. Code § 995) as outside the search-and-seizure topic. The review guide now says so explicitly. No record changed.

## 2026-10-18: Owner decisions

**Spot check passed.** The owner read 10 randomly drawn listed summaries against their opinions (seed 1027) and found them accurate. A few were judged accurate but missing some context; the owner accepted that for Phase 1. This clears the promoted records in `data/case_notes.jsonl` for publication.

**Data window.** Keep 2020-01-01 onward. 2020 is thinner than later years (see `data/validation/coverage.md`); the methodology page's coverage section now says so.

## 2026-10-17: Review queue rules (U9)

- L4 candidates include every queue-matching opinion with a dissent where the justice **wrote or joined** the majority. SPEC §8.3 says "joined"; the author is part of the majority too, and without this an unpublished pure affirmance a justice wrote over a colleague's dissent would reach no listing rule.
- Excluded records are promoted to the public `data/case_notes.jsonl` with their exclusion reason, so readers can audit which queued cases were not listed and why.
- "not_reached" is an *outcome* (SPEC §8.5), never an exclusion reason: a case nobody has read stays undecided and keeps its justice-topic at "Not yet reviewed".

## Changelog
