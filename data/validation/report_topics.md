# Topic keyword validation

For each topic, a random sample of the opinions its keyword rule tags was labeled by sessions that saw only the opinion text and the topic's definition, in shuffled order, mixed with near-miss opinions the rule does not tag. Precision is the share of tagged opinions that address the topic; a topic is shown on the pages only at 85% or higher on a sample not used to choose its rule. The undercount estimate scales the near-miss hits to the whole near-miss pool.

| Topic | Round | Rule | Tagged | Precision | Near-miss hits | Est. undercount | Shown |
|---|---|---|---|---|---|---|---|
| Anti-SLAPP | r1 | any anchor | 1154 | 72% (N = 50) | 0 of 30 | none found in sample | no |
| Arbitration | r1 | any anchor | 1447 | 64% (N = 50) | 4 of 30 | 10% | no |
| Consumer protection | r1 | any anchor | 1021 | 28% (N = 50) | 0 of 30 | none found in sample | no |
| Employment | r1 | any anchor | 1513 | 52% (N = 50) | 3 of 30 | 30% | no |
| Immigration consequences of pleas | r1 | any anchor | 497 | 62% (N = 50) | 0 of 30 | none found in sample | no |
| Interrogation | r1 | any anchor | 1568 | 26% (N = 50) | 0 of 30 | none found in sample | no |
| Jury selection | r1 | any anchor | 1014 | 14% (N = 50) | 0 of 30 | none found in sample | no |
| Land use and housing | r1 | any anchor | 411 | 74% (N = 50) | 6 of 30 | 25% | no |
| Landlord and tenant | r1 | any anchor | 651 | 38% (N = 50) | 1 of 30 | 27% | no |
| Police records | r1 | any anchor | 369 | 64% (N = 50) | 1 of 30 | 4% | no |
| Public records and open meetings | r1 | any anchor | 227 | 38% (N = 50) | 1 of 30 | 10% | no |
| Racial Justice Act | r1 | any anchor | 416 | 66% (N = 50) | 0 of 30 | none found in sample | no |
| Resentencing | r1 | any anchor | 8186 | 84% (N = 50) | 3 of 30 | 1% | no |
| Right to counsel | r1 | any anchor | 6256 | 72% (N = 50) | 2 of 30 | 2% | no |
| Search and seizure | r2 | ≥2 distinct anchors, ≥4 core-term uses | 598 | 98% (N = 50) | 4 of 50 | 19% | yes |
| Taxes and fees | r1 | any anchor | 283 | 40% (N = 50) | 1 of 30 | 43% | no |

Per-opinion labels: `labels_topic_<topic>_<round>.csv` in this folder.
