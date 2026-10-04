# Threat model

## What is protected
The **outcome** of whatever is being predicted (an experimental result, a measurement, a benchmark answer,
a proof of the target theorem), and the **test labels** used to score predictions.

## Who the adversary is
Usually nobody. Leakage is overwhelmingly accidental: capable tools doing ordinary things in a world where
answers get published. The model therefore assumes a *careless* rather than a malicious agent, with one
exception: an optimising agent (one that iterates against a score) will exploit any leak it can reach,
without intending to. Treat optimisers as adversaries of the test set.

## Leak channels

| Code | Channel | How the loop closes | Prevent | Detect |
|------|---------|---------------------|---------|--------|
| L1 | Memorised answers | the model was trained on text that reports the outcome | evaluate after the training cut-off | `temporal_gap`, `memorisation_probe`, audit Q2 |
| L2 | Retrieved answers | search, RAG or a database returns the outcome, a later paper citing it, or a press release | `TimeFirewall`, `blocked_sources`, hooks | G2–G4 on retrievals, ledger review |
| L3 | Proxy features | an input exists only because of the outcome ("selected for follow-up", annotation added after the result) | input review, `available_at` on inputs | G3 on inputs, audit Q4 |
| L4 | Near-duplicate splits | test items are near-copies of training items | group or time splits | `split-audit`, audit Q5 |
| L5 | Test-set steering | the agent iterates against the evaluation score | development set; `HoldoutGuard` | G8, audit Q6 |
| L6 | Self-grading | the generator, or a model sharing its information, judges the output | independent judges | G9, audit Q7 |
| L7 | Definitional loops | the outcome is defined from an input or from the model's own output | prediction card, review | human review |

Statistical channels (no agent required):

| Code | Channel | Detect |
|------|---------|--------|
| S1 | Double dipping: selection and testing on the same data | negative control through the whole pipeline |
| S2 | Preprocessing on all data before the split (scaling, imputation, target encoding, feature selection) | negative control |
| S3 | Double counting the same data, or citation echo | G10, audit Q8 |
| S4 | Garden of forking paths: analysis choices made after seeing outcomes | prediction card committed before analysis |

Proof channels:

| Code | Channel | Detect |
|------|---------|--------|
| M1 | The goal used as a premise, directly or through a chain | P1, P2 |
| M2 | An equivalent of the goal assumed as "obvious" | P2 with `equivalent:` declarations |
| M3 | Reasoning backwards through non-reversible steps | P4 |
| M4 | Unproved steps or assumed theorems in formal proofs | L1, L2, L3 |
| M5 | Citing a result whose own proof depends on the goal | `cited` statements need references that are checked separately |

## Trust boundaries and residual risk

- **Hooks run inside the agent's environment.** An agent with an unrestricted shell can read anything the
  user can. The hook blocks direct and obvious indirect access (paths in commands, recursive searches over
  sealed directories) and logs the rest. For real guarantees, keep outcomes on a different machine, in a
  store the agent has no credentials for, or behind the sealed evaluator service (implementation plan, phase 6).
- **The ledger records what is logged.** Unlogged channels (a human pasting a spoiler into a prompt) are
  invisible to it. `context_is_ancestor` makes everything the agent fetched count; the rest relies on
  discipline and review.
- **Metadata can lie.** A preprint re-uploaded with a new date passes a date filter. Block by origin and by
  identifier as well.
- **Memorisation is measured, not prevented.** Results on pre-cut-off outcomes are reported as recall.

## Failure behaviour

| Situation | Behaviour |
|-----------|-----------|
| `oguard.yaml` missing | hooks do nothing; `oguard` uses defaults |
| package not installed but config present | the blocking hook still enforces `sealed_paths` and `blocked_sources` (stdlib only); logging is skipped |
| ledger line edited or removed | `verify_chain` reports it; `oguard check` exits 1 |
| Stop hook finds critical findings | blocks once with the findings, then lets the agent finish so it can report them |
