# Rule catalogue

Every check in ouroboros-guard has a code. Agents and humans can cite these codes in reviews and commits.
Severity: **critical** blocks reporting results as predictions; **warn** must be disclosed; **info** is advice.

## Information graph (`oguard check`)

| Code | Severity | Rule | Why |
|------|----------|------|-----|
| G0 | warn | Every parent named by an event must be in the ledger. | Unknown provenance cannot be shown to be clean. |
| G1 | critical | The outcome being predicted must not be an ancestor of the prediction. | `Y ∈ Anc(Ŷ)` means the prediction saw its answer. |
| G2 | warn / critical | Retrievals and inputs that feed a prediction need an availability date (`missing_date_policy`). | An undated document may postdate the outcome. |
| G3 | critical | No ancestor may be dated at or after the prediction time. | Information from the future. |
| G4 | warn / critical | Dates that straddle the prediction time ("2024" vs 2024-06-01) are ambiguous. | Partial dates are intervals, not instants. |
| G5 | warn | A prediction whose outcome is in the ledger should have been committed. | Without a commitment nothing proves it came first. |
| G6 | critical | A prediction must be committed before its outcome is recorded. | Otherwise it may have been written with the answer in view. |
| G7 | critical | The information graph must be acyclic. | A cycle is circular reasoning. |
| G8 | warn / critical | Looks at an evaluation set must stay within `budget.test_looks` (critical above 3x). | Each look leaks up to log2(#answers) bits about the labels. |
| G9 | warn | A judge must not be the model that produced what it judges. | Shared blind spots look like agreement. |
| G10 | info | Several retrieved sources with the same `origin` count as one piece of evidence. | Citation echo inflates confidence. |

## Proofs (`oguard proof`)

| Code | Severity | Rule |
|------|----------|------|
| P0 | critical | The goal must be one of the statements. |
| P1 | critical | No statement may depend on itself, directly or through others. |
| P2 | critical | The goal, and anything declared equivalent to it, must not be an ancestor of the goal. |
| P3 | critical | Every non-root step needs support (`uses`); roots are axioms, definitions, assumptions and cited results. |
| P4 | critical | A statement derived from the goal may not establish the goal unless every step is reversible. |
| P5 | critical | `uses` may only name existing statements. |
| P6 | info | Results that rest on declared assumptions are conditional, and must be reported as such. |

## Formal proofs (`oguard lean-axioms`)

| Code | Severity | Rule |
|------|----------|------|
| L1 | critical | No dependency on `sorryAx`. |
| L2 | critical | No axiom named like the theorem it supports. |
| L3 | warn | Non-standard axioms (other than `propext`, `Classical.choice`, `Quot.sound`) must be reviewed. |

## Statistical controls

| Check | Fails when |
|-------|-----------|
| Negative control (`oguard control`, `permutation_control`) | the mean score on scrambled labels exceeds chance + tolerance |
| Split audit (`oguard split-audit`) | more than `max_fraction_above` of test items have a near-duplicate in training |
| Replicate ceiling (`oguard ceiling --claimed`) | the reported score exceeds what the measurement's own reproducibility allows |
| Evidence weight (`oguard evidence`) | a cited check has P(pass \| not H) near 1, so it carries about 0 bits |
| Temporal gap (`temporal_gap`) | accuracy on outcomes public before the model's training cut-off clearly exceeds accuracy after it |

## Agent invariants (AGENTS.md)

I1 sealed paths, I2 time firewall, I3 blocked sources, I4 commit before reveal, I5 test budget, I6 independent
judges, I7 count echoes once, I8 fixed outcome definitions, I9 proof hygiene, I10 honest reporting.
