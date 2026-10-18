# Parsing validation report: Supreme Court sample

Thresholds (SPEC §7.3.8): author ≥ 98%, panel membership ≥ 97%, separate-opinion detection ≥ 95%. The pooled sample must pass; the 4th District (≥ 60 labeled) and the Supreme Court (≥ 30) are also gated on their own strata, stated as allowed error counts.

| Stratum | Field | N | Errors | Allowed | Accuracy | Pass |
|---|---|---|---|---|---|---|
| pooled | author | 40 | 0 | 0 | 100.0% | yes |
| pooled | panel | 40 | 0 | 1 | 100.0% | yes |
| pooled | separate | 40 | 0 | 2 | 100.0% | yes |
| supreme | author | 40 | 0 | 0 | 100.0% | yes |
| supreme | panel | 40 | 0 | 1 | 100.0% | yes |
| supreme | separate | 40 | 0 | 2 | 100.0% | yes |

District status: supreme: pass
