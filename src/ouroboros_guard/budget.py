"""Budget your looks at the test set.

Every time a score on the test set feeds back into a decision, information
about its labels leaks into the system: up to log2(#possible answers) bits
per look. `HoldoutGuard` counts, logs and limits those looks, and offers
Dwork et al.'s Thresholdout for workflows that must look often.
"""
from __future__ import annotations

from typing import Any, Callable, Optional, Sequence

import numpy as np


class BudgetExceeded(RuntimeError):
    pass


class HoldoutGuard:
    """Wraps a scorer and the sealed test labels. The agent never touches the labels directly.

    mode="strict": refuse after `budget` looks.
    mode="thresholdout": a simplified Thresholdout (Dwork, Feldman, Hardt, Pitassi, Reingold & Roth,
        Science 2015). It answers with the training score unless that differs from the holdout score by
        more than a noisy threshold; only then does it reveal a noisy holdout score and spend budget.
        Tune `threshold` and `sigma` for your metric; the defaults suit accuracies in [0, 1].
    """

    def __init__(self, scorer: Callable[[Sequence[Any], Sequence[Any]], float], y_true: Sequence[Any], *,
                 budget: int = 1, mode: str = "strict", threshold: float = 0.04, sigma: float = 0.01,
                 ledger=None, set_name: str = "test", seed: Optional[int] = None):
        if mode not in ("strict", "thresholdout"):
            raise ValueError("mode must be strict or thresholdout")
        self._scorer = scorer
        self._y = np.asarray(y_true)
        self.budget = budget
        self.mode = mode
        self.threshold = threshold
        self.sigma = sigma
        self.ledger = ledger
        self.set_name = set_name
        self.looks = 0
        self.spent = 0
        self._rng = np.random.default_rng(seed)

    def _log(self, note: str, value: float) -> None:
        if self.ledger is not None:
            self.ledger.append("look", target=self.set_name,
                               meta={"set": self.set_name, "mode": self.mode, "note": note, "reported": round(float(value), 6)})

    def score(self, predictions: Sequence[Any], train_score: Optional[float] = None) -> float:
        self.looks += 1
        if self.mode == "strict":
            if self.spent >= self.budget:
                raise BudgetExceeded(f"the {self.set_name!r} set has been scored {self.spent} time(s); budget is {self.budget}")
            self.spent += 1
            s = float(self._scorer(self._y, predictions))
            self._log("strict", s)
            return s
        if train_score is None:
            raise ValueError("thresholdout needs the training (or development) score of the same predictor")
        hold = float(self._scorer(self._y, predictions))
        t = self.threshold + self._rng.laplace(0, 4 * self.sigma)
        if abs(train_score - hold) <= t:
            self._log("thresholdout: returned training score", train_score)
            return float(train_score)
        if self.spent >= self.budget:
            raise BudgetExceeded(f"thresholdout budget of {self.budget} overfitting detections is spent")
        self.spent += 1
        noisy = hold + self._rng.laplace(0, self.sigma)
        self._log("thresholdout: revealed noisy holdout score", noisy)
        return float(noisy)
