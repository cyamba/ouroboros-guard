# Principles

Load this file into an agent's context when it works on prediction, evaluation or proof.

## The one rule
The outcome must never be an ancestor of the prediction, and every check you report must have been able to fail.

## Why
A test is worth exactly as much as its ability to fail. Bayes' rule in odds form:

    posterior odds = K × prior odds,   K = P(pass | H) / P(pass | not H),   evidence = log2 K bits

A circular check passes whatever the truth, so P(pass | not H) = 1, K = 1, and it carries zero bits.
Leakage in prediction and circularity in proof are the same failure: the conclusion is among its own causes.

## Seven defences
1. **Draw the information graph and check it in code.** Every input, document and tool result gets a timestamp
   and a source. `Y ∉ Anc(Ŷ)`.
2. **Put a time firewall around the agent.** Every tool and data snapshot respects the prediction time.
3. **Commit, then reveal.** Publish a hash of the prediction before the outcome exists.
4. **Run negative controls through the whole pipeline.** Scrambled labels must give chance; masked identities and
   a training-cut-off split expose memorisation.
5. **Separate the generator from the judge.** A check is informative only if it can disagree.
6. **Budget your looks.** Iterate on a development set; touch the test set once.
7. **Respect the ceiling.** A score above the measurement's own reproducibility is a leak until proven otherwise.

## Three things that are not evidence
- Agreement with what was already known (consistency is not confirmation).
- A consequence derived from the claim that turned out true (affirming the consequent).
- The same result reported many times (citation echo).

## Where an evaluation sits
lookup → recall → near-neighbour → interpolation → prospective prediction.
The same score means copying at one end and new knowledge at the other. Always say which.
