---
name: negative-controls
description: Prove that a pipeline or agent cannot score well when there is nothing to find. Use before reporting any score, and whenever a result seems too good.
---

# Negative controls

An honest pipeline falls to chance when the labels are scrambled. One that does not is reading the answer
from somewhere other than its inputs.

## 1. Scrambled labels through the WHOLE pipeline
Every step must rerun on the scrambled labels: feature selection, tuning, model choice, thresholds, and any
decision the agent made after seeing scores. Scrambling only the final fit misses the leak.

Python:
```python
from ouroboros_guard.controls import permutation_control
res = permutation_control(pipeline, X, y, runs=200)     # pipeline(X, y) -> score
print(res.describe()); res.save(".oguard")
```
Any program (it must print its score as the last number):
```bash
oguard control --cmd "python train_eval.py --labels {labels}" --labels data/train_labels.csv --runs 100
```
Use `groups=` (Python) when rows are clustered (patients, batches, labs) so permutations respect the clusters.

## 2. Masked identities (literature-reading agents)
Scrambled labels do not scramble the literature. Replace names with neutral codes so retrieval and memory
cannot recognise the item:
```python
from ouroboros_guard.controls import mask_entities
masked, mapping = mask_entities(descriptions, entity_names)
```
A large drop in accuracy after masking means the agent was recognising items, not reasoning about them.

## 3. Temporal gap (memorisation)
Compare accuracy on outcomes that were public before the model's training cut-off with those published after:
```python
from ouroboros_guard.controls import temporal_gap
print(temporal_gap(correct, outcome_dates, cutoff="2025-01-01").describe())
```
A model that predicts the past much better than the future is remembering.

## 4. Memorisation probe
`memorisation_probe(model_fn, documents)` asks the model to continue documents it should not know.
High verbatim overlap means the evaluation is contaminated.

## Reading the result
- Scrambled mean above chance + tolerance: **leak**. Find it before anything else.
- Real score inside the null distribution (`p_value` large): there is no detectable signal.
- Both fine: the control passed. It shows the pipeline cannot exploit label noise; it does not prove the
  absence of every leak (masking and temporal checks cover others).
