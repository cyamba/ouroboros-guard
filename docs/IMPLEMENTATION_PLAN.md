# Implementation plan: keeping leakage out of agentic science, math and engineering

This plan describes how ouroboros-guard makes it hard for leakage and circular reasoning to creep into
systems that predict outcomes, evaluate theories or prove theorems, and how it makes whatever does creep in
visible. Status markers: **[done]** shipped in v0.1, **[next]** planned.

## 1. What "no leakage" can and cannot mean

No software can *guarantee* that a language model never saw an answer, or that a human never typed a
spoiler into a prompt. What a system can do is:

1. **Prevent** the common paths (sealed data, time-firewalled tools, blocked sources).
2. **Record** every path information takes (a hash-chained provenance ledger).
3. **Verify** the recorded paths and the statistics (graph checks, negative controls, split audits, ceilings).
4. **Commit** predictions so their timing can be proved (commit-reveal).
5. **Disclose** what could not be verified (the audit's "unknown" answers).

The design goal is that a leak must defeat several independent layers, and that a result which skipped a
layer says so in its report.

## 2. Design principles

- **The one rule is checkable.** `Y ∉ Anc(Ŷ)` is a graph property. Everything the system records is a node
  or an edge in that graph.
- **Conservative by default.** Partial dates are intervals; undated information is suspect; an agent's whole
  context window counts as an ancestor of its predictions.
- **Fail closed on sealed data.** The blocking hook needs only the Python standard library, so a broken
  install cannot silently open the vault.
- **Evidence on disk, not in memory.** The ledger, control results, split reports and commitments are files
  that can be committed, reviewed and audited by someone else.
- **Tool-agnostic.** A CLI, a Python API, JSON-lines and YAML. Agent integrations are thin layers on top.
- **Plain findings.** Each finding has a code, a severity, what happened, why it matters and what to do.

## 3. Layers and components

| Layer | Component | Status |
|-------|-----------|--------|
| Prevent | physical separation of outcomes (separate machine, store or service) | documented; **[next]** sealed evaluator service |
| Prevent | `sealed_paths` + Claude Code PreToolUse hook | **[done]** |
| Prevent | `TimeFirewall` for retrieval tools; `blocked_sources` | **[done]** |
| Record | hash-chained ledger (`oguard log`, hooks, firewall) | **[done]** |
| Verify | information-graph checks G0–G10 (`oguard check`) | **[done]** |
| Verify | negative controls: permutation, command-level, masking, temporal gap | **[done]** |
| Verify | split audit (n-gram Jaccard, cosine, Tanimoto, exact), group and time splits | **[done]** |
| Verify | replicate ceilings (binary, continuous) and evidence weight | **[done]** |
| Verify | test-set budget (`HoldoutGuard`, strict and Thresholdout) | **[done]** |
| Verify | proof graphs P0–P6, Lean `#print axioms` audit L1–L3 | **[done]** |
| Verify | memorisation probe | **[done]** (model call supplied by the user) |
| Commit | commit-reveal of prediction files | **[done]**; **[next]** public timestamping |
| Disclose | the ten-question audit (text, Markdown, JSON) | **[done]**; **[next]** badge and results schema |

## 4. Phases

### Phase 0: threat model and invariants [done]
- Deliverables: `docs/THREAT_MODEL.md`, `rules/INVARIANTS.md`, `AGENTS.md`.
- Acceptance: every leak channel in the threat model maps to at least one check or one explicit limitation.

### Phase 1: provenance core [done]
- Deliverables: `timeutil` (interval dates), `ledger` (hash chain), `graph` (ancestry, cycles, timing,
  commits, looks, judges, echoes), `firewall`, `commit`.
- Acceptance: tests show G1, G3, G6, G7, G8, G9 firing on constructed leaks and silent on clean ledgers;
  editing any ledger line is detected.

### Phase 2: statistical controls [done]
- Deliverables: `controls`, `splits`, `budget`, `ceiling`, `evidence`.
- Acceptance: the feature-selection leak (selection before cross-validation on pure noise) is flagged; the
  honest pipeline is not; the binary ceiling matches a Monte Carlo simulation within 0.005.

### Phase 3: agent integration [done], MCP server [next]
- Done: `AGENTS.md`, `CLAUDE.md`, seven skills, Claude Code hooks (pre, post, stop), Cursor rule, git pre-commit.
- Next: an **MCP server** that exposes firewalled search and retrieval tools (and nothing else) to any
  MCP-capable agent, logging every call to the ledger. This removes the need to trust the agent's own tools.
- Acceptance (next): an agent with only the MCP tools cannot fetch a document dated after `as_of` in a
  red-team test suite.

### Phase 4: proofs [done basic], richer extraction [next]
- Done: YAML/JSON proof graphs with equivalence declarations and backward-reasoning marks; Lean axiom audit.
- Next: extract the dependency graph of a Lean declaration automatically (constants used by its proof term);
  adapters for Isabelle and Coq; an LLM-assisted extractor that turns an informal proof into a draft graph
  that a human confirms.
- Acceptance (next): known circular formalisations in a test corpus are flagged without hand-written YAML.

### Phase 5: contamination [done basic], benchmark harness [next]
- Done: `temporal_gap`, `memorisation_probe`, `ngram_overlap`.
- Next: canary strings for private benchmarks; a harness that runs the probe across model versions; a
  standard pre/post-cut-off report.

### Phase 6: sealed evaluator service [next]
- A separate process (or machine) holds outcomes. Agents submit committed prediction files; the service
  verifies the commitment, scores through `HoldoutGuard`, logs the look and returns only the score.
- Public timestamping of commitments (signed git tags, OpenTimestamps or RFC 3161) so third parties can
  verify timing without trusting the author.
- Acceptance: an end-to-end prospective study where nobody on the predicting side can read outcomes.

### Phase 7: the leak zoo [next]
- A regression suite of deliberately leaky pipelines (preprocessing on all data, target encoding before the
  split, near-duplicate splits, test-set hill-climbing, retrieval of the answer, self-grading, label defined
  from an input, citation echo) that every release must catch. `examples/` is the seed.

### Phase 8: reporting [next]
- A JSON schema for results that carries the leakage-spectrum position, evidence weight, ceiling and audit
  status alongside the score; a README badge generated from `oguard audit`.

## 5. Adopting it in a project

| Step | Action | Time |
|------|--------|------|
| 1 | `pip install ouroboros-guard`, `oguard init`, fill in `as_of`, `sealed_paths`, `blocked_sources` (or start from `rules/packs/`) | 15 min |
| 2 | Move outcomes and holdout labels out of the agent's workspace, or under a sealed path | 30 min |
| 3 | Copy `.claude/settings.json` + `hooks/` (Claude Code) or `AGENTS.md` / `.cursor/rules` (other agents) | 10 min |
| 4 | Wrap retrieval tools with `TimeFirewall`; log inputs and predictions | 1–2 h |
| 5 | Add a negative control and a split audit to the evaluation script | 1 h |
| 6 | Commit predictions before outcomes; run `oguard audit` in CI | 30 min |

## 6. Release gates (CI)

Results may be reported as predictions only when:
1. `oguard check` exits 0 (no critical findings) and the ledger chain is intact;
2. the negative control passed, or its absence is disclosed;
3. the split report shows no near-duplicate leakage, or the score is broken down by similarity;
4. every prediction file verifies against its commitment;
5. `oguard audit` has no `fail`, and every `warn` and `unknown` is listed in the report.

## 7. Limitations

- **Memorisation cannot be ruled out**, only measured (temporal gap, probes). Evaluations on outcomes public
  before a model's training cut-off test recall, and the audit says so.
- **Dates can be wrong.** The firewall trusts metadata. Prefer first-publication dates; block by origin too.
- **Hooks can be bypassed** by an agent with unrestricted shell or network access. Physical separation of
  outcomes is the real control; hooks and the ledger are seatbelts and evidence.
- **Recorded edges are only as complete as the logging.** `context_is_ancestor` closes the biggest gap for LLM
  agents; explicit `--parent` links do the rest.
- **A structurally valid proof is not a correct proof.** The proof checks find circularity and gaps in the
  structure; step-level correctness needs a proof assistant or an independent reader.
- **Outcome definitions are a human responsibility.** Software cannot tell that a label was defined from an
  input; the prediction card and review must.
