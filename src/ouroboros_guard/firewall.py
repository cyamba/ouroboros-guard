"""Time firewall for tools: only information that existed before `as_of` gets through.

Use it to wrap any retrieval function (search, RAG, database lookup) so the
agent can never see documents dated at or after the prediction time, nor
documents from sources known to publish the outcomes.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

from .timeutil import is_before

DATE_KEYS = ("available_at", "published_at", "date", "published", "year", "created_at")
SOURCE_KEYS = ("url", "source", "doi", "id", "title")


@dataclass
class Decision:
    allowed: bool
    reason: str
    status: str  # pass | blocked-date | blocked-source | ambiguous | undated


class TimeFirewall:
    def __init__(self, as_of: Any, *, missing_date_policy: str = "warn",
                 blocked_sources: Sequence[str] = (), ledger=None):
        if missing_date_policy not in ("reject", "warn", "allow"):
            raise ValueError("missing_date_policy must be reject, warn or allow")
        self.as_of = as_of
        self.policy = missing_date_policy
        self.blocked = [re.compile(p, re.IGNORECASE) for p in blocked_sources]
        self.ledger = ledger

    @staticmethod
    def _date_of(item: Dict[str, Any]) -> Any:
        for k in DATE_KEYS:
            if item.get(k) not in (None, ""):
                return item[k]
        return None

    @staticmethod
    def _source_of(item: Dict[str, Any]) -> str:
        return " ".join(str(item[k]) for k in SOURCE_KEYS if item.get(k))

    def check(self, item: Dict[str, Any]) -> Decision:
        src = self._source_of(item)
        for pat in self.blocked:
            if pat.search(src):
                return Decision(False, f"source matches blocked pattern {pat.pattern!r}", "blocked-source")
        when = self._date_of(item)
        if self.as_of is None:
            return Decision(True, "no as_of configured", "pass")
        verdict = is_before(when, self.as_of)
        if verdict is True:
            return Decision(True, f"dated {when}, before {self.as_of}", "pass")
        if verdict is False:
            return Decision(False, f"dated {when}, not before {self.as_of}", "blocked-date")
        status = "undated" if when is None else "ambiguous"
        reason = "no date" if when is None else f"date {when!r} straddles {self.as_of}"
        if self.policy == "reject":
            return Decision(False, reason + " (policy: reject)", status)
        return Decision(True, reason + f" (policy: {self.policy})", status)

    def filter(self, items: Iterable[Dict[str, Any]], *, parent: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return only the allowed items. Each allowed item is logged to the ledger when one is attached."""
        kept = []
        for item in items:
            d = self.check(item)
            if d.allowed:
                if self.ledger is not None:
                    ev = self.ledger.append(
                        "retrieval",
                        parents=[parent] if parent else [],
                        available_at=self._date_of(item) if d.status == "pass" else None,
                        source=self._source_of(item)[:300] or None,
                        meta={"firewall": d.status, "origin": item.get("origin")},
                    )
                    item = {**item, "_ledger_id": ev.id}
                kept.append({**item, "_firewall": d.status})
        return kept

    def wrap(self, fn: Callable[..., Iterable[Dict[str, Any]]]) -> Callable[..., List[Dict[str, Any]]]:
        """Decorate a retrieval function so its results pass through the firewall."""
        def guarded(*args, **kwargs):
            return self.filter(fn(*args, **kwargs))
        guarded.__name__ = getattr(fn, "__name__", "guarded")
        guarded.__doc__ = (fn.__doc__ or "") + f"\n\n[ouroboros-guard] results filtered to before {self.as_of}."
        return guarded
