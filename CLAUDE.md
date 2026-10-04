# CLAUDE.md

@AGENTS.md

## Claude Code specifics

- Hooks are configured in `.claude/settings.json` and implemented in `hooks/claude/guard.py`:
  - **PreToolUse** blocks reads, greps, shell commands and fetches that touch sealed paths or blocked
    sources (exit code 2, with the reason). If a call is blocked, do not try another route to the same
    data. Tell the user what you needed and why.
  - **PostToolUse** logs web fetches, searches, file reads and MCP calls to `.oguard/ledger.jsonl`.
  - **Stop** refuses to finish while the information graph has critical findings. It lets you go on the
    second attempt, so explain the findings to the user instead of hiding them.
- Skills live in `.claude/skills/`. Load the matching skill before starting a prediction, an audit, a split,
  a negative control, a proof check or a theory review.
- Everything you retrieve in a session counts as an ancestor of later predictions (`context_is_ancestor`).
  If a prediction must be independent of earlier reading, make it in a fresh subagent that receives only the
  registered inputs, and log it with `--meta context=isolated`.
