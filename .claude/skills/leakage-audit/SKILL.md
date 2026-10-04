---
name: leakage-audit
description: Audit a pipeline, an agent run, a benchmark result or a paper's claims for leakage and circular evaluation. Use when someone reports a surprisingly good score, before publishing results, or when reviewing someone else's evaluation.
---

# Leakage audit

You are looking for any path by which the answer reached the prediction, and for any check that could
not have failed. Assume nothing is malicious; leaks are usually ordinary tools doing ordinary things.

## Run what can be run
```bash
oguard check                     # information graph: G1 outcome ancestor ... G10 citation echo
oguard audit --format md         # the ten questions, answered from evidence on disk
```

## Walk the seven channels (docs/THREAT_MODEL.md)
For each, write one line: *not applicable*, *checked and clean* (say how) or *leak found* (say where).

| # | Channel | Question to answer | Tool |
|---|---------|--------------------|------|
| L1 | Memorised answers | Were outcomes public before the model's training cut-off? | `temporal_gap`, `memorisation_probe` |
| L2 | Retrieved answers | Could search, RAG or a database return the outcome? | `TimeFirewall`, ledger retrievals |
| L3 | Proxy features | Does any input exist only because of the outcome? | column-by-column review |
| L4 | Near-duplicate splits | Is each test item near a training item? | `oguard split-audit` |
| L5 | Test-set steering | How many times was the test score looked at? | `look` events, `HoldoutGuard` |
| L6 | Self-grading | Is the judge the generator, or does it share its information? | `judge` events |
| L7 | Definitional loops | Is the label defined from an input? | read the outcome definition |

Add for statistics work: double dipping (selection and testing on the same data), double counting
(the same data in the prior and the likelihood), citation echo (one result reported many times).

## Quantitative sanity checks
- **Ceiling**: `oguard ceiling --agreement <replicate agreement> --claimed <score>`.
- **Negative control**: the pipeline on scrambled labels must fall to chance (`negative-controls` skill).
- **Search size**: if k hypotheses were tried on n samples, the best null correlation is about
  `sqrt(2 ln k / n)`. A reported effect near that size is not evidence.

## Output
A short report: verdict per channel, the audit table, the three most serious findings with the evidence
for each, and what would change the verdict. Mark every claim you could not verify as *unverified*.
