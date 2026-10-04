"""Split audits: is the test set really new, or a near-copy of the training set?

A random split puts near-identical items on both sides, and the model then
recognises neighbours instead of learning a rule. Report how similar each
test item is to its nearest training item, and split by group or time.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set

import numpy as np

from .timeutil import is_before


def shingles(text: str, n: int = 3) -> Set[str]:
    t = " ".join(str(text).lower().split())
    if len(t) <= n:
        return {t}
    return {t[i:i + n] for i in range(len(t) - n + 1)}


def jaccard(a: Set[Any], b: Set[Any]) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def nearest_similarity(train: Sequence[Any], test: Sequence[Any], metric: str = "jaccard", n: int = 3) -> np.ndarray:
    """For each test item, the similarity to its nearest training item.

    metric: "jaccard" (strings, character n-grams), "cosine" (numeric vectors),
            "tanimoto" (binary fingerprints / bit vectors), "exact" (equality).
    """
    if metric == "exact":
        seen = {json.dumps(x, sort_keys=True, default=str) for x in train}
        return np.array([1.0 if json.dumps(x, sort_keys=True, default=str) in seen else 0.0 for x in test])
    if metric == "jaccard":
        tr = [shingles(x, n) for x in train]
        out = np.zeros(len(test))
        for i, x in enumerate(test):
            s = shingles(x, n)
            out[i] = max((jaccard(s, t) for t in tr), default=0.0)
        return out
    A = np.asarray(train, dtype=float)
    B = np.asarray(test, dtype=float)
    if metric == "cosine":
        An = A / np.clip(np.linalg.norm(A, axis=1, keepdims=True), 1e-12, None)
        Bn = B / np.clip(np.linalg.norm(B, axis=1, keepdims=True), 1e-12, None)
        return (Bn @ An.T).max(axis=1)
    if metric == "tanimoto":
        A, B = (A > 0).astype(float), (B > 0).astype(float)
        inter = B @ A.T
        union = B.sum(1, keepdims=True) + A.sum(1)[None, :] - inter
        return np.where(union > 0, inter / np.clip(union, 1e-12, None), 1.0).max(axis=1)
    raise ValueError(f"unknown metric {metric!r}")


@dataclass
class SplitReport:
    n_train: int
    n_test: int
    metric: str
    threshold: float
    fraction_above: float
    median: float
    p90: float
    max: float
    worst: List[int]
    leak_suspected: bool

    def describe(self) -> str:
        return (f"{self.fraction_above:.1%} of {self.n_test} test items have a training neighbour with "
                f"{self.metric} similarity >= {self.threshold} (median {self.median:.2f}, p90 {self.p90:.2f}, "
                f"max {self.max:.2f})" + (" -> near-duplicate leakage" if self.leak_suspected else " -> ok"))

    def save(self, directory: Path) -> Path:
        d = Path(directory)
        d.mkdir(parents=True, exist_ok=True)
        p = d / "split_report.json"
        p.write_text(json.dumps(asdict(self), indent=2) + "\n")
        return p


def audit_split(train: Sequence[Any], test: Sequence[Any], *, metric: str = "jaccard", threshold: float = 0.9,
                max_fraction_above: float = 0.0, n: int = 3) -> SplitReport:
    sims = nearest_similarity(train, test, metric, n)
    frac = float(np.mean(sims >= threshold)) if len(sims) else 0.0
    worst = [int(i) for i in np.argsort(-sims)[:10]]
    return SplitReport(len(train), len(test), metric, threshold, frac, float(np.median(sims)),
                       float(np.quantile(sims, 0.9)), float(sims.max()), worst, frac > max_fraction_above)


def group_split(groups: Sequence[Any], test_fraction: float = 0.2, seed: int = 0) -> np.ndarray:
    """Boolean mask of test rows; whole groups (scaffolds, patients, labs, clusters) go to one side."""
    g = np.asarray(groups)
    uniq = np.unique(g)
    rng = np.random.default_rng(seed)
    rng.shuffle(uniq)
    n_test = max(1, int(round(len(uniq) * test_fraction)))
    return np.isin(g, uniq[:n_test])


def time_split(times: Sequence[Any], cutoff: Any) -> np.ndarray:
    """Boolean mask of test rows: everything not certainly before the cut-off goes to test."""
    return np.array([is_before(t, cutoff) is not True for t in times])


def group_overlap(train_groups: Sequence[Any], test_groups: Sequence[Any]) -> Dict[str, Any]:
    shared = sorted(set(map(str, train_groups)) & set(map(str, test_groups)))
    return {"shared_groups": shared[:50], "n_shared": len(shared), "leak_suspected": bool(shared)}
