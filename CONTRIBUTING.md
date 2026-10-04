# Contributing

Thank you for helping make predictions and proofs more trustworthy.

## Setup
```bash
pip install -e ".[dev]"
python -m pytest
```

## Adding a check
1. Give it a code (`G`, `P`, `L` series, or propose a new letter) and a severity.
2. Write the finding message in plain words: what happened, why it matters, what to do.
3. Add a test that shows the check firing on a constructed leak and one that shows it silent on a clean case.
4. Add a row to `rules/INVARIANTS.md`, and to `docs/THREAT_MODEL.md` if it covers a new channel.

## Adding to the leak zoo
The most useful contribution is a small, self-contained pipeline that leaks in a way the current checks
miss, placed under `examples/` with a test. Real leaks found in published work (described generically,
with a citation) are especially welcome.

## Principles
- The core depends only on `numpy` and `pyyaml`.
- Conservative defaults: when in doubt, report rather than pass.
- Never weaken a check to make a test pass; fix the test or document the limitation.
