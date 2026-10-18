# Parsing validation report: holdout sample (second sample)

**Independent result, scored before any fix it prompted:** author 100.0% (200/200), panel 96.0% (192/200), separate opinions 99.5% (199/200). The gate failed on panel membership.

The table below is the same sample re-scored **after** the parser was fixed for its misses, so it is not an independent measure and does not decide the gate. A third sample (`sample_parse_v3.csv`) does.

Thresholds (SPEC §7.3.8): author ≥ 98%, panel membership ≥ 97%, separate-opinion detection ≥ 95%. The pooled sample must pass; the 4th District (≥ 60 labeled) and the Supreme Court (≥ 30) are also gated on their own strata, stated as allowed error counts.

| Stratum | Field | N | Errors | Allowed | Accuracy | Pass |
|---|---|---|---|---|---|---|
| pooled | author | 200 | 0 | 4 | 100.0% | yes |
| pooled | panel | 200 | 2 | 6 | 99.0% | yes |
| pooled | separate | 200 | 0 | 10 | 100.0% | yes |
| 1 | author | 17 | 0 | 0 | 100.0% | yes |
| 1 | panel | 17 | 1 | 0 | 94.1% | no |
| 1 | separate | 17 | 0 | 0 | 100.0% | yes |
| 2 | author | 33 | 0 | 0 | 100.0% | yes |
| 2 | panel | 33 | 1 | 0 | 97.0% | no |
| 2 | separate | 33 | 0 | 1 | 100.0% | yes |
| 3 | author | 17 | 0 | 0 | 100.0% | yes |
| 3 | panel | 17 | 0 | 0 | 100.0% | yes |
| 3 | separate | 17 | 0 | 0 | 100.0% | yes |
| 4 | author | 69 | 0 | 1 | 100.0% | yes |
| 4 | panel | 69 | 0 | 2 | 100.0% | yes |
| 4 | separate | 69 | 0 | 3 | 100.0% | yes |
| 5 | author | 18 | 0 | 0 | 100.0% | yes |
| 5 | panel | 18 | 0 | 0 | 100.0% | yes |
| 5 | separate | 18 | 0 | 0 | 100.0% | yes |
| 6 | author | 16 | 0 | 0 | 100.0% | yes |
| 6 | panel | 16 | 0 | 0 | 100.0% | yes |
| 6 | separate | 16 | 0 | 0 | 100.0% | yes |
| supreme | author | 30 | 0 | 0 | 100.0% | yes |
| supreme | panel | 30 | 0 | 0 | 100.0% | yes |
| supreme | separate | 30 | 0 | 1 | 100.0% | yes |

District status: 1: pass, 2: pass, 3: pass, 4: pass, 5: pass, 6: pass, supreme: pass
