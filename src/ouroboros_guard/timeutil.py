"""Time handling with honest uncertainty.

A date such as "2024" or "2024-05" does not name an instant; it names an
interval. Leakage checks must treat it as such: a document published in
"2024" may or may not predate a cut-off of 2024-06-01. Every timestamp is
therefore parsed into a half-open UTC interval [start, end), and comparisons
return True, False or None (ambiguous).

A cut-off is always read as the *start* of its interval: "as of 2024-06-01"
means "information that existed before 2024-06-01T00:00Z". That is the
conservative reading for leakage control.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Optional, Union

When = Union[str, int, date, datetime, None]

_YEAR = re.compile(r"^\d{4}$")
_MONTH = re.compile(r"^(\d{4})-(\d{2})$")
_DAY = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_INSTANT = timedelta(microseconds=1)


@dataclass(frozen=True)
class Interval:
    """A half-open UTC interval [start, end). A precise instant has end == start + 1 µs."""

    start: datetime
    end: datetime

    @property
    def is_instant(self) -> bool:
        return self.end - self.start <= _INSTANT

    def iso(self) -> str:
        if self.is_instant:
            return self.start.isoformat().replace("+00:00", "Z")
        return f"[{self.start.date().isoformat()}, {self.end.date().isoformat()})"


def _utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def parse_when(value: When) -> Optional[Interval]:
    """Parse a timestamp or partial date into an Interval; None for missing values.

    Accepted: datetime, date, int year, "YYYY", "YYYY-MM", "YYYY-MM-DD", and ISO-8601
    datetimes (a trailing "Z" is allowed). Naive datetimes are taken as UTC.
    """
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        s = _utc(value)
        return Interval(s, s + _INSTANT)
    if isinstance(value, date):
        s = datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
        return Interval(s, s + timedelta(days=1))
    if isinstance(value, int):
        value = f"{value:04d}"
    text = str(value).strip()
    if _YEAR.match(text):
        y = int(text)
        return Interval(datetime(y, 1, 1, tzinfo=timezone.utc), datetime(y + 1, 1, 1, tzinfo=timezone.utc))
    m = _MONTH.match(text)
    if m:
        y, mo = int(m.group(1)), int(m.group(2))
        nxt = datetime(y + 1, 1, 1, tzinfo=timezone.utc) if mo == 12 else datetime(y, mo + 1, 1, tzinfo=timezone.utc)
        return Interval(datetime(y, mo, 1, tzinfo=timezone.utc), nxt)
    m = _DAY.match(text)
    if m:
        s = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=timezone.utc)
        return Interval(s, s + timedelta(days=1))
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"unrecognised date or time: {value!r}") from exc
    s = _utc(dt)
    return Interval(s, s + _INSTANT)


def is_before(item: When, cutoff: When) -> Optional[bool]:
    """Did `item` certainly exist before `cutoff`?

    True  - the whole item interval ends at or before the cut-off instant.
    False - the item starts at or after the cut-off instant.
    None  - missing date, or the item interval straddles the cut-off (ambiguous).
    """
    a, b = parse_when(item), parse_when(cutoff)
    if a is None or b is None:
        return None
    if a.end <= b.start:
        return True
    if a.start >= b.start:
        return False
    return None


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
