# Tag validation: search_seizure

An opinion counts as addressing search and seizure when it decides a search or seizure claim on the merits or rules one forfeited or not cognizable (KTD9). Labels came from sessions that saw only the opinion text, in shuffled order, with no indication of which opinions the tagger had flagged.

## Round 1: original rule (any anchor term, or 3+ broader terms)

- Precision: 28.0% (14 of 50 tagged opinions; target ≥ 85%: FAIL). Most false positives mention "search warrant" once in the facts.
- Recall check: 0 of 60 untagged 4th District and Supreme Court criminal opinions had a search or seizure issue.

## Round 2: current rule, checked on a fresh sample

Rule: at least 2 distinct anchor terms and at least 4 occurrences of the core terms (Fourth Amendment, motion to suppress, section 1538.5, suppression). The rule was chosen after round 1, so it was checked on opinions not used in round 1.

- Precision: 98.0% (N = 50; target ≥ 85%: pass)
- Recall loss: 4 of 50 opinions that the old rule tagged but the current rule does not had a search or seizure issue. Scaled to the 1,707 such opinions, about 137 qualifying opinions are not counted against 586 that are, so published topic counts undercount the topic by roughly one fifth.
- The reading queue for listed cases does not use this rule. It uses a looser match (any anchor or broader term), so the stricter count rule does not remove cases from review.
