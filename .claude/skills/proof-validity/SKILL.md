---
name: proof-validity
description: Check a mathematical proof, derivation or formal argument for circularity, smuggled assumptions, unjustified steps and backward reasoning. Use when writing, reviewing or machine-checking proofs, including Lean 4 developments.
---

# Proof validity

A circular proof establishes `Mod(A ∪ {T}) ⊆ Mod(T)`, which is true of every statement `T`. It rules out
no possible world, so it proves nothing. This skill makes the structure of an argument explicit so that
circularity becomes a graph property you can check.

## 1. Write the dependency graph
One YAML file per proof (see `examples/proofs/`):
```yaml
title: "..."
goal: main
statements:
  - id: main
    kind: goal            # axiom | definition | assumption | cited | lemma | step | goal
    claim: "..."
    uses: [lemma1, lemma2]
  - id: lemma1
    kind: lemma
    uses: [ax1]
  - id: ax1
    kind: axiom
equivalent:               # statements known to be equivalent to the goal, given the axioms
  - [main, some_reformulation]
```
Rules of thumb:
- Every step lists **all** the statements it relies on, including "obvious" facts. Hidden premises are
  where equivalents of the goal hide (Wallis assumed similar triangles; Legendre assumed angle-sum facts).
- Facts proved elsewhere are `cited` with a reference. Do not cite a source that itself relies on the goal.
- A statement obtained by assuming the goal gets `derived_from_goal: true`. It may support the goal only if
  every step was an equivalence (`reversible: true`). Squaring, multiplying by zero, taking absolute values
  and dropping cases are not reversible.

## 2. Check it
```bash
oguard proof proof.yaml
```
| Code | Meaning |
|------|---------|
| P1 | cycle: a statement depends on itself |
| P2 | the goal, or a declared equivalent, is an ancestor of the goal |
| P3 | a non-root step has no support |
| P4 | a consequence of the goal is used to conclude the goal (affirming the consequent) |
| P5 | `uses` names a statement that does not exist |
| P6 | the result is conditional on declared assumptions (informational) |

## 3. Formal proofs (Lean 4)
In the Lean project:
```lean
#print axioms MyNamespace.my_theorem
```
Save the output and run `oguard lean-axioms output.txt`. `sorryAx` means an unproved step (L1); an axiom
named like the theorem means it was assumed (L2); any non-standard axiom must be reviewed (L3). In Python,
`ouroboros_guard.lean.run_print_axioms(project_dir, module, theorems)` runs this for you when Lean is installed.

## 4. What a pass means
Structurally valid = acyclic, grounded in declared roots, no goal smuggling. Each step's correctness is a
separate question: check it in a proof assistant, or by an independent reader who did not write the proof.
State the roots the result rests on (axioms, cited theorems, assumptions) in plain words.
