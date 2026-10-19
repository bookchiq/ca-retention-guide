# Methodology

This is the detailed version, for readers who want to check how the guide was made. The [front page](index.md) has the short version.

An experiment by Sarah Lewis. Everything here, including the rules, the code, the validation samples, and each reviewer's notes, is public in the [GitHub repository](https://github.com/bookchiq/ca-retention-guide), so you can decide for yourself whether the method holds up.

Last updated: 2026-10-18.

## Ground rules

- **Describe, don't grade.** No scores, rankings, grades, recommendations, or ideological labels. The guide reports counts and cases.
- **Every claim links to a source.** Case summaries link to the opinion; background facts link to official bios, appointment releases, or election records.
- **Mechanical selection.** Which cases are listed is decided by fixed rules applied identically to every justice (below), including cases that cut against any apparent pattern.
- **Accuracy over coverage.** Anything not verified is not published; pages say "not yet reviewed" instead.
- **Base rates.** Every rate is shown next to the same rate for the justice's court over the same period.
- **No contact** with judges, courts, or campaigns.

## How the guide was made, step by step

1. **Ballot list.** The 64 justices, their courts, and their ballot wording come from the Secretary of State's list of judicial candidates, re-checked name by name.
2. **Background facts.** Appointment dates, appointing governor, prior career, earlier retention results, and public discipline were collected from official sources, one source link per fact ([justices.csv](data/justices.csv)).
3. **Opinions.** Every Supreme Court and Court of Appeal opinion in the window was loaded from CourtListener (see [Sources](#sources) and [Coverage](#coverage)).
4. **Who wrote what.** CourtListener does not record authors or panels for these courts, so software reads each opinion's signature lines to find the author, the other panel members, and any dissent or concurrence. Its accuracy was measured against hand-labeled samples before any count was published (see [Validation](#validation)).
5. **Counts.** Opinions written, publication rate, dissents, and concurrences were computed for each justice and for their court as a whole, which gives each rate its baseline ([metrics.csv](data/metrics.csv)).
6. **Topics.** Keyword rules flag opinions on each topic. Only the search-and-seizure rule has been checked by hand (see [Topics](#topics)).
7. **Case review.** For every justice (first the 17 on San Diego County ballots, then statewide), every opinion that might touch search and seizure was read, and fixed rules decided which to list (see [Which cases are listed](#which-cases-are-listed) and [Verification](#verification)).
8. **Pages.** The pages are generated from the data by a program, and the same data always produces the same pages. A word filter blocks a fixed list of loaded or ideological terms (listed in the review guide) from every page.

## Sources

- Opinions: [CourtListener](https://www.courtlistener.com/), a project of the Free Law Project. The quarterly bulk snapshot of 2026-09-30 supplies opinions through that date; the CourtListener API supplies opinions filed since. Opinion data courtesy of the Free Law Project.
- Ballot: California Secretary of State, List of Judicial Candidates (Nov. 3, 2026 General Election).
- Background: official court biographies, Governor's appointment releases, Commission on Judicial Appointments releases, Secretary of State Statements of Vote, and the Commission on Judicial Performance public decisions index.
- Supreme Court dissents from denial of review: David S. Ettinger, *At the Lectern* (Horvitz & Levy), quoted with attribution.

## Coverage

Opinions are counted from 2020-01-01. CourtListener's 2020 Court of Appeal data is incomplete: it holds about 2,750 unpublished opinions for 2020, against about 6,000 a year for 2021–2025, so 2020 counts are low for every justice. Per-year counts by court and publication status are in [the coverage report](https://github.com/bookchiq/ca-retention-guide/blob/main/data/validation/coverage.md).

## Validation

Author, panel, and separate opinions were read from each opinion's signature blocks by software, because CourtListener does not record them for these courts. Names are matched by surname, court, district, division, and date of service, never by surname alone.

Accuracy was measured against hand-labeled samples of 200 opinions, stratified so the Fourth District (which covers San Diego) and the Supreme Court were each scored on their own. The labels came from separate reviewing sessions that saw only the opinion text, not the software's answer. When a sample exposed a parser error, the error was fixed and then a **fresh** sample was drawn, so the published accuracy was never measured on opinions used to fix the parser. No count was published until every district passed.

Full results: [validation report](https://github.com/bookchiq/ca-retention-guide/blob/main/data/validation/report_parse.md).

## Topics

Topics are found by keyword matching, a first-pass filter rather than a classification. The search-and-seizure keywords' precision was checked by hand: an opinion counts only if it addresses a search or seizure claim on the merits or rules it forfeited. An opinion counts as addressing search and seizure when it decides a search or seizure claim on the merits or rules one forfeited or not cognizable (KTD9). Labels came from sessions that saw only the opinion text, in shuffled order, with no indication of which opinions the tagger had flagged.

## Round 1: original rule (any anchor term, or 3+ broader terms)

- Precision: 28.0% (14 of 50 tagged opinions; target ≥ 85%: FAIL). Most false positives mention "search warrant" once in the facts.
- Recall check: 0 of 60 untagged 4th District and Supreme Court criminal opinions had a search or seizure issue.

## Round 2: current rule, checked on a fresh sample

Rule: at least 2 distinct anchor terms and at least 4 occurrences of the core terms (Fourth Amendment, motion to suppress, section 1538.5, suppression). The rule was chosen after round 1, so it was checked on opinions not used in round 1.

- Precision: 98.0% (N = 50; target ≥ 85%: pass)
- Recall loss: 4 of 50 opinions that the old rule tagged but the current rule does not had a search or seizure issue. Scaled to the 1,707 such opinions, about 137 qualifying opinions are not counted against 586 that are, so published topic counts undercount the topic by roughly one fifth.
- The reading queue for listed cases does not use this rule. It uses a looser match (any anchor or broader term), so the stricter count rule does not remove cases from review.

Every other topic goes through the same check before its counts appear on the pages. The first, unchecked version of the search-and-seizure keywords was right only 28% of the time, so unchecked counts can mislead badly. For each topic, separate reviewing sessions that saw only the opinion text and the topic's definition labeled a random sample of the opinions its keywords flag, shuffled together with near misses the keywords skip. A topic is shown only when at least 85% of its flagged opinions really address it, measured on a sample that was not used to choose its keywords. When a topic fails, its keyword rule is tightened and then checked again on a fresh sample. The near-miss sample estimates how many qualifying opinions the keywords miss, so counts are lower bounds by about that share.

Some topics cannot be counted by keywords at all, because whether an opinion qualifies turns on who is suing or whether an issue was actually decided. For those, every opinion with a ballot justice on the panel that uses any of the topic's keywords was **read** against the topic's definition, and the count comes from those decisions instead of keywords. A random 15% was read again by a separate session that did not see the first decision; the table reports how often the two agreed, and a third reader decided every disagreement. A topic counted this way is shown only if the two readers agreed at least 90% of the time. Each decision, with the reader's note, is published in [data/topic_reads](https://github.com/bookchiq/ca-retention-guide/tree/main/data/topic_reads). Opinions that never use the keywords were not read, so these counts can still miss some qualifying opinions.

| Topic | What counts | Accuracy check | Est. missed | On the pages |
|---|---|---|---|---|
| Search and seizure | The court decides a search or seizure claim: Fourth Amendment claims, motions to suppress (Pen. Code § 1538.5), warrant sufficiency, warrantless searches and their exceptions, detentions and stops, the lawfulness of an arrest, or CalECPA suppression. | 98% (N = 50) | 19% | yes |
| Interrogation | The court decides whether a defendant's statements to police or other government agents were admissible: Miranda warnings, waiver, or invocation; custody; or whether a confession or admission was voluntary. An ineffective-assistance claim for failing to move to suppress the defendant's own statements counts when the court decides it; rulings about a third party's statements do not. | 92% (N = 50) | 34% | yes |
| Right to counsel | The court decides a right-to-counsel claim: ineffective assistance of counsel, a Marsden motion to substitute appointed counsel, a Faretta request for self-representation, a conflict of interest, or a denial of counsel or of a continuance to obtain counsel. Other Sixth Amendment issues, such as confrontation or jury-trial rights, do not count. An ineffective-assistance claim counts when the court decides it, even as an alternative to another claim; a civil motion to disqualify opposing counsel does not. | 90% (N = 50) | 58% | yes |
| Jury selection | The court decides a jury-selection claim: a Batson/Wheeler objection to a peremptory challenge, an objection under Code of Civil Procedure section 231.7, or a challenge to excusing a prospective juror for cause. Peremptory challenges to a judge (Code Civ. Proc. § 170.6) and peremptory writs are not jury selection. A for-cause claim includes refusing to excuse a juror for cause and Witherspoon/Witt death-qualification excusals. Discovery of a prosecutor's jury-selection notes, juror misconduct found after selection, and discharging a sworn juror are not this topic. | each opinion read; second readers agreed on 99% (N = 99) | none found in sample | yes |
| Racial Justice Act | The court decides a claim under the California Racial Justice Act (Pen. Code § 745), including whether a claim was properly raised, a hearing was required, or the Act applies to the case. A § 745 reference only inside a quotation of another statute does not count. | 94% (N = 50) | 22% | yes |
| Police records | The court decides a dispute over access to law-enforcement personnel or misconduct records: a Pitchess motion, Penal Code section 832.7 (including SB 1421 disclosures), or a Brady claim about officer records. A request to review the sealed transcript of a Pitchess in-camera hearing counts, because the court decides it. The Pitchess Detention Center and citations to Blair v. Pitchess are not this topic. | 92% (N = 50) | 12% | yes |
| Immigration consequences of pleas | The court decides whether a criminal conviction or plea must be vacated, or whether counsel erred, because of its immigration consequences (Pen. Code § 1473.7, Padilla claims, or related advisements under § 1016.5). A § 1473.7(a)(2) motion based on newly discovered evidence of innocence is not this topic. | 92% (N = 50) | 7% | yes |
| Resentencing | The court decides a resentencing claim under recent sentencing-reform statutes: petitions under Penal Code § 1172.6 (formerly § 1170.95, SB 1437/SB 775), recall and resentencing under §§ 1172.1 or 1172.75, or youth-offender parole and Franklin proceedings under § 3051. Former § 1170(d)(1) and § 1170.03 recalls (predecessors of § 1172.1) count. Ordinary sentencing errors, remands for resentencing on other grounds, and other resentencing statutes (Prop 47, Prop 36, § 1170.91, Prop 64, juvenile LWOP recall) do not. | 96% (N = 50) | 18% | yes |
| Arbitration | The court decides an arbitration issue: a motion to compel or stay arbitration, the enforceability or unconscionability of an arbitration agreement, waiver of the right to arbitrate, or a petition to confirm, correct, or vacate an arbitration award. Dismissing an appeal of such an order as premature or nonappealable counts. | 92% (N = 50) | 51% | yes |
| Employment | The court decides a claim between an employee (or job applicant) and an employer: discrimination, harassment, or retaliation (including FEHA), wrongful termination, wage and hour or PAGA claims, or other employment-law claims. Public-employee discipline and benefits claims count. An arbitration ruling in an employment case counts only if the court also decides an employment-law issue; claims against an employer's lawyers, or by a business against a union, do not. A ruling that a PAGA, FEHA, or wage right cannot be waived by an arbitration agreement (Iskanian, Armendariz, Gentry) is an employment-law issue and counts. | each opinion read; second readers agreed on 95% (N = 146) | 30% | yes |
| Consumer protection | The court decides a consumer-protection claim: Song-Beverly (lemon law) or other warranty claims, the Consumers Legal Remedies Act, the Unfair Competition Law, false advertising, or similar claims by consumers against businesses. Consumers include buyers, borrowers, and tenants suing a business. An Unfair Competition Law claim brought by a competitor, an employee over wages, or a taxpayer does not count, and neither does an arbitration ruling unless a consumer-protection issue is also decided. A ruling that a consumer's public-injunction claim cannot be waived by an arbitration agreement (McGill) is a consumer-protection issue and counts. | each opinion read; second readers agreed on 98% (N = 99) | none found in sample | yes |
| Landlord and tenant | The court decides a dispute between a landlord and a residential or commercial tenant: unlawful detainer (eviction), just-cause or rent-control rules, habitability, security deposits, or lease terms. An eviction after a foreclosure sale with no landlord-tenant relationship does not count, nor does a ruling in a landlord-tenant suit on an unrelated issue (for example, only an anti-SLAPP or attorney-disqualification ruling). | each opinion read; second readers agreed on 97% (N = 62) | 27% | yes |
| Public records and open meetings | The court decides a public-access claim against a government body: a California Public Records Act request, or a Brown Act (open meetings) claim. Open-meetings claims under the Bagley-Keene Act (state bodies) count, as do suits to stop an agency from releasing records. The Meyers-Milias-Brown Act and other labor laws named "Brown" are not this topic. | each opinion read; second readers agreed on 96% (N = 25) | 10% | yes |
| Anti-SLAPP | The court decides a special motion to strike under the anti-SLAPP statute (Code Civ. Proc. § 425.16), or an appeal of a ruling or fee award on one. Dismissing such an appeal as untimely counts; "protected activity" in a retaliation or civil-harassment sense does not. | 94% (N = 50) | none found in sample | yes |
| Taxes and fees | The court decides the validity or application of a tax, fee, assessment, or charge under the California Constitution's tax limits (Propositions 13, 218, and 26) or other tax law, including property-tax assessment disputes. Mitigation Fee Act and school-fee challenges count. A private contract dispute over who pays a tax, and criminal fines and fees, do not. | each opinion read; second readers agreed on 100% (N = 28) | 43% | yes |
| Land use and housing | The court decides a land-use or housing-development claim: CEQA review, zoning or general-plan consistency, permits for a project, the Housing Accountability Act, density bonus law, or similar challenges to development approvals or denials. CEQA review counts for any project, not only housing. An appeal deciding only attorney fees after a land-use case does not count, nor does building-code enforcement against a single property. | each opinion read; second readers agreed on 98% (N = 43) | 25% | yes |

"What counts" means the court decided the issue (on the merits, or by ruling it forfeited, waived, moot, or not reviewable); a mention in the facts does not count. Counts for topics not yet shown are in [metrics.csv](data/metrics.csv), marked "unvalidated keywords", for anyone who wants them. Full results, round by round: [topic validation report](https://github.com/bookchiq/ca-retention-guide/blob/main/data/validation/report_topics.md); labeling instructions: [topic labeling guide](https://github.com/bookchiq/ca-retention-guide/blob/main/docs/topic-labeling-guide.md).

## Which cases are listed

For each justice, the guide lists every search-and-seizure case where the justice:

1. wrote a dissent, concurrence, or concurrence-and-dissent;
2. wrote a published majority opinion;
3. wrote a majority opinion that reversed, vacated, modified, or granted writ relief on the issue, in either direction;
4. was in the majority over another justice's dissent on the issue.

For the Supreme Court, every majority opinion the justice wrote on the topic is listed. Candidates are drawn generously by keyword and then decided by reading; every exclusion is recorded with its reason and published in the [case data](data/case_notes.csv).

A case counts as being about search and seizure only if the court actually decided a search or seizure claim, or ruled it forfeited or improperly raised. A warrant mentioned only in the facts does not count. Neither do Miranda-only issues, probation conditions, bail rulings, or "probable cause" to hold a defendant for trial. The full reviewer instructions are in the [review guide](https://github.com/bookchiq/ca-retention-guide/blob/main/docs/review-guide.md).

## Verification

Each case went through these steps, with the reading, verification, and second check done by **separate** AI sessions:

1. **Reading.** A reviewer read the opinion, decided whether search and seizure was actually at issue, applied the listing rules, and wrote the record and summary.
2. **Verification.** A different reviewer re-opened the opinion and confirmed the case name and docket against the opinion's own caption, the author and panel from the signature lines, the disposition, the listing rule, the vote, and that the summary matches the holding.
3. **Second check.** A third, fresh reviewer re-read a random 15% of each justice's records (at least one per justice), both listed and excluded. Any substantive error would have sent that justice's whole set back to verification.
4. **Consistency.** A case that appears for several justices must get the same decision about whether search and seizure was at issue for each of them.
5. **Author spot check.** Sarah Lewis read 10 randomly drawn summaries against their opinions before publication. She found them accurate, though a few leave out some context.

Results so far: 1223 records for 53 justices were reviewed. 70 cases are listed and 1153 were excluded, for these reasons:

| Reason for exclusion | Records |
|---|---|
| `topic_not_at_issue` | 1109 |
| `topic_issue_affirmed` | 30 |
| `dissent_on_other_issue` | 7 |
| `no_rule_applies` | 6 |
| `duplicate` | 1 |

The second check re-read 204 records; 0 had a substantive error.

The [case data](data/case_notes.csv) includes every record, listed or excluded, with each reviewer's notes on what they checked.

## Known weaknesses

- **Summaries are short.** Each is at most 50 words. They were checked for accuracy, but some leave out context a lawyer would want, so read the opinion before relying on one.
- **Judgment calls.** Deciding whether a search issue was "at issue" is sometimes close. Each such call, and every rule clarification made during review, is in the [decisions log](https://github.com/bookchiq/ca-retention-guide/blob/main/DECISIONS.md).
- **Source errors.** CourtListener occasionally files an opinion under the wrong case name. Reviewers check each case name against the opinion's own caption; the errors found are listed in the decisions log.
- **Filing dates.** Dates come from CourtListener, which sometimes records an opinion one to three days after the "Filed" date printed on it. Reviewers noted these differences but did not change the dates.
- **Keyword counts undercount.** Every topic's counts are a floor: the keywords miss some qualifying opinions, from about one in five (search and seizure) to more than half (right to counsel, arbitration). The table under [Topics](#topics) gives each estimate. The search-and-seizure case lists are not affected, because review started from a much broader match.
- **Two ways of counting.** Nine topics are counted by keyword rules that passed a hand check; seven (jury selection and six civil topics) are counted from AI readers' decisions on each candidate opinion, because no keyword rule could count them accurately. Read-based counts are more precise, but they cover only opinions with a ballot justice on the panel that use the topic's keywords, and the readers' close calls are judgment calls; every decision and its note is public so it can be checked.

## Limitations

1. **California courts follow federal search-and-seizure rules.** Under the Truth-in-Evidence provision (Cal. Const., art. I, § 28(f)(2); *In re Lance W.* (1985) 37 Cal.3d 873), state courts may exclude evidence only where the U.S. Constitution requires it. Differences between justices appear mostly in how they apply precedent to close facts.
2. **Panels.** Three justices decide each Court of Appeal case. Outcomes reflect the panel; authored and separate opinions are the clearest individual signals.
3. **Selection effects.** Which cases are appealed, and which justice writes, are not random. Many criminal appeals are affirmed, which says little about the justice.
4. **Unpublished opinions** are public but generally cannot be cited as precedent (Cal. Rules of Court, rule 8.1115). They are included because they are most of the record.
5. **Coverage and errors.** Data comes from CourtListener and is limited to the stated window. Measured parsing and tagging error rates are published above.
6. **Supreme Court docket.** The Supreme Court chooses its cases, so its record looks different. Dissents from denial of review come from a third-party compilation.
7. **Short tenures.** Some justices have little or no appellate record; their pages say so.
8. **Not advice or endorsement.** The guide does not recommend a vote.

## AI assistance

The data was collected and analyzed with AI tools (Claude). AI sessions wrote the parsing code, labeled the validation samples, and read, verified, and second-checked every case. The author wrote the specification the listing rules come from, made the scope decisions, and read a random sample of summaries against the opinions. Clarifications to the rules came up during review and were made within that process, not by the author case by case; each one is dated and explained in the [decisions log](https://github.com/bookchiq/ca-retention-guide/blob/main/DECISIONS.md).

## Check the work yourself

- [Source code](https://github.com/bookchiq/ca-retention-guide) for every step, with its tests.
- [Validation reports](https://github.com/bookchiq/ca-retention-guide/tree/main/data/validation): the samples, the labels, and the scores.
- [Review guide](https://github.com/bookchiq/ca-retention-guide/blob/main/docs/review-guide.md): the instructions every reviewer followed.
- [Decisions log](https://github.com/bookchiq/ca-retention-guide/blob/main/DECISIONS.md): every change to scope, rules, or method, with the date and reason.
- Data files: [justices.csv](data/justices.csv), [metrics.csv](data/metrics.csv), [case_notes.csv](data/case_notes.csv).

## Corrections

This guide is an experiment and a work in progress. If you find an error, please open an [issue](https://github.com/bookchiq/ca-retention-guide/issues) or a [pull request](https://github.com/bookchiq/ca-retention-guide/pulls) on GitHub, or email Sarah Lewis at sarah@happyhumans.com. Corrections are logged in [DECISIONS.md](https://github.com/bookchiq/ca-retention-guide/blob/main/DECISIONS.md).

## Changelog

See [DECISIONS.md](https://github.com/bookchiq/ca-retention-guide/blob/main/DECISIONS.md).
