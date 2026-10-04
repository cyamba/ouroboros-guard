"""Performance ceilings set by the measurement itself.

No model can predict the noise of a single run, so the reproducibility of the
experiment caps the score any honest model can reach against one run.

Binary outcomes, symmetric independent errors with per-run accuracy q:
    a = q^2 + (1 - q)^2   =>   q = (1 + sqrt(2a - 1)) / 2
Continuous outcomes, Y_i = T + e_i with independent errors (classical test theory):
    corr(Y1, Y2) = R (reliability)   =>   max corr(f(X), Y1) = sqrt(R)
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional


def binary_accuracy_ceiling(replicate_agreement: float) -> float:
    a = float(replicate_agreement)
    if not 0.5 <= a <= 1:
        raise ValueError("replicate agreement for a binary outcome must lie in [0.5, 1]")
    return (1 + math.sqrt(2 * a - 1)) / 2


def correlation_ceiling(test_retest_r: float) -> float:
    r = float(test_retest_r)
    if not 0 <= r <= 1:
        raise ValueError("test-retest correlation must lie in [0, 1]")
    return math.sqrt(r)


@dataclass
class CeilingCheck:
    claimed: float
    ceiling: float
    margin: float
    suspicious: bool

    def describe(self) -> str:
        rel = "above" if self.claimed > self.ceiling else "below"
        verdict = "investigate for leakage" if self.suspicious else "plausible"
        return f"claimed {self.claimed:.3f} is {rel} the ceiling {self.ceiling:.3f} -> {verdict}"


def check_claim(claimed: float, *, replicate_agreement: Optional[float] = None,
                test_retest_r: Optional[float] = None, tolerance: float = 0.01) -> CeilingCheck:
    if replicate_agreement is not None:
        ceil = binary_accuracy_ceiling(replicate_agreement)
    elif test_retest_r is not None:
        ceil = correlation_ceiling(test_retest_r)
    else:
        raise ValueError("give replicate_agreement (binary) or test_retest_r (continuous)")
    return CeilingCheck(claimed, ceil, claimed - ceil, claimed > ceil + tolerance)
