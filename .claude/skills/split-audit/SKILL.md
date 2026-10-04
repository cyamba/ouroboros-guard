---
name: split-audit
description: Build or check train/test (and development) splits so the test set is genuinely new. Use when creating benchmarks, splitting data for an agent, or reviewing a reported test score.
---

# Split audit

A random split puts near-copies on both sides; the model then recognises neighbours instead of learning a rule.

## Choose the split before modelling
| Data | Split by |
|------|----------|
| items with families (molecules by scaffold, proteins by sequence cluster, materials by composition family, documents by source) | group |
| repeated measures (patients, devices, labs, batches) | group |
| anything that will be used to predict the future | time |
| truly exchangeable, independent items | random is acceptable |

```python
from ouroboros_guard.splits import group_split, time_split, group_overlap
test_mask = group_split(cluster_ids, test_fraction=0.2, seed=0)
test_mask = time_split(measurement_dates, cutoff="2026-01-01")
```

## Measure how new the test set is
```bash
oguard split-audit --train train.txt --test test.txt --threshold 0.9      # one item per line (text, SMILES, sequences)
```
Python, for vectors and fingerprints:
```python
from ouroboros_guard.splits import audit_split
audit_split(train_vectors, test_vectors, metric="cosine", threshold=0.95).save(".oguard")
audit_split(train_bits, test_bits, metric="tanimoto", threshold=0.7)
```
Report the distribution of nearest-neighbour similarity with the score, and the score broken down by
similarity band. A model whose accuracy collapses on the least similar test items is interpolating.

## Three sets, three jobs
- **train**: fitting.
- **development**: every decision, as often as you like.
- **test**: once, at the end, through `HoldoutGuard(budget=1)`. If you must reuse it, use `mode="thresholdout"`.
