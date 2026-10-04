"""Append-only, hash-chained provenance ledger.

Every piece of information that can influence a prediction is an event:
an input file, a retrieved document, a tool call, a derived artefact, a
prediction, a commitment, a revealed outcome, a look at the test set.
`parents` records information flow, so the ledger *is* the information
graph. Each line carries the hash of the previous line, so silent edits
or deletions are detectable.
"""
from __future__ import annotations

import hashlib
import json
import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .timeutil import now_utc, parse_when

EVENT_TYPES = {
    "input",       # a dataset, file or fact registered as available at prediction time
    "retrieval",   # a document returned by search, RAG or a database lookup
    "tool_call",   # any tool invocation by the agent
    "derive",      # an artefact computed from parents (features, model, summary, memory note)
    "label",       # training labels (legitimate ancestors)
    "prediction",  # a prediction for a target
    "commit",      # a cryptographic commitment to one or more predictions
    "outcome",     # the revealed ground truth for a target
    "look",        # someone scored something against an evaluation set
    "judge",       # an evaluator's verdict on a prediction or argument
    "control",     # a negative-control result
    "note",
}

GENESIS = "0" * 64


def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: os.PathLike) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class Event:
    id: str
    type: str
    t: str
    parents: List[str] = field(default_factory=list)
    available_at: Optional[str] = None
    target: Optional[str] = None
    source: Optional[str] = None
    content_sha256: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)
    prev: str = GENESIS
    hash: str = ""

    def body(self) -> Dict[str, Any]:
        d = {k: v for k, v in self.__dict__.items() if k != "hash"}
        return d

    def compute_hash(self) -> str:
        return sha256_text(canonical(self.body()))

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Event":
        known = {k: d.get(k) for k in cls.__dataclass_fields__ if k in d}
        known.setdefault("parents", [])
        known.setdefault("meta", {})
        if known.get("parents") is None:
            known["parents"] = []
        if known.get("meta") is None:
            known["meta"] = {}
        return cls(**known)


class Ledger:
    """A JSON-lines file of hash-chained events."""

    def __init__(self, path: os.PathLike):
        self.path = Path(path)

    # ---- reading -----------------------------------------------------------
    def read(self) -> List[Event]:
        if not self.path.exists():
            return []
        out = []
        with open(self.path, encoding="utf-8") as f:
            for n, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(Event.from_dict(json.loads(line)))
                except (json.JSONDecodeError, TypeError) as exc:
                    raise ValueError(f"{self.path}:{n}: unreadable ledger line ({exc})") from exc
        return out

    def last_hash(self) -> str:
        events = self.read()
        return events[-1].hash if events else GENESIS

    # ---- writing -----------------------------------------------------------
    def append(
        self,
        type: str,
        *,
        parents: Optional[Iterable[str]] = None,
        available_at: Any = None,
        target: Optional[str] = None,
        source: Optional[str] = None,
        content: Optional[str] = None,
        content_sha256: Optional[str] = None,
        meta: Optional[Dict[str, Any]] = None,
        id: Optional[str] = None,
        t: Optional[str] = None,
    ) -> Event:
        if type not in EVENT_TYPES:
            raise ValueError(f"unknown event type {type!r}; expected one of {sorted(EVENT_TYPES)}")
        if available_at is not None:
            parse_when(available_at)  # validate early
            available_at = str(available_at)
        if content is not None and content_sha256 is None:
            content_sha256 = sha256_text(content)
        events = self.read()
        ev = Event(
            id=id or f"{type}:{uuid.uuid4().hex[:12]}",
            type=type,
            t=t or now_utc(),
            parents=list(parents or []),
            available_at=available_at,
            target=target,
            source=source,
            content_sha256=content_sha256,
            meta=dict(meta or {}),
            prev=events[-1].hash if events else GENESIS,
        )
        if ev.id in {e.id for e in events}:
            raise ValueError(f"duplicate event id {ev.id!r}")
        ev.hash = ev.compute_hash()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(canonical(ev.__dict__) + "\n")
        return ev

    # ---- integrity ---------------------------------------------------------
    def verify_chain(self) -> List[str]:
        """Return a list of integrity problems (empty means the chain is intact)."""
        problems = []
        prev = GENESIS
        seen = set()
        for i, ev in enumerate(self.read(), 1):
            if ev.prev != prev:
                problems.append(f"event {i} ({ev.id}): chain broken, an earlier line was edited, removed or reordered")
            if ev.compute_hash() != ev.hash:
                problems.append(f"event {i} ({ev.id}): content does not match its hash, the line was edited")
            if ev.id in seen:
                problems.append(f"event {i} ({ev.id}): duplicate id")
            seen.add(ev.id)
            prev = ev.hash
        return problems
