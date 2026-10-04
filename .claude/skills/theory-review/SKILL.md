---
name: theory-review
description: Judge how much evidence really supports a scientific theory, model, hypothesis or engineering claim, and where its support is circular. Use when evaluating a theory's validity, a model's claimed validation, or an agent's "confirmed" hypothesis.
---

# Theory review

A theory earns credibility only from observations that could have refuted it. For each piece of support,
ask how likely it was to be observed **if the theory were false**.

## 1. Map the claim
- State the theory in one sentence, and list its testable consequences.
- Draw the support graph: which observations, derivations and assumptions support which claims.
  Use the proof format (`proof-validity` skill) for the derivational part.
- Mark every definition that uses the theory's own terms. A definition that builds in the conclusion
  (for example, defining the class of "responders" by the marker the theory says predicts response) makes
  every later confirmation circular.

## 2. Weigh each piece of evidence
For each observation `E` estimate `P(E | theory)` and `P(E | not theory)`:
```bash
oguard evidence --p-pass-h 0.9 --p-pass-not-h 0.6 --prior 0.3
```
| Weight | Meaning |
|--------|---------|
| about 0 bits | consistent but uninformative: it would have happened anyway (accommodation, not prediction) |
| under 1 bit | weak support |
| several bits | a genuine test the theory could have failed |

Down-weight or remove:
- results the theory was fitted to (they were explained, not predicted);
- several reports of one experiment (count once);
- checks run by the people or the model that produced the claim, with no independent information;
- tests whose analysis choices were made after seeing the data (the garden of forking paths).

## 3. Look for the riskiest prediction
Name the observation that would most embarrass the theory if it turned out otherwise. If none exists, the
theory is not yet testable. If one exists and has not been tested, that is the most valuable next experiment.
Pre-register it with the `prediction-protocol` skill.

## 4. Check the ceiling
If the theory's fit to data exceeds what replicate measurements agree with each other
(`oguard ceiling`), it is fitting noise or leaking.

## Output
- Verdict: well supported, partly supported, unsupported, or circular, with the bits of evidence behind it.
- The two or three load-bearing observations and whether each could have failed.
- Circular or self-confirming links, if any.
- The single most informative next test.
