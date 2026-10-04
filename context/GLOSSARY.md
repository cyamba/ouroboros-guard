# Glossary

**Ancestor** — node A is an ancestor of B in the information graph if information can flow from A to B along
recorded edges (A was used, directly or indirectly, to produce B). `Anc(B)` is the set of all ancestors.

**As-of time (`as_of`)** — the prediction time. Every input must have existed before it.

**Blocked source** — a site, registry, database or file that publishes the outcomes being predicted.

**Citation echo** — one result reported by many documents (paper, preprint, review, press release, database
entry) and counted as many independent confirmations.

**Commit-reveal** — publish `c = SHA-256(prediction ‖ salt)` before the outcome exists; reveal prediction and
salt afterwards so anyone can check `c`. Hiding (c reveals nothing) and binding (c cannot be reopened to a
different prediction).

**Context-is-ancestor** — for LLM agents, everything retrieved or run earlier in a session may influence a
later prediction, so it is treated as an ancestor unless the prediction was made in an isolated context.

**Double dipping** — using the same data to choose what to test and to test it.

**Double counting** — letting the same data into an inference twice (for example in the prior and the
likelihood), which makes intervals too narrow.

**Evidence weight** — `log2 K` bits, where `K = P(pass | H) / P(pass | not H)` is the Bayes factor of a check.

**Information graph** — the directed graph of everything that can influence a prediction, built from the
ledger. Sound reasoning is acyclic; leakage is an edge from the outcome into the prediction's ancestry.

**Leakage** — any path by which information about the outcome reaches the prediction other than through the
legitimate inputs. Formally `I(Ŷ; Y | X) > 0`.

**Ledger** — the append-only, hash-chained JSON-lines file of events (`.oguard/ledger.jsonl`).

**Look** — scoring anything against an evaluation set. Each look can leak information about its labels.

**Negative control** — running the whole pipeline where there is nothing to find (scrambled labels, masked
identities) to show it falls to chance.

**Replicate ceiling** — the best score any honest model can reach against a single noisy measurement, set by
how well two runs of the same experiment agree.

**Sealed path** — a location holding outcomes, holdout labels or answer keys that agents must never read.

**Temporal gap** — the difference in accuracy between outcomes made public before and after a model's
training cut-off; a large positive gap indicates memorisation.
