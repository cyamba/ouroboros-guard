# Proof graph format

A proof is checked as a dependency graph. YAML or JSON:

```yaml
title: string                 # free text
goal: <id>                    # the statement being proved
statements:
  - id: <id>                  # unique
    kind: goal | lemma | step | corollary | axiom | definition | assumption | cited
    claim: string             # the mathematical statement, any notation
    uses: [<id>, ...]         # every statement this one relies on
    citation: string          # for kind: cited
    derived_from_goal: bool   # obtained by assuming the goal (default false)
    reversible: bool          # every step in that derivation is an equivalence (default false)
equivalent:                   # groups of statements known to be equivalent, given the axioms
  - [<id>, <id>, ...]
```

**Roots** are `axiom`, `definition`, `assumption` and `cited`. Every other statement needs `uses`.

## Checks

| Code | Finds |
|------|-------|
| P0 | the goal is missing |
| P1 | a cycle: some statement depends on itself |
| P2 | the goal, or a statement declared equivalent to it, is an ancestor of the goal |
| P3 | a non-root statement without support |
| P4 | a statement derived from the goal, through non-reversible steps, is used to establish the goal |
| P5 | a reference to a statement that does not exist |
| P6 | the result rests on declared assumptions (informational) |

The report also lists the axioms, definitions, cited results and assumptions the goal rests on, the
statements that are never used, and the depth of the longest chain.

## Writing good graphs

- **Name hidden premises.** Most circular proofs in history hid the goal inside an "obvious" premise:
  similar triangles of any size exist (Wallis), the angle sum of a triangle is 180°, a circle passes through
  any three non-collinear points. Write such premises as statements so they can be checked.
- **Declare equivalences you know.** If a premise is known to be equivalent to the goal, P2 needs that
  knowledge. Collect standard equivalences for your field in a shared file and copy them in.
- **Separate definitions.** Whether L'Hôpital's rule is circular for $\lim \sin x / x$ depends on how sine is
  defined (geometrically: circular; by power series: not). The definition is a root; choose it explicitly.
- **Mark backward reasoning.** "Assume the claim, simplify to a true statement" proves the claim only if
  every simplification is reversible. Mark it and let P4 check.

## Examples

| File | Verdict |
|------|---------|
| `examples/proofs/sinx_lhopital.yaml` | invalid: cycle through the derivative of sine (P1, P2) |
| `examples/proofs/sinx_squeeze.yaml` | structurally valid; rests on unit-circle geometry, radian measure, continuity of cos and the squeeze theorem |
| `examples/proofs/parallel_wallis.yaml` | invalid: assumes an equivalent of the parallel postulate (P2) |
| `examples/proofs/minus_one_equals_one.yaml` | invalid: squares both sides, then argues backwards (P1, P4) |
