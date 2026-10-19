# Coverage report

Opinion clusters per year in `data/cases.sqlite`, by court and publication status. A Court of Appeal year below 80% of the expected ~7,000 opinions is flagged LOW.

| Year | Court | Published | Unpublished | Other | Total | Flag |
|---|---|---|---|---|---|---|
| 2019 | cal | 151 | 0 | 0 | 151 |  |
| 2020 | cal | 82 | 0 | 0 | 82 |  |
| 2020 | calctapp | 1060 | 2750 | 0 | 3810 | LOW |
| 2021 | cal | 64 | 0 | 0 | 64 |  |
| 2021 | calctapp | 970 | 6173 | 0 | 7143 |  |
| 2022 | cal | 57 | 0 | 0 | 57 |  |
| 2022 | calctapp | 921 | 5914 | 0 | 6835 |  |
| 2023 | cal | 55 | 0 | 0 | 55 |  |
| 2023 | calctapp | 891 | 5657 | 0 | 6548 |  |
| 2024 | cal | 61 | 0 | 0 | 61 |  |
| 2024 | calctapp | 732 | 5584 | 0 | 6316 |  |
| 2025 | cal | 53 | 0 | 0 | 53 |  |
| 2025 | calctapp | 749 | 6248 | 0 | 6997 |  |
| 2026 | cal | 47 | 0 | 0 | 47 | partial year through 2026-10-16 |
| 2026 | calctapp | 536 | 4928 | 0 | 5464 | partial year through 2026-10-16 |

## Projected Tier 1 reading workload

Opinions with at least one `search_seizure` anchor term, in the courts the San Diego set sits on. This is an upper bound on what the reading queue draws from: the queue only includes cases a given justice wrote, joined over a dissent, or that were reversed or published.

| Window starts | 4th District opinions with an anchor | Supreme Court opinions with an anchor |
|---|---|---|
| 2020-01-01 | 555 | 58 |
| 2023-01-01 | 314 | 28 |
