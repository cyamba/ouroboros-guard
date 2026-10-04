"""Proof dependency graphs: is a proof acyclic, grounded and free of smuggled goals?

A proof is a directed acyclic graph from accepted roots (axioms, definitions,
declared assumptions, cited theorems) to the goal. This module checks a proof
written as YAML or JSON (see examples/proofs/) for the failure modes that
turn a proof into a null result:

  P1 cycle                 a statement depends on itself
  P2 goal smuggled         the goal, or a statement declared equivalent to it, is an ancestor of the goal
  P3 unjustified step      a non-root statement with no support
  P4 affirming consequent  a statement derived *from* the goal is used to conclude the goal
  P5 dangling reference    `uses` names a statement that does not exist
  P6 conditional result    the result depends on declared assumptions (reported, not an error)
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Set

import yaml

from .graph import Finding

ROOT_KINDS = {"axiom", "definition", "assumption", "cited"}
STEP_KINDS = {"lemma", "step", "goal", "corollary"}


@dataclass
class ProofReport:
    title: str
    goal: str
    findings: List[Finding] = field(default_factory=list)
    axioms: List[str] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)
    cited: List[str] = field(default_factory=list)
    unused: List[str] = field(default_factory=list)
    depth: int = -1  # -1 when the graph is cyclic, so no longest chain exists

    @property
    def valid(self) -> bool:
        return not any(f.severity == "critical" for f in self.findings)

    def describe(self) -> str:
        lines = [f"Proof: {self.title}  (goal: {self.goal})",
                 f"  verdict: {'structurally valid' if self.valid else 'INVALID'}; "
                 f"depth {self.depth if self.depth >= 0 else 'undefined (cyclic)'}",
                 f"  rests on axioms {self.axioms or '-'}; definitions/cited {self.cited or '-'}"]
        if self.assumptions:
            lines.append(f"  conditional on assumptions {self.assumptions}")
        for f in self.findings:
            lines.append(f"  [{f.severity}] {f.code}: {f.message}")
        if self.unused:
            lines.append(f"  unused statements: {self.unused}")
        return "\n".join(lines)


def load_proof(path: Path) -> Dict[str, Any]:
    text = Path(path).read_text(encoding="utf-8")
    return json.loads(text) if str(path).endswith(".json") else yaml.safe_load(text)


def check_proof(doc: Dict[str, Any]) -> ProofReport:
    stmts = {s["id"]: s for s in doc.get("statements", [])}
    goal = doc.get("goal")
    rep = ProofReport(doc.get("title", "untitled proof"), str(goal))
    if goal not in stmts:
        rep.findings.append(Finding("P0-no-goal", "critical", f"goal {goal!r} is not among the statements"))
        return rep

    uses: Dict[str, List[str]] = {}
    for sid, s in stmts.items():
        u = list(s.get("uses") or [])
        uses[sid] = u
        for ref in u:
            if ref not in stmts:
                rep.findings.append(Finding("P5-dangling", "critical", f"{sid} uses {ref!r}, which is not defined", [sid, ref]))
    uses = {k: [r for r in v if r in stmts] for k, v in uses.items()}

    # ancestors of the goal and cycle detection (DFS with colours)
    WHITE, GREY, BLACK = 0, 1, 2
    colour = {k: WHITE for k in stmts}
    cycles: List[List[str]] = []
    stack: List[str] = []

    def dfs(v: str) -> None:
        colour[v] = GREY
        stack.append(v)
        for w in uses[v]:
            if colour[w] == GREY:
                cyc = stack[stack.index(w):] + [w]
                cycles.append(cyc)
            elif colour[w] == WHITE:
                dfs(w)
        stack.pop()
        colour[v] = BLACK

    for k in stmts:
        if colour[k] == WHITE:
            dfs(k)
    for cyc in cycles:
        # print the cycle in the direction of inference: premise -> conclusion
        rep.findings.append(Finding("P1-cycle", "critical",
                                    "circular dependency: " + " <- ".join(cyc) +
                                    "  (each statement is justified by the next, and the last is the first)", cyc))

    anc: Set[str] = set()
    todo = list(uses[goal])
    while todo:
        n = todo.pop()
        if n in anc:
            continue
        anc.add(n)
        todo.extend(uses[n])

    # P2: goal or an equivalent of it among the goal's ancestors
    equiv: Set[str] = {goal}
    for group in doc.get("equivalent", []) or []:
        if goal in group:
            equiv.update(group)
    for e in sorted(equiv & anc):
        what = "the goal itself" if e == goal else f"{e!r}, declared equivalent to the goal"
        rep.findings.append(Finding("P2-goal-smuggled", "critical",
                                    f"the proof of {goal!r} depends on {what}. It assumes what it sets out to prove.", [e, goal]))
    # an assumption that is equivalent to the goal is the same smuggling, even if not reached through `uses`
    for sid in equiv - {goal}:
        if sid in stmts and stmts[sid].get("kind") == "assumption" and sid in anc:
            pass  # already reported above

    # P3: unjustified non-root steps
    for sid in sorted(anc | {goal}):
        kind = stmts[sid].get("kind", "step")
        if kind not in ROOT_KINDS and not uses[sid]:
            rep.findings.append(Finding("P3-unjustified", "critical",
                                        f"{sid} ({kind}) has no support. Mark it as an axiom, definition, assumption or "
                                        f"cited theorem, or give the statements it uses.", [sid]))

    # P4: statements derived from the goal used to establish it
    for sid in sorted(anc):
        s = stmts[sid]
        if s.get("derived_from_goal") and not s.get("reversible", False):
            rep.findings.append(Finding("P4-affirming-consequent", "critical",
                                        f"{sid} was derived by assuming the goal, and is then used to conclude the goal. "
                                        f"A true consequence says nothing about its premise unless every step is reversible "
                                        f"(set `reversible: true` only if each step is an equivalence).", [sid, goal]))

    # inventory
    for sid in sorted(anc):
        kind = stmts[sid].get("kind", "step")
        if kind == "axiom":
            rep.axioms.append(sid)
        elif kind == "assumption":
            rep.assumptions.append(sid)
        elif kind in ("cited", "definition"):
            rep.cited.append(sid)
    if rep.assumptions:
        rep.findings.append(Finding("P6-conditional", "info",
                                    f"the result holds only under the assumptions {rep.assumptions}", rep.assumptions))
    rep.unused = sorted(set(stmts) - anc - {goal})

    # depth (longest chain from a root to the goal), only meaningful when acyclic
    if not cycles:
        memo: Dict[str, int] = {}

        def depth(v: str) -> int:
            if v not in memo:
                memo[v] = 0 if not uses[v] else 1 + max(depth(w) for w in uses[v])
            return memo[v]
        rep.depth = depth(goal)
    return rep
