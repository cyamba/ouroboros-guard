---
name: time-firewall
description: Give an agent search, retrieval (RAG), web or database tools without letting future information or published outcomes in. Use whenever tools could return documents written after the prediction time.
---

# Time firewall

Every tool that returns documents gets an **as-of date**. Nothing dated at or after it gets through.

## Dates are intervals
"2024" means [2024-01-01, 2025-01-01). Against a cut-off of 2024-06-01 it is *ambiguous*, not "before".
`missing_date_policy` decides what happens to undated and ambiguous items:
- `reject` for prospective evaluations and anything you will publish;
- `warn` while exploring (the ledger records them; `oguard check` reports them);
- `allow` only for material that cannot carry the outcome (textbooks, axioms, code documentation).

## Wiring it in
Python:
```python
from ouroboros_guard import TimeFirewall, Ledger
fw = TimeFirewall("2026-03-01", missing_date_policy="reject",
                  blocked_sources=[r"results-registry\.example", r"doi\.org/10\.9999/"],
                  ledger=Ledger(".oguard/ledger.jsonl"))
search = fw.wrap(search)
```
Any language: write results as JSON lines with a `published_at` (or `date`, `year`) field and pipe them through
`oguard firewall - --as-of 2026-03-01 --policy reject --log`.

Claude Code: list outcome sources under `blocked_sources` in `oguard.yaml`; the PreToolUse hook blocks
`WebFetch` to them, and the PostToolUse hook logs every fetch and search.

## What the firewall cannot do
- It cannot see what a language model memorised in training. Use the `negative-controls` skill
  (temporal gap and memorisation probe) for that.
- It trusts the dates it is given. Prefer the date the information first became public (preprint, registry
  entry, press release) over the date of the version you retrieved.
- Search engines return later documents that *cite* the result. Block by origin as well as by date when the
  outcome's own identifiers are known.
