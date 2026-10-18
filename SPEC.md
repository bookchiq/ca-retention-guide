# Spec: California Appellate Justice Retention Guide (Nov 3, 2026)

Build a nonpartisan, source-linked dataset and voter guide describing the records of the California Supreme Court and Court of Appeal justices on the November 3, 2026 retention ballot. Phase 1 covers every ballot justice with automated metrics and gives the 17 justices on San Diego County ballots full, hand-verified case summaries. Phase 2 extends the verified case summaries statewide.

This file is the single source of truth for the project. When the code and this spec disagree, fix one of them and log the decision in `DECISIONS.md`.

**Claude Code: start with section 17 (First session checklist) after reading the whole spec.**

> **Amended 2026-10-17.** Several sections below are superseded by the "Spec deviations" table in `DECISIONS.md`: opinion acquisition (§5.1, now bulk-data first because of new API limits), repo layout and the drafts/promotion split (§6.2), service history (§7.1), the validation sample (§7.3.8), the case record schema (§8.5), second-check sampling (§9.1), and link checking (§13). Where they disagree, `DECISIONS.md` wins.

---

## 1. Purpose and audience

California voters cast yes/no retention votes on appellate justices with almost no information. The audience is any California voter, regardless of politics. The guide must be useful to a voter who wants judges who protect individual rights from government overreach, and equally useful to a voter who wants judges who defer to law enforcement. It does this by describing what each justice did, with links, rather than grading them.

## 2. Ground rules (non-negotiable)

1. **Describe, don't grade.** No scores, rankings, letter grades, or recommendations. No labels such as "pro-police," "soft on crime," "activist," or "liberal/conservative." Report counts and cases; let readers apply their own values.
2. **Every claim links to a source.** Each case summary links to the opinion. Each background fact links to an official bio, press release, or record.
3. **Mechanical selection, not cherry-picking.** Which cases get listed is decided by fixed rules (section 8.3), applied identically to every justice. If a rule would list a case that cuts against an apparent pattern, it gets listed.
4. **Accuracy over coverage.** A wrong summary attached to a real judge's name is the worst possible failure. Anything not verified does not ship. It is fine for a justice's page to say "not yet reviewed."
5. **Show base rates.** Most criminal appeals are affirmed. Any rate shown for a justice must be shown next to the comparable rate for their district/division so readers aren't misled by raw numbers.
6. **Say what the data can't show.** Each justice page and the methodology page carry the limitations in section 11.
7. **No contact with judges, courts, or campaigns.** This is a records project. Justices are barred by judicial ethics rules from campaigning or commenting.
8. **Disclose AI assistance.** The methodology page states that the data was collected and first-pass analyzed with AI tools, and that every listed case summary was verified against the opinion text.

## 3. Scope and phases

### Phase 1 (target: published by Tuesday, October 27, 2026)

- **All 64 ballot justices (statewide):** background facts and automated metrics (section 8.1 and 8.2), plus topic counts for every topic in section 7.
- **The 17 justices on San Diego County ballots** (2 Supreme Court + 15 Fourth District): hand-verified case lists and summaries (section 8.3) for **Tier 1** topics. Do **Tier 2** too if time allows before the cutoff.
- Freeze rule: on the morning of Oct 27, ship whatever is verified. Unfinished justices or topics are marked "not yet reviewed," never estimated.

### Phase 2 (after Phase 1 ships; may run past the election)

- Extend verified case summaries (Tier 1 and Tier 2) to all 64 ballot justices.
- Add Tier 3 topics.
- Optional: API-assisted first-pass classification (section 9.2) with verification sampling, plus Supreme Court review/reversal tracking (section 8.4).

### Time window

Default: each justice's appellate opinions from **January 1, 2020** (or their appellate start date, if later) through the run date. This is configurable in `config.yaml`. If download throughput is a problem, shrink to 2023 onward and document it. Record the exact window on every page.

## 4. The ballot

Source: California Secretary of State, *General Election, November 3, 2026, List of Judicial Candidates with Headings and Ballot Questions* (Aug 24, 2026): https://elections.cdn.sos.ca.gov/statewide-elections/2026-general/judicial.pdf

Court of Appeal justices appear on the ballot for their **whole district** (all divisions), not just their division. Copy names exactly as the SOS lists them. Before relying on this table, Claude Code must re-check it against the SOS PDF.

`SD` = appears on San Diego County ballots (Phase 1 hand-verified set).

### Supreme Court (all counties)

| Name | Notes |
|---|---|
| Joshua Groban | SD. Appointed by Gov. Brown; joined the court January 2019; retained in 2022 for the rest of an unexpired term. |
| Kelli M. Evans | SD. Appointed by Gov. Newsom in 2022; joined the court in 2023. First retention vote. |

### First District (Alameda, Contra Costa, Del Norte, Humboldt, Lake, Marin, Mendocino, Napa, San Francisco, San Mateo, Solano, Sonoma)

| Division | Name |
|---|---|
| One | Monique Langhorne Wilson |
| One | Charles A. Smiley |
| One | Kathleen M. Banke |
| Two (Presiding) | Therese M. Stewart |
| Two | Tara M. Desautels |
| Three | Ioana Petrou |
| Three | Victor A. Rodriguez |
| Four (Presiding) | Tracie L. Brown |
| Five | Danny Y. Chou |
| Five | Mark Simons |
| Five | Gordon Burns |

### Second District (Los Angeles, San Luis Obispo, Santa Barbara, Ventura)

| Division | Name |
|---|---|
| One | Michelle C. Kim |
| One | Gregory J. Weingart |
| Two | Anne Richardson |
| Two | Steve Goorvitch |
| Three (Presiding) | Rashida A. Adams |
| Three | Mark Hanasono |
| Four (Presiding) | Helen Zukin |
| Four | Nicholas Daum |
| Four | Audra M. Mori |
| Four | Armen Tamzarian |
| Five (Presiding) | Brian M. Hoffstadt |
| Six (Presiding) | Tari L. Cody |
| Six | Kenneth R. Yegan |
| Seven (Presiding) | Gonzalo C. Martinez |
| Seven | Natalie Stone |
| Eight | John Wiley |
| Eight | Matthew A. Scherb |
| Eight | Victor G. Viramontes |

### Third District (Sacramento and 22 other counties)

| Division | Name |
|---|---|
| (Administrative Presiding) | Laurie Earl |
| — | Lauri Damrell |
| — | David B. Sapp |
| — | Stacy Boulware Eurie |
| — | Jonathan Renner |
| — | Aimee A. Feinberg |
| — | Shama Mesiwala |

### Fourth District (Imperial, Inyo, Orange, Riverside, San Bernardino, San Diego): all SD

| Division | Name |
|---|---|
| One (San Diego) | Julia C. Kelety |
| One | Jose S. Castillo |
| One | Truc T. Do |
| One | William S. Dato |
| One | Eran M. Bermudez |
| One | Lisa Rodriguez |
| One | David M. Rubin |
| Two (Riverside) | Corey G. Lee |
| Two | Michael J. Raphael |
| Three (Santa Ana) (Presiding) | Joanne Motoike |
| Three | Thomas A. Delaney |
| Three | Nathan R. Scott |
| Three | Deborah C. Servino |
| Three | Martha K. Gooding |
| Three | Juliet O. Macaulay |

### Fifth District (Fresno and 8 other counties)

Arlan L. Harrell · Thomas DeSantos · Sonny S. Sandhu · Mark W. Snauffer · Amy K. Guerra · Kathleen A. Meehan

### Sixth District (Monterey, San Benito, Santa Clara, Santa Cruz)

Charles E. Wilson II · Frederick S. Chung · Charles F. Adams · Allison Marston Danner · Daniel H. Bromberg

**Totals:** 2 Supreme Court + 62 Court of Appeal = 64 justices. San Diego set: 2 + 15 = 17.

### Justices likely to have little or no appellate record

Verify each from official bios. Pages for these justices should say plainly that their appellate record is too short to assess, and give background facts only. Do not substitute trial-court records, which are mostly unpublished and not comparable.

- **Lisa Rodriguez** (4th/1): San Diego Superior Court judge; nominated Aug 7, 2026; confirmed Aug 20, 2026.
- **Juliet O. Macaulay** (4th/3): nominated Aug 7, 2026; confirmed Aug 20, 2026.
- **Charles F. Adams** (6th): sworn in Aug 6, 2026.
- **Frederick S. Chung** (6th): Superior Court judge; nominated Aug 7, 2026.
- **David B. Sapp** (3rd): nominated Aug 7, 2026 (listed on the ballot without a judicial title).
- **Lauri Damrell** (3rd): nominated Aug 7, 2026 (listed as Associate Justice; confirm start date).
- **Rashida A. Adams** (2nd/3): on the Court of Appeal since 2023; nominated as Presiding Justice. She **does** have a record; just use the correct start date.

Rule: flag anyone with less than 12 months of appellate service as "limited appellate record."

---

## 5. Data sources

### 5.1 Opinions: CourtListener (Free Law Project)

API base: `https://www.courtlistener.com/api/rest/v4/`

What was verified on Oct 17, 2026 (re-verify before building):

| Check | Result |
|---|---|
| Search endpoint `search/?type=o&court=calctapp` | Works **without** a token. |
| Court ID for the Court of Appeal | `calctapp` works. Supreme Court is believed to be `cal`; verify. |
| Unpublished opinions present? | **Yes.** Since 2025-01-01: 1,291 published, 11,205 unpublished. Use `stat_Published=on&stat_Unpublished=on` to get both. |
| "Fourth Amendment" hits since 2025-01-01 | 175 total (27 published, 148 unpublished). |
| `judge` / `panel_names` fields for `calctapp` | **Empty** on every sample. Author and panel must be parsed from the opinion text. |
| Opinion type on samples | `combined-opinion` (majority and separate opinions in one text blob). |
| `opinions/{id}/` (full text) | **401 without a token.** Needs a free CourtListener account. |
| `download_url` (old courts.ca.gov PDF links) | 404 on the sample tested. Don't rely on them. |
| Anonymous HTML page scrape | Returned 202 with empty body. Don't scrape; use the API. |

**Auth:** read the token from the environment variable `COURTLISTENER_TOKEN`; send as `Authorization: Token <token>`. Never print, log, write to disk, or commit the token. Add `.env` to `.gitignore`.

**Rate limits:** check CourtListener's current documented limits before the bulk run. Design for about 1 request/second with exponential backoff on 429/5xx (use `tenacity`). Set a descriptive `User-Agent` with a contact email from config.

**Efficiency:** prefer list endpoints with filters (for example, opinions filtered by court and date filed) that return text in bulk over one call per opinion. Confirm filter field names against the API docs. Cache every response in SQLite so reruns are free and resumable. If the API proves too slow, CourtListener's bulk data exports are the fallback; investigate size first.

**Volume estimate:** about 7,000 Court of Appeal opinions per year statewide. Because almost every three-justice panel includes at least one ballot justice, the 2020–present window means downloading essentially all Court of Appeal opinions in that period (about 40,000). Budget for an overnight run.

### 5.2 Background facts

| Field | Source |
|---|---|
| Court, district, division, title | SOS ballot list (above); appellate court justice bio pages: https://appellate.courts.ca.gov/district-courts/ (each district has a Justices page) |
| Appointment date, appointing governor, prior career | Official bio; Governor's appointment press release (gov.ca.gov) |
| Prior retention results | SOS Statements of Vote for prior general elections |
| Public discipline | Commission on Judicial Performance public decisions: https://cjp.ca.gov/ (search each name; record "none found" with the search date if none) |
| Statements of Economic Interests (Form 700) | Phase 2, optional. Locate the correct custodian first; do not guess. |

### 5.3 Supreme Court: dissents from denial of review

These dissents are not in the opinion text; they appear in court minutes and docket entries. For Phase 1, cite existing compilations rather than re-deriving them: David S. Ettinger's *At the Lectern* blog (Horvitz & Levy, https://www.horvitzlevy.com/) publishes term-by-term counts. Example reported figure (2024–25 term): Evans 63 dissents from denial of review, all in criminal cases; Groban 22, 10 in criminal cases. Quote the figures with attribution and a link; do not restate them as our own measurement.

---

## 6. Technical setup

### 6.1 Stack

- Python 3.11+
- `requests`, `tenacity`, `pyyaml`, `pandas`, `rapidfuzz` (name matching), `jinja2` (page rendering)
- SQLite for storage (`data/cases.sqlite`)
- Outputs in Markdown (the owner prefers Markdown)

### 6.2 Repo layout

```
retention-guide/
  SPEC.md                 # this file
  DECISIONS.md            # log of any change to rules, scope, or keywords, with date and reason
  config.yaml             # window, rate limits, user agent, phase flags, file paths
  .env.example            # COURTLISTENER_TOKEN= (and optional ANTHROPIC_API_KEY= for Phase 2)
  .gitignore              # .env, data/raw/, data/*.sqlite
  data/
    justices.csv          # hand-built and verified (section 7.1 schema)
    aliases.csv           # signature variants per justice
    keywords.yaml         # topic keyword sets (section 7)
    raw/                  # cached API responses (never published)
    cases.sqlite          # opinions, panels, tags, classifications
    case_notes.jsonl      # verified case records (section 8.3)
    validation/           # hand-labeled samples and accuracy reports
  src/
    fetch.py              # download and cache
    parse.py              # header, publication status, author, panel, separate opinions
    tag.py                # topic tagging
    metrics.py            # per-justice and baseline metrics
    review.py             # helpers for the reading/verification queue
    render.py             # build the guide pages
  guide/                  # generated, publishable output
    index.md
    methodology.md
    justices/<slug>.md
```

### 6.3 Commands (target)

```
python -m src.fetch --court calctapp --since 2020-01-01
python -m src.fetch --court cal --since 2019-01-01
python -m src.parse
python -m src.tag
python -m src.metrics
python -m src.review queue --set sd17 --tier 1      # lists cases needing a human/agent read
python -m src.render
```

All steps must be idempotent and resumable.

---

## 7. Data model, parsing, and topics

### 7.1 `justices.csv`

`slug, full_name_ballot, court (supreme|appeal), district (1-6|null), division (One..Eight|null), title, sd_ballot (bool), appellate_start_date, appointing_governor, prior_career (semicolon list from the categories below), prior_retention (year:pct_yes;...), cjp_public_discipline (none_found|text), cjp_search_date, limited_record (bool), bio_url, appointment_release_url, notes`

**Prior career categories** (neutral; multiple allowed): `prosecutor`, `public_defender`, `private_criminal_defense`, `civil_plaintiff`, `civil_defense`, `government_counsel`, `appellate_court_staff`, `trial_judge`, `academia`, `policy_or_political_staff`, `other`. The Utah warrant study (Harvard Law Review 2025, "Unwarranted Warrants?") found that judges' professional backgrounds correlated with how they reviewed warrants, so this field matters. Record years in each role where the bio gives them.

### 7.2 Opinions table (`opinions`)

`cl_opinion_id, cl_cluster_id, case_name, docket_number, court, district, division, date_filed, published (bool), disposition_text, author_slug|null, author_raw, per_curiam (bool), panel_slugs (json), panel_raw (json), assigned_judges_raw (json), has_dissent, has_concurrence, separate_opinions (json: [{type, author_slug, author_raw}]), topics (json), text_hash, source_url`

### 7.3 Parsing rules

Build these from real samples and measure. Don't trust any pattern below until validated.

1. **District and division:**
   - First from the docket number prefix: `A` = 1st, `B` = 2nd, `C` = 3rd, `D` = 4th/Div. One, `E` = 4th/Div. Two, `G` = 4th/Div. Three, `F` = 5th, `H` = 6th.
   - For the 1st and 2nd Districts, take the division from the caption header (for example, "SECOND APPELLATE DISTRICT DIVISION EIGHT").
   - Cross-check the prefix against the header; log disagreements.
2. **Publication status:** "CERTIFIED FOR PUBLICATION" / "CERTIFIED FOR PARTIAL PUBLICATION" vs. "NOT TO BE PUBLISHED IN THE OFFICIAL REPORTS". Cross-check with CourtListener `status`.
3. **Court of Appeal author:** typically a signature line at the end of the majority opinion, like `DATO, J.`, `HUFFMAN, Acting P. J.`, or `McCONNELL, P. J.`, followed by `WE CONCUR:` / `We concur:` and the other panel members.
   - Some opinions place the author elsewhere. "THE COURT" means per curiam.
   - Handle mixed case (`McCONNELL`), apostrophes (`O'ROURKE`), and compound surnames (`BOULWARE EURIE`, `LANGHORNE WILSON`).
4. **Supreme Court author:** current format is typically "Justice X authored the opinion of the Court, in which ... concurred," plus "Justice Y filed a dissenting/concurring opinion." Verify on samples.
5. **Separate opinions:** detect headings and phrases such as "DISSENTING OPINION," "Dissenting Opinion of," "CONCURRING OPINION," "Concurring and Dissenting," and "I respectfully dissent." Attribute each to its signature. A partial dissent counts as a dissent and also gets flagged `partial`.
6. **Assigned judges:** text like "Judge of the ___ Superior Court, assigned by the Chief Justice pursuant to article VI, section 6" marks a trial judge sitting by assignment. Record them in the panel; never match them to a ballot justice.
7. **Name resolution:** match on (surname alias, district, division, date within service window) using `aliases.csv`, never surname alone.
   - Known collisions: Rodriguez (Victor A., 1st/3; Lisa, 4th/1), Adams (Rashida A., 2nd/3; Charles F., 6th), Wilson (Monique Langhorne Wilson, 1st/1; Charles E. Wilson II, 6th).
   - Former justices with the same surnames may exist in the same district; the date window must handle them.
   - Any unresolved match goes to a review queue, not a guess.
8. **Validation gate (must pass before computing metrics):**
   - Hand-label a stratified sample of 200 opinions: every district, both publication statuses, and at least 20 with separate opinions.
   - Required accuracy: author ≥ 98%, panel membership ≥ 97%, separate-opinion detection ≥ 95%.
   - Save the sample and report under `data/validation/`. Iterate until passing.

### 7.4 Topics (`keywords.yaml`)

Tagging is a first-pass filter, not a classification. An opinion gets a topic if it contains an **anchor term** for that topic, or at least 3 hits from that topic's broader term list. Store hit counts.

Validate precision on a hand-checked sample of 50 per Tier 1–2 topic; target ≥ 85%. Tune and log changes in `DECISIONS.md`.

**Tier 1 (Phase 1 verified summaries for the SD 17)**

- `search_seizure`
  - Anchors: "Fourth Amendment"; "motion to suppress"; "section 1538.5" / "§ 1538.5"; "search warrant"; "warrantless"; "exclusionary rule"; "CalECPA" / "Electronic Communications Privacy Act" / "section 1546".
  - Broader terms: "probable cause"; "reasonable suspicion"; "detention"; "consent to search"; "good faith exception" / "Leon"; "inevitable discovery"; "Terry stop" / "pat-down"; "probation search" / "parole search" / "Fourth waiver"; "knock-notice"; "Franks hearing"; "geofence"; "cell site"; "automobile exception"; "search incident to arrest".

**Tier 2 (Phase 1 if time allows; otherwise Phase 2)**

- `interrogation`: "Miranda"; "custodial interrogation"; "voluntariness"; "involuntary confession".
- `counsel_fair_trial`: "ineffective assistance"; "Strickland"; "Marsden"; "Faretta"; "Sixth Amendment".
- `jury_selection`: "Batson"; "Wheeler"; "section 231.7".
- `racial_justice_act`: "Racial Justice Act"; "section 745".
- `police_records`: "Pitchess"; "Evidence Code section 1043"; "section 832.7"; "Senate Bill 1421".
- `immigration_pleas`: "section 1473.7"; "immigration consequences"; "Padilla v. Kentucky".
- `resentencing`: "section 1172.6"; "section 1170.95"; "Senate Bill 1437"; "Senate Bill 775"; "section 3051"; "youth offender parole"; "Franklin"; "section 1172.1"; "section 1172.75".

**Tier 3 (Phase 2)**

- `arbitration`: "motion to compel arbitration"; "arbitration agreement"; "unconscionab"; "Armendariz".
- `employment`: "Private Attorneys General Act" / "PAGA"; "Labor Code section 2698"; "FEHA"; "wage and hour"; "wrongful termination".
- `consumer`: "Song-Beverly"; "lemon law"; "Consumers Legal Remedies Act"; "Business and Professions Code section 17200" / "Unfair Competition Law".
- `landlord_tenant`: "unlawful detainer"; "Tenant Protection Act"; "Civil Code section 1946.2"; "rent control".
- `transparency`: "California Public Records Act"; "Government Code section 7920"; "section 6250"; "Brown Act"; "Government Code section 54950".
- `anti_slapp`: "anti-SLAPP"; "section 425.16".
- `taxpayer`: "Proposition 218"; "Proposition 13"; "Proposition 26"; "special tax"; "Howard Jarvis".
- `land_use_housing`: "CEQA"; "California Environmental Quality Act"; "Housing Accountability Act"; "builder's remedy"; "density bonus".

---

## 8. Metrics, case selection, and verification

### 8.1 Background (all 64 justices, Phase 1)

Fill `justices.csv` per section 7.1. Every field has a source URL or is left blank. Do the SD 17 first.

### 8.2 Automated metrics (all 64 justices, Phase 1)

Computed per justice over their window. Show each with the same metric for their district/division ("baseline") alongside.

- **Volume:** majority opinions authored (published / unpublished), and panels sat on.
- **Publication rate** of authored opinions.
- **Separate opinions:** dissents authored and concurrences authored, each as a count and per 100 panels.
- **Topic counts:** for each topic, opinions authored and panels sat on.
- **Contested votes:** cases in a topic where the panel split, and which side the justice was on.

No automated "direction" metrics (pro-individual vs. pro-government) in Phase 1. Direction comes only from verified reading (8.3) or, in Phase 2, from audited API classification (9.2).

### 8.3 Which cases get listed (fixed rules, applied to every justice)

For each justice and each topic being reviewed, list:

- **L1.** Every separate opinion (dissent, concurrence, concurrence-and-dissent) the justice wrote.
- **L2.** Every published majority opinion the justice wrote.
- **L3.** Every majority opinion the justice wrote (published or not) where the court reversed, vacated, modified, or granted writ relief on the topic issue, **in either direction.** This includes the People's appeals that reverse a suppression order.
- **L4.** Every case where the justice joined the majority over another justice's dissent on the topic issue.

Everything else in the topic is counted (8.2), not listed. Routine affirmances are numerous and look alike; reversals and split votes are where justices differ, and including reversals in both directions keeps the selection symmetric.

If a justice has more than 25 listed cases in one topic, show the 25 most recent on the page and link to the full CSV.

### 8.4 Supreme Court specifics

- **Opinions:** apply L1–L4 to Groban's and Evans's opinions. For the Supreme Court, also list every majority opinion they authored in Tier 1 topics, since every Supreme Court opinion is precedential.
- **Dissents from denial of review:** cite the *At the Lectern* compilations (5.3).
- **Phase 2:** track how often each Court of Appeal justice's authored opinions were granted review, depublished, or reversed by the Supreme Court. Find a reliable source first; do not infer from citations.

### 8.5 Case record schema (`case_notes.jsonl`)

```json
{
  "cl_opinion_id": 0,
  "case_name": "",
  "citation_or_docket": "",
  "date_filed": "YYYY-MM-DD",
  "published": false,
  "justice_slug": "",
  "role": "author | dissent | concurrence | concur_dissent | joined_majority_over_dissent",
  "listing_rule": "L1 | L2 | L3 | L4 | SC",
  "topic": "search_seizure",
  "issue_type": "",
  "posture": "defendant_appeal | people_appeal | writ_by_defendant | writ_by_people | civil_appeal | other",
  "trial_court_ruling": "",
  "result_on_issue": "",
  "outcome": "",
  "vote": "3-0 | 2-1 | 7-0 | 6-1 | ...",
  "summary": "",
  "opinion_url": "",
  "verified": false,
  "verified_by": "",
  "verified_date": "",
  "verification_notes": ""
}
```

- **`issue_type` for `search_seizure`:** `warrant_sufficiency`, `warrantless_exception`, `detention_or_stop`, `consent`, `probation_parole_search`, `electronic_data`, `vehicle`, `home_entry`, `other`.
- **`outcome` vocabulary is topic-specific.** For `search_seizure`: `evidence_suppressed_or_search_held_unlawful`, `search_upheld`, `mixed`, `not_reached` (forfeited, harmless error, or decided on other grounds). For Tier 3 topics, define the outcome enum in `keywords.yaml` alongside the terms (for example, arbitration: `arbitration_compelled` / `arbitration_denied`). Never use "won/lost" or value-laden labels.

---

## 9. Reading and verification workflow

### 9.1 Phase 1: agent-read (SD 17, Tier 1)

1. `review.py queue` produces the L1–L4 list per justice. Work one justice at a time, so partial progress yields complete pages. Order:
   - Supreme Court (Groban, Evans)
   - 4th District Division One (San Diego)
   - Division Three
   - Division Two
2. For each case, read the relevant sections plus the disposition and signature blocks. Fill the record.
3. **Verify:** re-open the opinion and confirm:
   - author and panel from the signature lines
   - the disposition sentence (e.g., "The judgment is affirmed," "reversed," "writ granted")
   - that the summary matches the holding
   Set `verified: true` with date.
4. **Second check:** in a fresh session, re-verify a random 15% of records. If any record is wrong, re-verify all of that justice's records and log the error type in `DECISIONS.md`.
5. **Owner check:** the project owner reads 10 random summaries against the opinions before publication.

### 9.2 Phase 2: API-assisted classification (optional)

- Use the Claude API with `ANTHROPIC_API_KEY` from the environment. Set the model in `config.yaml`, checking current model names and pricing in Anthropic's docs; do not hardcode.
- Use structured JSON output matching 8.5 plus `evidence` (short quoted lines from the opinion supporting author, disposition, and outcome) and `confidence`.
- Send the opinion's caption, the relevant topic sections, the disposition, and the signature blocks, not necessarily the whole text.
- **Pilot first:** run on 100 already-verified Phase 1 records. Report agreement per field and actual cost before any full run.
- **Listed cases (L1–L4) are always agent-verified** regardless of the API result.
- **Counts of non-listed cases:** API output may feed outcome counts only if a random 10% audit shows ≤ 5% error on `outcome`. Otherwise, publish volume counts only. Publish the audit error rate on the methodology page.

---

## 10. Summary style guide

- At most 50 words. Past tense. Lead with the justice's role.
- State the issue, the holding, and the disposition. Include the vote if it was split.
- Neutral party terms: "the defendant," "officers," "the prosecution"/"the People," "the employer," "the tenant." Use the case name only in the citation.
- No adjectives about the justice or the outcome. No motive. No characterizations of the crime beyond what's needed to understand the issue. Don't name victims; use initials where the source does.
- If a summary can't be written neutrally in 50 words, quote the opinion's own one-sentence statement of the holding (court opinions are public domain) and cite the page.

**Acceptable examples** (illustrative, not real cases):

> Wrote the 2–1 majority holding that a warrant affidavit relying on an uncorroborated anonymous tip did not establish probable cause; reversed the denial of the suppression motion. (Unpublished.)

> Dissented from a decision upholding a vehicle search; argued that officers lacked reasonable suspicion to prolong the traffic stop.

> Wrote the opinion reversing a trial court's suppression order on the People's appeal, holding that the good-faith exception applied.

**Unacceptable:**

> Stood up for privacy rights by... / Let a dangerous suspect walk free by... / Rubber-stamped another police search...

**Automated lint:** the render step fails if any guide page contains a word on the banned list: "pro-police," "anti-police," "soft on crime," "tough on crime," "activist," "liberal," "conservative," "radical," "lenient," "rubber-stamp," "heroic," "outrageous." Extend the list as needed; log additions.

---

## 11. Limitations (publish on the methodology page and summarize on each justice page)

1. **California courts follow federal search-and-seizure rules.** Under the "Truth-in-Evidence" provision (Cal. Const., art. I, § 28(f)(2), added by Prop. 8 in 1982; *In re Lance W.* (1985) 37 Cal.3d 873), state courts may exclude evidence only where the U.S. Constitution requires it. Differences between justices therefore appear mostly in how they apply existing precedent to close facts. Statutory remedies such as CalECPA's suppression provision, and laws like the Racial Justice Act, leave more room for differences.
2. **Panels.** Three justices decide each Court of Appeal case. Outcomes reflect the panel. Authored opinions and separate opinions are the clearest individual signals.
3. **Selection effects.** Which cases are appealed, and which justice is assigned to write, are not random. Many criminal appeals raise weak claims and are affirmed; that says little about the justice.
4. **Unpublished opinions** are public but generally cannot be cited as precedent (Cal. Rules of Court, rule 8.1115). They are included because they are most of the record.
5. **Coverage and errors.** Data comes from CourtListener and is limited to the stated window. Parsing and tagging error rates measured in validation are published.
6. **Supreme Court docket.** The Supreme Court chooses its cases, so its opinion record looks different from the Court of Appeal's. Dissents from denial of review are reported from a third-party compilation.
7. **Short tenures.** Some justices have little or no appellate record. The guide says so rather than filling the gap.
8. **Not advice or endorsement.** The guide does not recommend a vote.

---

## 12. Output

### 12.1 `guide/index.md`

- Short intro (what retention votes are, what this guide does and doesn't do) and a "How to read this" note.
- One table of all 64 justices with columns:
  - Name
  - Court / District / Division
  - Appointed (year, governor)
  - Prior career
  - Authored opinions (window)
  - Separate opinions
  - Tier 1 cases listed
  - Record status: `verified` / `metrics only` / `limited appellate record`
- Order: Supreme Court, then district and division in ballot order. **Never sort or rank by any outcome measure.**

### 12.2 `guide/justices/<slug>.md`

1. Name, court, and the exact ballot question text.
2. Background: appointment, appointing governor, prior career, prior retention results, public discipline (or "none found as of DATE").
3. Record at a glance: section 8.2 metrics with district/division baselines.
4. Per topic:
   - counts table
   - listed cases (newest first) with summary, vote, published status, and link
   - or "Not yet reviewed" / "No cases in window"
5. Limitations note, data window, and last-updated date.

### 12.3 `guide/methodology.md`

Ground rules (section 2), sources, parsing and tagging approach, listing rules (8.3), verification process, validation results, limitations (section 11), AI-assistance disclosure, correction contact, and changelog.

### 12.4 Data exports

`guide/data/justices.csv`, `guide/data/metrics.csv`, `guide/data/case_notes.csv`. Never publish `data/raw/` or the SQLite file.

Publishing venue (web page, GitHub Pages, etc.) is decided by the owner after Phase 1 review.

---

## 13. Acceptance checklist (Phase 1 ship gate)

- [ ] Ballot table re-checked against the SOS PDF; names exact.
- [ ] Parsing validation gate passed (7.3.8); results in methodology.
- [ ] Tier 1 tagging precision ≥ 85% on the validation sample.
- [ ] Every listed case `verified: true`; every link resolves.
- [ ] 15% second-check done; errors logged and fixed.
- [ ] Owner spot-check of 10 summaries done.
- [ ] Every rate shown has its baseline beside it.
- [ ] Banned-word lint passes.
- [ ] Every justice page shows window, last-updated date, and limitations note.
- [ ] Limited-record justices say so plainly.
- [ ] No token, raw data, or SQLite file in `guide/` or git history.

---

## 14. Phase 1 timeline (adjust as needed; the freeze date holds)

| Date (2026) | Work |
|---|---|
| Sat Oct 17 – Sun Oct 18 | Repo setup; `justices.csv` and `aliases.csv` (SD 17 first); start the bulk fetch. |
| Mon Oct 19 – Tue Oct 20 | Parser and validation gate; topic tagging and precision check; metrics for all 64. |
| Wed Oct 21 – Sat Oct 24 | Tier 1 reading and verification for the SD 17 (order in 9.1). |
| Sun Oct 25 | Render; 15% second-check; Tier 2 for the SD 17 if ahead of schedule. |
| Mon Oct 26 | Acceptance checklist; owner spot-check. |
| **Tue Oct 27** | **Freeze and publish.** Unfinished items are marked "not yet reviewed." |

## 15. Phase 2 backlog

1. Tier 1 and Tier 2 verified summaries for the remaining 47 justices.
2. Tier 3 topics.
3. API-assisted classification pilot, audit, and full run (9.2).
4. Supreme Court review, depublication, and reversal tracking (8.4).
5. Form 700 economic-interest data (5.2).
6. Make the pipeline reusable for the 2028 retention ballot: ballot list as an input file, no hardcoded names.

## 16. Open decisions for the owner

- Publishing venue, project name, and a correction-contact email for the methodology page.
- Whether the owner is credited by name.
- Confirm the 2020-onward window (or choose a different one) once fetch throughput is known.

## 17. First Claude Code session

1. Read this spec end to end. Create `DECISIONS.md`.
2. Confirm `COURTLISTENER_TOKEN` is set, without printing it.
3. Re-run the section 5.1 checks and record results in `DECISIONS.md`. Confirm the Supreme Court court ID.
4. Re-check the ballot table (section 4) against the SOS PDF.
5. Build `justices.csv` for the SD 17 with sources.
6. Pull 30 sample opinions across districts. Draft parsing patterns, then start the bulk fetch in the background with caching and resume.
7. Report back to the owner: what's working, what's blocked, and any decision needed.
