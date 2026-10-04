"""Weight of evidence: a check is worth exactly as much as its ability to fail.

    posterior odds = K x prior odds,   K = P(pass | H) / P(pass | not H)
    W = log2 K  bits   (I. J. Good's weight of evidence)

A circular check passes whatever the truth is: P(pass | not H) = 1, so K = 1 and W = 0.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


def bayes_factor(p_pass_given_h: float, p_pass_given_not_h: float) -> float:
    if not (0 <= p_pass_given_h <= 1 and 0 <= p_pass_given_not_h <= 1):
        raise ValueError("probabilities must lie in [0, 1]")
    if p_pass_given_not_h == 0:
        return math.inf
    return p_pass_given_h / p_pass_given_not_h


def weight_of_evidence_bits(k: float) -> float:
    return math.inf if math.isinf(k) else math.log2(k) if k > 0 else -math.inf


def posterior_probability(prior: float, k: float) -> float:
    if not 0 < prior < 1:
        raise ValueError("prior must lie strictly between 0 and 1")
    if math.isinf(k):
        return 1.0
    odds = k * prior / (1 - prior)
    return odds / (1 + odds)


@dataclass
class CheckAssessment:
    bayes_factor: float
    bits: float
    posterior: float
    verdict: str  # informative | weak | circular

    def describe(self) -> str:
        return (f"K = {self.bayes_factor:.3g}, {self.bits:.2f} bits, posterior {self.posterior:.1%} "
                f"-> {self.verdict}")


def assess_check(p_pass_given_h: float, p_pass_given_not_h: float, prior: float = 0.5,
                 circular_threshold: float = 0.95) -> CheckAssessment:
    """Classify a check by how much it can move belief.

    circular: it passes almost regardless of the truth (P(pass|not H) >= threshold and K <= 1.05)
    weak:     less than one bit of evidence
    """
    k = bayes_factor(p_pass_given_h, p_pass_given_not_h)
    bits = weight_of_evidence_bits(k)
    post = posterior_probability(prior, k)
    if p_pass_given_not_h >= circular_threshold and k <= 1.05:
        verdict = "circular"
    elif bits < 1:
        verdict = "weak"
    else:
        verdict = "informative"
    return CheckAssessment(k, bits, post, verdict)
