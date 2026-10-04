"""The classic leak, caught by a negative control.

Sixty samples, 5,000 features of pure noise, labels that mean nothing.
Pipeline A chooses the 20 "best" features on ALL the data, then cross-validates.
Pipeline B chooses them inside each training fold.
Run both on scrambled labels: A still scores far above chance, B falls to chance.
(After Ambroise & McLachlan, PNAS 2002.)

    python examples/feature_selection_leak/run.py
"""
from __future__ import annotations

import numpy as np

from ouroboros_guard.controls import permutation_control

N, P, K, FOLDS = 60, 5000, 20, 5


def t_stat(X, y):
    a, b = X[y == 1], X[y == 0]
    return (a.mean(0) - b.mean(0)) / np.sqrt(a.var(0, ddof=1) / len(a) + b.var(0, ddof=1) / len(b) + 1e-12)


def nearest_centroid_accuracy(Xtr, ytr, Xte, yte):
    c1, c0 = Xtr[ytr == 1].mean(0), Xtr[ytr == 0].mean(0)
    pred = (((Xte - c1) ** 2).sum(1) < ((Xte - c0) ** 2).sum(1)).astype(int)
    return float(np.mean(pred == yte))


def make_pipeline(leaky: bool, seed: int = 0):
    def pipeline(X, y):
        rng = np.random.default_rng(seed)
        idx = rng.permutation(len(y))
        fold = np.arange(len(y)) % FOLDS
        if leaky:  # selection sees every label, including the ones it will be tested on
            sel = np.argsort(-np.abs(t_stat(X, y)))[:K]
        accs = []
        for f in range(FOLDS):
            te, tr = idx[fold == f], idx[fold != f]
            if not leaky:
                sel = np.argsort(-np.abs(t_stat(X[tr], y[tr])))[:K]
            accs.append(nearest_centroid_accuracy(X[tr][:, sel], y[tr], X[te][:, sel], y[te]))
        return float(np.mean(accs))
    return pipeline


def main(runs: int = 100):
    rng = np.random.default_rng(42)
    X = rng.standard_normal((N, P))
    y = np.array([0, 1] * (N // 2))
    results = {}
    for name, leaky in (("selection-before-split", True), ("selection-inside-folds", False)):
        res = permutation_control(make_pipeline(leaky), X, y, runs=runs, seed=1, name=name)
        results[name] = res
        print(res.describe())
    return results


if __name__ == "__main__":
    main()
