# Parsing validation report: first sample

This first sample was used to find and fix parser gaps, so the table below (scored after those fixes) is not an independent measure and does not decide the gate. Before the fixes, after correcting name comparison, the 4th District stratum scored 100% on all three fields (73 opinions). The gate is decided by a fresh sample; see `report_parse_holdout.md` and `report_parse_v3.md`.

Thresholds (SPEC §7.3.8): author ≥ 98%, panel membership ≥ 97%, separate-opinion detection ≥ 95%. The pooled sample must pass; the 4th District (≥ 60 labeled) and the Supreme Court (≥ 30) are also gated on their own strata, stated as allowed error counts.

| Stratum | Field | N | Errors | Allowed | Accuracy | Pass |
|---|---|---|---|---|---|---|
| pooled | author | 200 | 0 | 4 | 100.0% | yes |
| pooled | panel | 200 | 0 | 6 | 100.0% | yes |
| pooled | separate | 200 | 0 | 10 | 100.0% | yes |
| 1 | author | 18 | 0 | 0 | 100.0% | yes |
| 1 | panel | 18 | 0 | 0 | 100.0% | yes |
| 1 | separate | 18 | 0 | 0 | 100.0% | yes |
| 2 | author | 28 | 0 | 0 | 100.0% | yes |
| 2 | panel | 28 | 0 | 0 | 100.0% | yes |
| 2 | separate | 28 | 0 | 1 | 100.0% | yes |
| 3 | author | 19 | 0 | 0 | 100.0% | yes |
| 3 | panel | 19 | 0 | 0 | 100.0% | yes |
| 3 | separate | 19 | 0 | 0 | 100.0% | yes |
| 4 | author | 73 | 0 | 1 | 100.0% | yes |
| 4 | panel | 73 | 0 | 2 | 100.0% | yes |
| 4 | separate | 73 | 0 | 3 | 100.0% | yes |
| 5 | author | 16 | 0 | 0 | 100.0% | yes |
| 5 | panel | 16 | 0 | 0 | 100.0% | yes |
| 5 | separate | 16 | 0 | 0 | 100.0% | yes |
| 6 | author | 15 | 0 | 0 | 100.0% | yes |
| 6 | panel | 15 | 0 | 0 | 100.0% | yes |
| 6 | separate | 15 | 0 | 0 | 100.0% | yes |
| supreme | author | 31 | 0 | 0 | 100.0% | yes |
| supreme | panel | 31 | 0 | 0 | 100.0% | yes |
| supreme | separate | 31 | 0 | 1 | 100.0% | yes |

District status: 1: pass, 2: pass, 3: pass, 4: pass, 5: pass, 6: pass, supreme: pass
