"""Negative controls: run the whole pipeline where there is nothing to find.

An honest pipeline falls to chance on scrambled labels. One that still
scores well is reading the answer from somewhere other than its inputs.
For agents that can read the literature, scrambling labels is not enough,
because the literature is not scrambled; use `mask_entities` and
`temporal_gap` as well.
"""
from __future__ import annotations

import json
import re
import shlex
import subprocess
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

from .timeutil import is_before, now_utc


@dataclass
class ControlResult:
    name: str
    real_score: Optional[float]
    null_scores: List[float]
    chance: Optional[float]
    tolerance: float
    null_mean: float = 0.0
    null_p95: float = 0.0
    p_value: Optional[float] = None
    leak_suspected: bool = False
    created_at: str = field(default_factory=now_utc)

    def describe(self) -> str:
        parts = [f"[{self.name}] scrambled-label runs: mean {self.null_mean:.3f}, 95th pct {self.null_p95:.3f}"]
        if self.chance is not None:
            parts.append(f"chance {self.chance:.3f}")
        if self.real_score is not None:
            parts.append(f"real {self.real_score:.3f} (permutation p = {self.p_value:.3g})")
        parts.append("LEAK SUSPECTED: the pipeline scores well on noise" if self.leak_suspected else "control passed")
        return "; ".join(parts)

    def save(self, directory: Path) -> Path:
        d = Path(directory) / "controls"
        d.mkdir(parents=True, exist_ok=True)
        p = d / f"{self.name}.json"
        p.write_text(json.dumps(asdict(self), indent=2) + "\n")
        return p


def majority_rate(y: Sequence[Any]) -> Optional[float]:
    vals, counts = np.unique(np.asarray(y), return_counts=True)
    if len(vals) > 20:
        return None  # looks continuous; caller must supply chance
    return float(counts.max() / counts.sum())


def _finish(name, real, nulls, chance, tolerance) -> ControlResult:
    nulls = [float(s) for s in nulls]
    arr = np.asarray(nulls)
    res = ControlResult(name, None if real is None else float(real), nulls, chance, tolerance)
    res.null_mean = float(arr.mean())
    res.null_p95 = float(np.quantile(arr, 0.95))
    if real is not None:
        res.p_value = float((1 + np.sum(arr >= real)) / (len(arr) + 1))
    res.leak_suspected = bool(chance is not None and res.null_mean > chance + tolerance)
    return res


def permutation_control(pipeline: Callable[[Any, np.ndarray], float], X: Any, y: Sequence[Any], *,
                        runs: int = 200, seed: int = 0, chance: Optional[float] = None,
                        tolerance: float = 0.05, name: str = "permutation", include_real: bool = True,
                        groups: Optional[Sequence[Any]] = None) -> ControlResult:
    """Score `pipeline(X, y_scrambled)` many times. `pipeline` must run EVERY step (selection, tuning, fitting).

    If `groups` is given, labels are permuted between whole groups, which keeps any group structure intact.
    """
    y = np.asarray(y)
    rng = np.random.default_rng(seed)
    chance = majority_rate(y) if chance is None else chance
    real = pipeline(X, y) if include_real else None
    nulls = []
    for _ in range(runs):
        if groups is None:
            ys = rng.permutation(y)
        else:
            g = np.asarray(groups)
            uniq = np.unique(g)
            perm = dict(zip(uniq, rng.permutation(uniq)))
            # each group takes the labels of another group (groups must have equal sizes for an exact swap;
            # otherwise fall back to permuting labels within the pooled set)
            sizes = {u: int(np.sum(g == u)) for u in uniq}
            if len(set(sizes.values())) == 1:
                ys = y.copy()
                for u in uniq:
                    ys[g == u] = y[g == perm[u]]
            else:
                ys = rng.permutation(y)
        nulls.append(pipeline(X, ys))
    return _finish(name, real, nulls, chance, tolerance)


_FLOAT = re.compile(r"[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?")


def _last_float(text: str) -> float:
    found = _FLOAT.findall(text)
    if not found:
        raise ValueError("the command printed no number; print the score as the last number on stdout")
    return float(found[-1])


def read_labels(path: Path) -> Tuple[List[str], List[str]]:
    """Read labels: one per line, or a CSV whose last column is the label. Returns (header_lines, labels)."""
    lines = Path(path).read_text().splitlines()
    header: List[str] = []
    if lines and not _FLOAT.fullmatch(lines[0].split(",")[-1].strip()) and "," in lines[0]:
        header, lines = [lines[0]], lines[1:]
    return header, [ln for ln in lines if ln.strip()]


def command_control(cmd: str, labels_path: Path, *, runs: int = 50, seed: int = 0,
                    chance: Optional[float] = None, tolerance: float = 0.05, name: str = "command",
                    timeout: Optional[float] = None) -> ControlResult:
    """Negative control for any program. `cmd` must contain `{labels}`; the program prints its score last.

    Rows of the labels file are kept, and only the label column is shuffled, so every other column stays aligned.
    """
    if "{labels}" not in cmd:
        raise ValueError("cmd must contain the placeholder {labels}")
    header, rows = read_labels(labels_path)
    split = [r.rsplit(",", 1) if "," in r else ["", r] for r in rows]
    keys = [s[0] for s in split]
    labels = [s[1] for s in split]
    rng = np.random.default_rng(seed)

    def run(lbls: List[str]) -> float:
        with tempfile.NamedTemporaryFile("w", suffix=Path(labels_path).suffix or ".csv", delete=False) as f:
            body = [f"{k},{v}" if k else v for k, v in zip(keys, lbls)]
            f.write("\n".join(header + body) + "\n")
            tmp = f.name
        try:
            proc = subprocess.run(cmd.replace("{labels}", shlex.quote(tmp)), shell=True, capture_output=True,
                                  text=True, timeout=timeout)
        finally:
            Path(tmp).unlink(missing_ok=True)
        if proc.returncode != 0:
            raise RuntimeError(f"command failed ({proc.returncode}): {proc.stderr.strip()[:500]}")
        return _last_float(proc.stdout)

    if chance is None:
        chance = majority_rate(labels)
    real = run(labels)
    nulls = [run(list(rng.permutation(labels))) for _ in range(runs)]
    return _finish(name, real, nulls, chance, tolerance)


def mask_entities(texts: Sequence[str], entities: Sequence[str], prefix: str = "ENTITY") -> Tuple[List[str], Dict[str, str]]:
    """Replace named entities with neutral codes so retrieval cannot look them up.

    Longest names are replaced first, matching whole words, ignoring case.
    """
    ordered = sorted(set(e for e in entities if e), key=len, reverse=True)
    mapping = {e: f"{prefix}_{i:03d}" for i, e in enumerate(ordered, 1)}
    out = []
    for t in texts:
        for e in ordered:
            t = re.sub(rf"(?<!\w){re.escape(e)}(?!\w)", mapping[e], t, flags=re.IGNORECASE)
        out.append(t)
    return out, mapping


@dataclass
class TemporalGap:
    acc_before: float
    acc_after: float
    n_before: int
    n_after: int
    gap: float
    ci_low: float
    ci_high: float
    memorisation_suspected: bool

    def describe(self) -> str:
        return (f"accuracy on outcomes known before the cut-off {self.acc_before:.3f} (n={self.n_before}) vs after "
                f"{self.acc_after:.3f} (n={self.n_after}); gap {self.gap:+.3f}, 95% CI [{self.ci_low:+.3f}, {self.ci_high:+.3f}]"
                + (" -> the model predicts the past much better than the future: likely memorisation"
                   if self.memorisation_suspected else ""))


def temporal_gap(correct: Sequence[bool], outcome_dates: Sequence[Any], cutoff: Any, *,
                 threshold: float = 0.05, n_boot: int = 2000, seed: int = 0) -> TemporalGap:
    """Compare accuracy on outcomes that were public before vs after a model's training cut-off."""
    c = np.asarray(correct, dtype=float)
    side = np.array([is_before(d, cutoff) for d in outcome_dates], dtype=object)
    b, a = c[side == True], c[side == False]  # noqa: E712  (ambiguous dates are dropped)
    if len(b) == 0 or len(a) == 0:
        raise ValueError("need outcomes on both sides of the cut-off")
    rng = np.random.default_rng(seed)
    boots = [rng.choice(b, len(b)).mean() - rng.choice(a, len(a)).mean() for _ in range(n_boot)]
    lo, hi = np.quantile(boots, [0.025, 0.975])
    gap = float(b.mean() - a.mean())
    return TemporalGap(float(b.mean()), float(a.mean()), len(b), len(a), gap, float(lo), float(hi),
                       bool(lo > threshold))
