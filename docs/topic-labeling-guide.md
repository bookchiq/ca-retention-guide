# Topic labeling guide

How validation samples for topic keywords are labeled. A labeler gets one topic's definition, a folder of opinion texts, and a blank label file. The labeler is not told which opinions the keyword rule tagged; the folder mixes tagged opinions with near misses, in shuffled order.

## The question

For each opinion: **does the court decide an issue within the topic's definition?**

- `1`: the court decides such an issue, on the merits or by ruling it forfeited, waived, moot, not cognizable, or not ripe. A short ruling counts; a Wende or Anders review that addresses the issue counts.
- `0`: the topic appears only in the facts, the procedural history, a quotation, a string cite, a description of what happened below without any ruling on it, a footnote saying the court need not reach it, or a separate opinion only.

When the issue is decided in a separate opinion but not by the court, label `0` and say so in the note.

## How to read

Opinions are long. Read the introduction and the disposition, then find every place the topic comes up and read it in context. Do not stop at the first mention; the decided issues are usually in the Discussion section.

## The label file

Fill `at_issue` with `0` or `1` for every row, and write a short `notes` entry (a few words: the issue decided, or why the topic is only mentioned). If a call is genuinely close, start the note with `CLOSE:` and explain; still choose `0` or `1`. Do not leave a row blank, and do not add or remove rows.

Do not open anything outside the packet folder and the label file, and do not look at the keyword lists. The point is an independent reading.
