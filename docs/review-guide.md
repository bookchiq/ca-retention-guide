# Case review guide (Tier 1: search and seizure)

How each queued case is read, decided, and recorded. The same rules apply to every justice. Authority: `SPEC.md` §8.3–8.5 and §10, as amended in `DECISIONS.md` (KTD7).

## 1. Is the topic at issue?

The case is **at issue** if the court decides a search or seizure claim on the merits, or rules one forfeited, waived, or not cognizable: Fourth Amendment claims; motions to suppress (Pen. Code § 1538.5); warrant sufficiency; warrantless searches and their exceptions (consent, exigency, automobile, search incident to arrest, probation/parole/Fourth-waiver searches, inevitable discovery, good faith); detentions, stops, pat-downs, prolonged stops; the lawfulness of an arrest as a seizure; CalECPA suppression. An ineffective-assistance claim counts only if the court analyzes whether the search or seizure was lawful. Mentions in the facts or procedural history, probation-condition challenges (Lent/overbreadth), Miranda-only issues, bail and pretrial-detention rulings (*Humphrey*), and "probable cause" to hold a defendant to answer (Pen. Code § 995) are **not** at issue.

A ruling on how a suppression motion is litigated (its timeliness, a continuance of the suppression hearing, whether a hearing must be held) **is** at issue: it rules on the claim the way a forfeiture ruling does. *(Clarified 2026-10-18 after two readers decided* People v. Brown *(S271877) differently.)*

Not at issue → `listing_decision: excluded`, `exclusion_reason: topic_not_at_issue`. Stop.

A case shared by several justices' queues gets the same at-issue decision for every justice.

## 2. Which listing rule applies?

Check the queue entry's `candidate_rules`, then decide from the opinion. Use the first rule that applies, in this order.

| Rule | List the case when | Role | If it does not hold |
|---|---|---|---|
| L1 | The justice wrote a separate opinion (dissent, concurrence, or both) that addresses the search or seizure issue | `dissent`, `concurrence`, or `concur_dissent` | Separate opinion on another issue → exclude, `dissent_on_other_issue` |
| SC | Supreme Court: the justice wrote the majority opinion | `author` | — |
| L2 | The justice wrote a published majority opinion | `author` | — |
| L3 | The justice wrote a majority opinion that reversed, vacated, modified, or granted writ relief **on the search or seizure issue**, in either direction (including the People's appeal reversing a suppression order) | `author` | Relief granted on a different issue, search issue rejected → exclude, `topic_issue_affirmed` |
| L4 | The justice wrote or joined the majority over another justice's dissent **on the search or seizure issue** | `joined_majority_over_dissent` (or `author` if they wrote it) | Dissent on another issue → exclude, `dissent_on_other_issue` |

A queued opinion that is the same decision as another queued one (a modified version, a duplicate) → exclude, `duplicate`.

The issue is at issue but the justice's role meets none of the rules (for example, they joined a dissent another justice wrote, or joined a unanimous unpublished affirmance) → exclude, `no_rule_applies`.

## 3. The record (listed cases)

Fill every field of the draft in `data/drafts/<justice>/search_seizure.jsonl`:

- `listing_decision: listed`, `listing_rule`, `role` (from the table)
- `issue_type`: `warrant_sufficiency`, `warrantless_exception`, `detention_or_stop`, `consent`, `probation_parole_search`, `electronic_data`, `vehicle`, `home_entry`, or `other`
- `posture`: `defendant_appeal`, `people_appeal`, `writ_by_defendant`, `writ_by_people`, `civil_appeal`, or `other`
- `trial_court_ruling`: one short sentence (e.g., "Denied the motion to suppress.")
- `result_on_issue`: one short sentence on what the appellate court held on the search or seizure issue
- `outcome`: `evidence_suppressed_or_search_held_unlawful`, `search_upheld`, `mixed`, or `not_reached` (forfeited, harmless, or decided on other grounds)
- `vote`: `3-0`, `2-1`, `7-0`, `6-1`, etc., counting only justices who decided the case
- `summary`: at most 50 words, written to the style rules below
- `published`: true or false, as printed on the opinion

Leave `verified` false. Verification is a separate step by a different session.

## 4. Summary style (SPEC §10)

- At most 50 words. Past tense. Lead with the justice's role ("Wrote the opinion…", "Dissented from…", "Joined the 2–1 majority…").
- State the issue, the holding, and the disposition. Include the vote if split.
- Neutral party terms: "the defendant", "officers", "the prosecution" or "the People". Use the case name only in the citation fields.
- No adjectives about the justice or the outcome, no motive, nothing about the crime beyond what the issue needs, and no victims' names.
- Never use: pro-police, anti-police, soft on crime, tough on crime, activist, liberal, conservative, radical, lenient, rubber-stamp, heroic, outrageous.
- If it cannot be said neutrally in 50 words, quote the opinion's one-sentence statement of its holding and give the page.

Good: "Wrote the 2–1 majority holding that a warrant affidavit relying on an uncorroborated anonymous tip did not establish probable cause; reversed the denial of the suppression motion."

## 5. Verification (a different session)

Re-open the opinion and confirm: the case name and docket number match the opinion's own caption (CourtListener occasionally files an opinion under another case's name; correct the record to the caption and note it), the author and panel from the signature lines (or the Supreme Court attribution), the disposition sentence, the listing rule and role, the vote, and that the summary matches the holding. Fix anything wrong, then stamp with `python -m src.review verify --justice <slug> --by <session> --ids ...`.

## 6. Second check and promotion

A fresh session re-checks a random 15% of each justice's decided records, listed and excluded (`review sample`, `review check`, `review finish-check`). Any substantive error sends the whole justice back to verification and gets a `DECISIONS.md` entry. Only then does `review promote` write the records to `data/case_notes.jsonl`. Those commits stay unpushed until the owner's spot check passes.
