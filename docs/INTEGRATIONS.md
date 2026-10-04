# Integrations

## Any agent: AGENTS.md
`AGENTS.md` is read by most coding agents (Codex, Cursor, Gemini CLI, Copilot coding agent, Claude Code via
`CLAUDE.md`). Copy it, `context/` and `.claude/skills/` into your project. The skills are plain Markdown, so
agents that do not load skills natively can still be told to read the matching file.

## Claude Code
1. `pip install ouroboros-guard` (or `pip install -e .` in this repository).
2. Copy `.claude/settings.json` and `hooks/claude/guard.py` into your project (keep the path
   `hooks/claude/guard.py`, or edit the command in `settings.json`).
3. `oguard init` and fill in `as_of`, `sealed_paths` and `blocked_sources`.
4. Copy `.claude/skills/` so Claude can load the playbooks, and `CLAUDE.md`.

What the hooks do:

| Event | Behaviour |
|-------|-----------|
| PreToolUse (Read, Edit, Write, Grep, Glob, Bash, WebFetch, ...) | exit 2 with a reason when a path is sealed, a recursive search would enter a sealed directory, a command mentions a sealed path, or a URL matches a blocked source |
| PostToolUse (WebFetch, WebSearch, Read, Bash, Grep, Glob, MCP tools) | append `retrieval` or `tool_call` events to the ledger |
| Stop | exit 2 once if the information graph has critical findings, so the agent addresses or discloses them |

## Cursor
`.cursor/rules/ouroboros-guard.mdc` is an always-applied rule that points the agent at `AGENTS.md`.

## Git
```bash
git config core.hooksPath hooks/git     # or: ln -s ../../hooks/git/pre-commit .git/hooks/pre-commit
```
The pre-commit hook refuses `*.salt` files, ledgers with critical findings, and prediction files that no
longer match their commitments.

## CI (GitHub Actions)
```yaml
- run: pip install ouroboros-guard
- run: oguard check
- run: oguard audit --format md --out AUDIT.md
- uses: actions/upload-artifact@v4
  with: { name: ouroboros-audit, path: AUDIT.md }
```

## Python pipelines and agent frameworks
Wrap the retrieval function your framework calls; log what the model produced.
```python
from ouroboros_guard import Ledger, TimeFirewall
led = Ledger(".oguard/ledger.jsonl")
fw = TimeFirewall("2026-03-01", missing_date_policy="reject", ledger=led)

@fw.wrap
def search(query: str):            # returns [{"title", "url", "published_at", "origin"}, ...]
    return my_search_backend(query)

inp = led.append("input", id="input:table", available_at="2026-01-15", source="data/table.csv")
pred = led.append("prediction", target="E-12", parents=[inp.id], meta={"model": "my-model"})
```

## Notebooks
Log inputs at the top, wrap tools, and end the notebook with `!oguard check && oguard audit`.

## Lean 4
```bash
lake env lean Check.lean > axioms.txt     # Check.lean: `import MyProject` then `#print axioms MyProject.thm`
oguard lean-axioms axioms.txt
```
or `ouroboros_guard.lean.run_print_axioms(project_dir, "MyProject", ["MyProject.thm"])`.

## MCP (planned)
An MCP server exposing only firewalled retrieval tools, logging every call, so any MCP-capable agent gets
the time firewall without trusting its own tool stack. See the implementation plan, phase 3.
