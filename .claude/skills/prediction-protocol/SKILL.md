---
name: prediction-protocol
description: Make a scientific, engineering or ML prediction whose accuracy can be trusted. Use before predicting any outcome that will be scored, published or acted on, so the outcome can never reach the prediction.
---

# Prediction protocol

Goal: a prediction that could have been wrong, made from information that existed before the outcome,
committed before anyone could see the answer.

## 0. Settle the question first
- Write down the target, the outcome definition and the scoring rule **before** looking at any data.
  Store it as a prediction card (`templates/prediction_card.md`) and log it:
  `oguard log note --id note:card --file prediction_card.md`
- Set `as_of` in `oguard.yaml` to the moment predictions are made. If outcomes for some targets are
  already public, either exclude those targets or label the evaluation "recall", not "prediction".

## 1. Register inputs
For each dataset or fact the model may use:
```bash
oguard log input --id input:<name> --available-at <date it existed> --file <path>
```
Ask of every column: *could this value have been recorded before the outcome existed?* If not, drop it
(proxy features such as "selected for follow-up" or "number of papers about this item" are classic leaks).

## 2. Retrieve through the firewall
Wrap every search, RAG or database tool:
```python
from ouroboros_guard import TimeFirewall, Ledger
fw = TimeFirewall(as_of, missing_date_policy="reject", blocked_sources=[...], ledger=Ledger(".oguard/ledger.jsonl"))
search = fw.wrap(search)          # results dated at/after as_of never reach you
```
Record `origin` (the original study or dataset) on each document so repeated reports count once.

## 3. Derive and predict
Log derived artefacts with their parents, then the prediction:
```bash
oguard log derive --id derive:features --parent input:<name>
oguard log prediction --id prediction:<t> --target <t> --parent derive:features --meta model=<id>
```
Your whole context window counts as an ancestor. If earlier reading may have exposed outcomes, predict in
a fresh subagent that receives only registered inputs and log it with `--meta context=isolated`.

## 4. Commit before the outcome exists
```bash
oguard commit predictions.jsonl --prediction prediction:<t>
```
Publish `predictions.jsonl.commit.json` (timestamped: a git tag, a public post, an email to a colleague).
Keep the `.salt` private. Never edit the file afterwards.

## 5. Controls, then reveal
- Run `negative-controls` (scrambled labels, masked identities, pre/post training cut-off).
- When outcomes arrive: `oguard log outcome --target <t>`, `oguard verify predictions.jsonl`, score **once**
  through `HoldoutGuard`.

## 6. Audit and report
`oguard check` must be clean, then `oguard audit --format md --out AUDIT.md`. In the report give:
the position on the leakage spectrum, the score with its uncertainty, the replicate ceiling, and every audit
answer that is not `pass`.

## Stop conditions
Stop and tell the human if a hook blocks you, `oguard check` reports a critical finding, a score exceeds the
replicate ceiling, or a negative control does not fall to chance.
