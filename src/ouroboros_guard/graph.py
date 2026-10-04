"""The information graph and the checks that make a prediction honest.

Rule zero (see docs/MATH.md):  Y ∉ Anc(Ŷ)
and every ancestor of Ŷ existed before Ŷ was fixed.

The graph is built from ledger events: an edge parent -> child means
"information in parent could influence child".
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Set

from .ledger import Event
from .timeutil import is_before, parse_when

SEVERITY_ORDER = {"critical": 0, "warn": 1, "info": 2}


@dataclass
class Finding:
    code: str
    severity: str  # critical | warn | info
    message: str
    nodes: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict:
        return {"code": self.code, "severity": self.severity, "message": self.message, "nodes": self.nodes}


CONTEXT_TYPES = ("retrieval", "tool_call")


class InfoGraph:
    """Information graph built from ledger events.

    context_is_ancestor (default True): an LLM agent's context window is shared, so anything it
    retrieved or ran before making a prediction could have influenced it. Every retrieval and tool
    call recorded before a prediction becomes an implicit parent of that prediction, unless the
    prediction is marked `meta.context = "isolated"` (it was made in a fresh context whose inputs
    are listed explicitly).
    """

    def __init__(self, events: Iterable[Event], *, context_is_ancestor: bool = True):
        self.events: Dict[str, Event] = {}
        self.order: List[str] = []
        for e in events:
            self.events[e.id] = e
            self.order.append(e.id)
        self.parents: Dict[str, List[str]] = {i: list(self.events[i].parents) for i in self.order}
        self.implicit: Set[tuple] = set()
        if context_is_ancestor:
            seen_context: List[str] = []
            for i in self.order:
                e = self.events[i]
                if e.type == "prediction" and e.meta.get("context") != "isolated":
                    for c in seen_context:
                        if c not in self.parents[i]:
                            self.parents[i].append(c)
                            self.implicit.add((c, i))
                if e.type in CONTEXT_TYPES:
                    seen_context.append(i)
        self.children: Dict[str, List[str]] = defaultdict(list)
        for child, ps in self.parents.items():
            for p in ps:
                self.children[p].append(child)

    # ---- structure ---------------------------------------------------------
    def ancestors(self, node: str) -> Set[str]:
        seen: Set[str] = set()
        stack = list(self.parents.get(node, []))
        while stack:
            n = stack.pop()
            if n in seen:
                continue
            seen.add(n)
            stack.extend(self.parents.get(n, []))
        return seen

    def path_to(self, src: str, dst: str) -> List[str]:
        """One directed path src -> ... -> dst (following parent->child edges), or []."""
        prev: Dict[str, Optional[str]] = {src: None}
        queue = [src]
        while queue:
            n = queue.pop(0)
            if n == dst:
                out = [n]
                while prev[out[-1]] is not None:
                    out.append(prev[out[-1]])  # type: ignore[arg-type]
                return list(reversed(out))
            for c in self.children.get(n, []):
                if c not in prev:
                    prev[c] = n
                    queue.append(c)
        return []

    def cycles(self) -> List[List[str]]:
        """Return one representative cycle per strongly connected component of size > 1 (or self-loop)."""
        index: Dict[str, int] = {}
        low: Dict[str, int] = {}
        on: Set[str] = set()
        stack: List[str] = []
        comps: List[List[str]] = []
        counter = [0]
        nodes = set(self.order) | {p for ps in self.parents.values() for p in ps}

        def strong(v: str) -> None:
            # iterative Tarjan to stay safe on deep graphs
            work = [(v, iter(self.children.get(v, [])))]
            index[v] = low[v] = counter[0]
            counter[0] += 1
            stack.append(v)
            on.add(v)
            while work:
                node, it = work[-1]
                advanced = False
                for w in it:
                    if w not in index:
                        index[w] = low[w] = counter[0]
                        counter[0] += 1
                        stack.append(w)
                        on.add(w)
                        work.append((w, iter(self.children.get(w, []))))
                        advanced = True
                        break
                    elif w in on:
                        low[node] = min(low[node], index[w])
                if advanced:
                    continue
                work.pop()
                if work:
                    parent = work[-1][0]
                    low[parent] = min(low[parent], low[node])
                if low[node] == index[node]:
                    comp = []
                    while True:
                        w = stack.pop()
                        on.discard(w)
                        comp.append(w)
                        if w == node:
                            break
                    if len(comp) > 1 or node in self.children.get(node, []):
                        comps.append(comp)

        for v in sorted(nodes):
            if v not in index:
                strong(v)
        return comps

    # ---- checks ------------------------------------------------------------
    def predictions(self) -> List[Event]:
        return [self.events[i] for i in self.order if self.events[i].type == "prediction"]

    def commit_time(self, pred: Event) -> Optional[str]:
        """Earliest commit event that names this prediction as a parent."""
        times = [self.events[c].t for c in self.children.get(pred.id, []) if self.events[c].type == "commit"]
        return min(times) if times else None

    def prediction_time(self, pred: Event, default_as_of: Optional[str] = None) -> Optional[str]:
        return pred.meta.get("as_of") or default_as_of or self.commit_time(pred) or pred.t

    def check_prediction(self, pred_id: str, *, default_as_of: Optional[str] = None,
                         missing_date_policy: str = "warn") -> List[Finding]:
        pred = self.events[pred_id]
        out: List[Finding] = []
        anc = self.ancestors(pred_id)
        when = self.prediction_time(pred, default_as_of)

        # R1: the outcome being predicted must not be an ancestor.
        for a in sorted(anc):
            ev = self.events.get(a)
            if ev is None:
                out.append(Finding("G0-unknown-parent", "warn",
                                   f"{pred_id} depends on {a}, which is not in the ledger, so its provenance is unknown.", [a]))
                continue
            if ev.type == "outcome" and (pred.target is None or ev.target in (None, pred.target)):
                path = self.path_to(a, pred_id)
                out.append(Finding("G1-outcome-ancestor", "critical",
                                   f"The outcome {a} (target {ev.target!r}) is an ancestor of prediction {pred_id}. "
                                   f"Path: {' -> '.join(path)}. The prediction saw its own answer.", path or [a, pred_id]))

        # R2: every ancestor must have existed before the prediction was fixed.
        if when:
            for a in sorted(anc):
                ev = self.events.get(a)
                if ev is None or ev.type in ("label",) and ev.available_at is None:
                    continue
                stamp = ev.available_at
                if stamp is None:
                    if ev.type in ("retrieval", "input") and missing_date_policy != "allow":
                        sev = "critical" if missing_date_policy == "reject" else "warn"
                        out.append(Finding("G2-undated-ancestor", sev,
                                           f"{a} ({ev.type}, source {ev.source!r}) has no availability date, so it cannot be "
                                           f"shown to predate {pred_id}.", [a, pred_id]))
                    continue
                verdict = is_before(stamp, when)
                if verdict is False:
                    out.append(Finding("G3-future-ancestor", "critical",
                                       f"{a} became available at {stamp}, which is not before the prediction time {when} "
                                       f"of {pred_id}. Information from the future reached the prediction.", [a, pred_id]))
                elif verdict is None:
                    sev = "critical" if missing_date_policy == "reject" else ("warn" if missing_date_policy == "warn" else "info")
                    out.append(Finding("G4-ambiguous-date", sev,
                                       f"{a} is dated {stamp!r}, which straddles the prediction time {when}. "
                                       f"Use a more precise date or exclude it.", [a, pred_id]))

        # R4: the prediction must be committed before its outcome is recorded.
        ct = self.commit_time(pred)
        outcomes = [self.events[i] for i in self.order
                    if self.events[i].type == "outcome" and pred.target is not None and self.events[i].target == pred.target]
        for o in outcomes:
            if ct is None:
                out.append(Finding("G5-uncommitted", "warn",
                                   f"Prediction {pred_id} was never committed, but its outcome {o.id} is in the ledger. "
                                   f"Nothing proves the prediction existed before the outcome.", [pred_id, o.id]))
            elif is_before(ct, o.t) is not True:
                out.append(Finding("G6-commit-after-outcome", "critical",
                                   f"Prediction {pred_id} was committed at {ct}, not before its outcome {o.id} was recorded at {o.t}.",
                                   [pred_id, o.id]))
        return out

    def check_all(self, *, default_as_of: Optional[str] = None, missing_date_policy: str = "warn",
                  look_budget: Optional[int] = None, require_different_judge: bool = True) -> List[Finding]:
        out: List[Finding] = []
        for cyc in self.cycles():
            out.append(Finding("G7-cycle", "critical",
                               f"The information graph contains a cycle: {' -> '.join(sorted(cyc))}. "
                               f"Something depends on itself, which is circular reasoning.", sorted(cyc)))
        for p in self.predictions():
            out.extend(self.check_prediction(p.id, default_as_of=default_as_of, missing_date_policy=missing_date_policy))

        # test-set looks (adaptive overfitting)
        looks = [self.events[i] for i in self.order if self.events[i].type == "look"]
        by_set: Dict[str, List[Event]] = defaultdict(list)
        for lk in looks:
            by_set[lk.meta.get("set", lk.target or "test")].append(lk)
        if look_budget is not None:
            for name, lks in by_set.items():
                if len(lks) > look_budget:
                    out.append(Finding("G8-look-budget", "critical" if len(lks) > 3 * look_budget else "warn",
                                       f"Evaluation set {name!r} was scored {len(lks)} times against a budget of {look_budget}. "
                                       f"Each look leaks information about its labels.", [lk.id for lk in lks]))

        # judge independence
        if require_different_judge:
            for j in (self.events[i] for i in self.order if self.events[i].type == "judge"):
                jm = j.meta.get("model")
                for parent in j.parents:
                    pe = self.events.get(parent)
                    if pe is not None and jm and pe.meta.get("model") == jm:
                        out.append(Finding("G9-self-grading", "warn",
                                           f"Judge {j.id} uses model {jm!r}, the same model that produced {parent}. "
                                           f"Agreement between them is weak evidence.", [j.id, parent]))

        # citation echo: several retrieved sources that report the same original result
        for p in self.predictions():
            origins: Dict[str, List[str]] = defaultdict(list)
            for a in self.ancestors(p.id):
                ev = self.events.get(a)
                if ev is not None and ev.type == "retrieval" and ev.meta.get("origin"):
                    origins[str(ev.meta["origin"])].append(a)
            for origin, ids in origins.items():
                if len(ids) > 1:
                    out.append(Finding("G10-citation-echo", "info",
                                       f"{len(ids)} sources behind {p.id} report the same origin {origin!r}. "
                                       f"Count them as one piece of evidence.", sorted(ids)))
        out.sort(key=lambda f: (SEVERITY_ORDER.get(f.severity, 9), f.code))
        return out
