# Parsing validation report

Thresholds (SPEC §7.3.8): author ≥ 98%, panel membership ≥ 97%, separate-opinion detection ≥ 95%. The pooled sample must pass; the 4th District (≥ 60 labeled) and the Supreme Court (≥ 30) are also gated on their own strata, stated as allowed error counts.

| Stratum | Field | N | Errors | Allowed | Accuracy | Pass |
|---|---|---|---|---|---|---|
| pooled | author | 200 | 0 | 4 | 100.0% | yes |
| pooled | panel | 200 | 1 | 6 | 99.5% | yes |
| pooled | separate | 200 | 0 | 10 | 100.0% | yes |
| 1 | author | 20 | 0 | 0 | 100.0% | yes |
| 1 | panel | 20 | 0 | 0 | 100.0% | yes |
| 1 | separate | 20 | 0 | 1 | 100.0% | yes |
| 2 | author | 30 | 0 | 0 | 100.0% | yes |
| 2 | panel | 30 | 0 | 0 | 100.0% | yes |
| 2 | separate | 30 | 0 | 1 | 100.0% | yes |
| 3 | author | 19 | 0 | 0 | 100.0% | yes |
| 3 | panel | 19 | 0 | 0 | 100.0% | yes |
| 3 | separate | 19 | 0 | 0 | 100.0% | yes |
| 4 | author | 66 | 0 | 1 | 100.0% | yes |
| 4 | panel | 66 | 0 | 1 | 100.0% | yes |
| 4 | separate | 66 | 0 | 3 | 100.0% | yes |
| 5 | author | 20 | 0 | 0 | 100.0% | yes |
| 5 | panel | 20 | 0 | 0 | 100.0% | yes |
| 5 | separate | 20 | 0 | 1 | 100.0% | yes |
| 6 | author | 15 | 0 | 0 | 100.0% | yes |
| 6 | panel | 15 | 0 | 0 | 100.0% | yes |
| 6 | separate | 15 | 0 | 0 | 100.0% | yes |
| supreme | author | 30 | 0 | 0 | 100.0% | yes |
| supreme | panel | 30 | 1 | 0 | 96.7% | no |
| supreme | separate | 30 | 0 | 1 | 100.0% | yes |

District status: 1: pass, 2: pass, 3: pass, 4: pass, 5: pass, 6: pass, supreme: FAIL
