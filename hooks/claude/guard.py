#!/usr/bin/env python3
"""ouroboros-guard hook for Claude Code (and any agent runner that speaks the same JSON-on-stdin protocol).

    guard.py pre    PreToolUse : block reads of sealed paths and fetches from blocked sources (exit 2)
    guard.py post   PostToolUse: log tool calls and retrievals to the provenance ledger
    guard.py stop   Stop       : refuse to finish while the information graph has critical findings

The blocking path uses only the standard library, so a missing install can never silently
open the vault. Logging and the stop check use the ouroboros_guard package when available.

Hooks are a seatbelt, not a vault. The strongest protection is to keep outcomes and holdout
labels outside the agent's filesystem and network reach altogether (see docs/THREAT_MODEL.md).
"""
from __future__ import annotations

import fnmatch
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()).resolve()
_REPO_SRC = Path(__file__).resolve().parents[2] / "src"
if _REPO_SRC.is_dir():
    sys.path.insert(0, str(_REPO_SRC))

PATH_KEYS = ("file_path", "path", "notebook_path")
CONFIG_NAMES = ("oguard.yaml", "oguard.yml", ".oguard.yaml")


# ---------------------------------------------------------------- config (stdlib fallback)
def _read_list(text: str, key: str) -> list:
    """Minimal YAML list reader for `key:` followed by `- item` lines, or `key: [a, b]`."""
    m = re.search(rf"^{key}:\s*\[(.*?)\]\s*$", text, re.M)
    if m:
        return [x.strip().strip("'\"") for x in m.group(1).split(",") if x.strip()]
    out, inside = [], False
    for line in text.splitlines():
        if re.match(rf"^{key}:\s*$", line):
            inside = True
            continue
        if inside:
            m = re.match(r"^\s+-\s+(.*?)\s*$", line)
            if m:
                out.append(m.group(1).strip("'\""))
            elif line.strip() and not line.startswith((" ", "\t", "#")):
                break
    return out


def load_cfg():
    for name in CONFIG_NAMES:
        p = ROOT / name
        if p.is_file():
            try:
                from ouroboros_guard.config import load_config
                return load_config(p)
            except Exception:  # package missing: fall back to the minimal reader
                text = p.read_text()
                return {"sealed_paths": _read_list(text, "sealed_paths"),
                        "blocked_sources": _read_list(text, "blocked_sources"),
                        "ledger": ".oguard/ledger.jsonl", "_root": str(ROOT), "_fallback": True}
    return None


# ---------------------------------------------------------------- matching
def _rel(p: str) -> str:
    path = Path(p)
    if not path.is_absolute():
        path = ROOT / path
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _base(pattern: str) -> str:
    """Literal directory prefix of a glob pattern ('data/holdout/**' -> 'data/holdout')."""
    parts = []
    for part in pattern.split("/"):
        if any(ch in part for ch in "*?["):
            break
        parts.append(part)
    return "/".join(parts)


def sealed_match(path: str, patterns: list) -> str | None:
    rel = _rel(path)
    for pat in patterns:
        base = _base(pat)
        if fnmatch.fnmatch(rel, pat) or (base and (rel == base or rel.startswith(base + "/"))):
            return pat
    return None


def covers_sealed(search_root: str, patterns: list) -> str | None:
    """Would a recursive search rooted here walk into a sealed directory that exists?"""
    root = _rel(search_root or ".")
    root = "" if root == "." else root
    for pat in patterns:
        base = _base(pat)
        if base and (ROOT / base).exists() and (root == "" or base == root or base.startswith(root + "/")):
            return pat
    return None


def deny(reason: str) -> int:
    print(f"[ouroboros-guard] blocked: {reason}", file=sys.stderr)
    return 2


# ---------------------------------------------------------------- hooks
def pre(event: dict) -> int:
    cfg = load_cfg()
    if cfg is None:
        return 0  # project not configured for ouroboros-guard
    sealed = list(cfg.get("sealed_paths") or [])
    blocked = [re.compile(p, re.I) for p in (cfg.get("blocked_sources") or [])]
    tool = event.get("tool_name", "")
    ti = event.get("tool_input") or {}

    for k in PATH_KEYS:
        if ti.get(k):
            hit = sealed_match(str(ti[k]), sealed)
            if hit:
                return deny(f"{ti[k]} is sealed by pattern {hit!r}. It holds outcomes, holdout labels or answers, "
                            f"which a prediction must never see. Work from the inputs that existed at prediction time.")
    if tool in ("Grep", "Glob"):
        pattern = str(ti.get("pattern") or "")
        hit = covers_sealed(str(ti.get("path") or "."), sealed)
        if tool == "Glob" and pattern:
            hit = hit or sealed_match(pattern, sealed)
        if hit and not ti.get("glob"):
            return deny(f"a recursive {tool} from {ti.get('path') or '.'} would walk into the sealed area {hit!r}. "
                        f"Search a narrower path (for example src/ or data/inputs/), or pass a glob that excludes it.")
    if tool == "Bash":
        cmd = str(ti.get("command") or "")
        for pat in sealed:
            base = _base(pat)
            if base and base in cmd:
                return deny(f"the command mentions the sealed path {base!r}. Agents may not read, copy or list it.")
    if tool in ("WebFetch",):
        url = str(ti.get("url") or "")
        for rx in blocked:
            if rx.search(url):
                return deny(f"{url} matches the blocked source pattern {rx.pattern!r}, which publishes the outcomes "
                            f"being predicted.")
    return 0


def post(event: dict) -> int:
    cfg = load_cfg()
    if cfg is None or cfg.get("_fallback"):
        return 0
    try:
        from ouroboros_guard.config import resolve
        from ouroboros_guard.ledger import Ledger
    except Exception:
        return 0
    tool = event.get("tool_name", "")
    ti = event.get("tool_input") or {}
    led = Ledger(resolve(cfg, cfg["ledger"]))
    session = event.get("session_id")
    if tool in ("WebFetch", "WebSearch"):
        src = ti.get("url") or ("search: " + str(ti.get("query", "")))
        led.append("retrieval", source=str(src)[:500],
                   meta={"tool": tool, "session": session, "note": "date unknown; add one with oguard log if it matters"})
    elif tool.startswith("mcp__") or tool in ("Read", "Bash", "Grep", "Glob", "NotebookRead"):
        summary = ti.get("file_path") or ti.get("path") or ti.get("command") or ti.get("pattern") or ""
        led.append("tool_call", source=f"{tool}: {str(summary)[:300]}", meta={"tool": tool, "session": session})
    return 0


def stop(event: dict) -> int:
    if event.get("stop_hook_active"):
        return 0  # never loop: the agent already had one chance to respond
    cfg = load_cfg()
    if cfg is None or cfg.get("_fallback"):
        return 0
    try:
        from ouroboros_guard.config import resolve
        from ouroboros_guard.graph import InfoGraph
        from ouroboros_guard.ledger import Ledger
    except Exception:
        return 0
    led = Ledger(resolve(cfg, cfg["ledger"]))
    if not led.path.exists():
        return 0
    problems = led.verify_chain()
    g = InfoGraph(led.read(), context_is_ancestor=cfg.get("context_is_ancestor", True))
    crit = [f for f in g.check_all(default_as_of=cfg.get("as_of"), missing_date_policy=cfg["missing_date_policy"],
                                   look_budget=cfg["budget"].get("test_looks"))
            if f.severity == "critical"]
    if problems or crit:
        lines = problems + [f"{f.code}: {f.message}" for f in crit[:8]]
        print("[ouroboros-guard] the information graph has critical findings. Do not report these results as "
              "predictions until they are fixed or explicitly disclosed:\n- " + "\n- ".join(lines), file=sys.stderr)
        return 2
    return 0


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "pre"
    raw = sys.stdin.read()
    try:
        event = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        return 0
    return {"pre": pre, "post": post, "stop": stop}.get(mode, pre)(event)


if __name__ == "__main__":
    sys.exit(main())
