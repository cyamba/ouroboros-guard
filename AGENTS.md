# AGENTS.md

Operating contract for any AI agent (Claude Code, Codex, Cursor, Gemini, Copilot, or your own harness)
working in a project that uses **ouroboros-guard**. Humans should read it too: it is the shortest
description of what "an honest prediction" means here.

## The one rule

> The outcome must never be an ancestor of the prediction, and every check you report must have been able to fail.

Formally: `Y ∉ Anc(Ŷ)`, and every node in `Anc(Ŷ)` existed before `Ŷ` was fixed. A check whose pass
rate does not depend on whether the claim is true carries zero bits of evidence. See `docs/MATH.md`.

## Invariants (never break these)

| ID | Invariant | Enforced by |
|----|-----------|-------------|
| I1 | Never read, list, copy, grep or summarise a **sealed path** (outcomes, holdout labels, answer keys). | `hooks/claude/guard.py pre`, `sealed_paths` |
| I2 | Never use information dated at or after the prediction time `as_of`. Undated information is suspect, not neutral. | `TimeFirewall`, `oguard check` (G2, G3, G4) |
| I3 | Never fetch from a **blocked source** (a site, database or registry that publishes the outcomes). | `blocked_sources`, `guard.py pre` |
| I4 | Commit every prediction (`oguard commit`) **before** its outcome exists or is revealed. Never edit a committed file. | `oguard commit/verify`, git pre-commit (G6) |
| I5 | Do not score against the final test set more than the budget allows. Iterate on a development set. | `HoldoutGuard`, `look` events (G8) |
| I6 | Do not grade your own output with the same model, or with any judge that saw the same information. | `judge` events (G9) |
| I7 | Count repeated reports of one result (paper, press release, review, database entry) as **one** piece of evidence. | `origin` on retrievals (G10) |
| I8 | Define outcomes before modelling and independently of the inputs. Never redefine a label after seeing results. | human review; `docs/THREAT_MODEL.md` L7 |
| I9 | In proofs: no statement may depend on the goal or on anything declared equivalent to it; never conclude a premise from a true consequence unless every step is reversible. | `oguard proof` (P1–P5), `oguard lean-axioms` |
| I10 | Report results with their position on the leakage spectrum, their evidence weight, and the measurement ceiling. Never present recall as prediction. | `oguard audit`, reporting rules below |

If you cannot satisfy an invariant, **stop and say so**. Do not work around a blocked hook, do not move a
sealed file, do not change `as_of` to make a finding disappear. Report the finding to the human.

## Workflow for a prediction or evaluation

1. **Register** every input with its availability date:
   `oguard log input --id input:<name> --available-at <date> --file <path>`
2. **Retrieve** only through the time firewall (`TimeFirewall(as_of).wrap(search)` in Python, or
   `oguard firewall docs.jsonl --as-of <date> --log`). Record `origin` (the original study) on each document.
3. **Derive** features, summaries and models; log them with `--parent` links:
   `oguard log derive --id derive:<name> --parent input:<name>`
4. **Predict**, listing what the prediction used:
   `oguard log prediction --id prediction:<target> --target <target> --parent derive:<name> --meta as_of=<date> --meta model=<model-id>`
5. **Commit** before any outcome exists: `oguard commit predictions.jsonl --prediction prediction:<target>`.
   Publish the `.commit.json`; keep the `.salt` private (it is git-ignored).
6. **Control**: run the whole pipeline on scrambled labels (`oguard control --cmd "... {labels}" --labels y.csv`)
   and, for literature-reading agents, with masked identities and a pre/post training-cut-off split.
7. **Reveal and score** once: log the outcome (`oguard log outcome --target <target>`), verify the commitment
   (`oguard verify predictions.jsonl`), score through `HoldoutGuard`.
8. **Audit**: `oguard audit --format md --out AUDIT.md`. Every `fail` must be fixed or disclosed.

## Workflow for a proof or derivation

1. Write the argument as a dependency graph (`examples/proofs/*.yaml`): every statement has an `id`,
   a `kind` (`axiom | definition | assumption | cited | lemma | step | goal`) and `uses`.
2. Declare known equivalences of the goal under `equivalent:` (for example the parallel postulate and
   "the angles of every triangle sum to 180°"). Smuggling an equivalent is the most common circular proof.
3. Mark statements obtained by assuming the goal with `derived_from_goal: true`; set `reversible: true`
   only when every step is an equivalence.
4. Run `oguard proof proof.yaml`. For Lean 4, run `#print axioms` and `oguard lean-axioms output.txt`.
5. A proof that passes is *structurally* sound: acyclic, grounded and goal-free. It is not thereby correct.
   Each step still needs checking, ideally by a proof assistant.

## Reporting rules

- State where the evaluation sits on the **leakage spectrum**: lookup, recall, near-neighbour,
  interpolation, prospective. "92% on outcomes published before the model's training cut-off" and
  "92% on experiments run after the predictions were committed" are different claims.
- Give the **weight of evidence** of every validation you cite (`oguard evidence --p-pass-h --p-pass-not-h`).
  A check that would pass whatever the truth (`P(pass | not H) ≈ 1`) is worth zero bits; say so.
- Compare scores with the **replicate ceiling** (`oguard ceiling`). A score above it is a leak until proven otherwise.
- Never write "validated", "confirmed" or "consistent with" for a check that could not have failed.

## Commands

```bash
pip install -e .            # or: pip install git+https://github.com/cyamba/ouroboros-guard
oguard init                 # writes oguard.yaml and .oguard/
oguard check                # information-graph checks (exit 1 on critical findings)
oguard audit --format md    # the ten-question audit
oguard proof FILE.yaml      # proof dependency graph
python -m pytest            # this repository's own tests
```

## Where things live

| Path | What |
|------|------|
| `src/ouroboros_guard/` | the library and the `oguard` CLI |
| `.claude/skills/*/SKILL.md` | task playbooks (any agent can read them as plain Markdown) |
| `.claude/settings.json`, `hooks/claude/guard.py` | Claude Code hooks: block sealed reads, log retrievals, stop on critical findings |
| `hooks/git/pre-commit` | refuses salts, broken graphs and edited committed predictions |
| `rules/` | the invariants as a rule catalogue, plus ready-made policy packs |
| `context/` | glossary, principles and the audit questions, for loading into an agent's context |
| `docs/` | implementation plan, architecture, math, threat model, proofs, integrations |

## Skills

| Skill | Use it when |
|-------|-------------|
| `prediction-protocol` | making any prediction whose accuracy will be reported |
| `leakage-audit` | reviewing a pipeline, a paper's claims or your own results for leakage |
| `time-firewall` | giving an agent search, RAG or database tools in a prediction setting |
| `negative-controls` | proving that a pipeline cannot score well on noise |
| `split-audit` | building or checking train/test splits |
| `proof-validity` | checking a mathematical proof or derivation for circularity |
| `theory-review` | judging how much evidence really supports a theory or claim |

## Repository conventions

- Python ≥ 3.10, dependencies limited to `numpy` and `pyyaml`. Keep it that way for the core.
- Every new check gets: a finding code (`Gn`, `Pn`, `Ln`), a test that shows it firing and one that shows it silent,
  and a line in `rules/INVARIANTS.md`.
- Messages say what happened, why it matters and what to do, in plain words.
