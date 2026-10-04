"""Memorisation probes: does the model already know the answer?

Give a model the first part of a document it should not have seen (a paper,
a dataset row, a result table) and measure how much of the rest it
reproduces. High overlap on items that predate its training cut-off, and low
overlap on later ones, is the signature of memorisation (see Golchin &
Surdeanu, ICLR 2024, for the guided-completion idea this follows).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, List, Sequence

_WORD = re.compile(r"\w+", re.UNICODE)


def tokens(text: str) -> List[str]:
    return _WORD.findall(text.lower())


def ngram_overlap(reference: str, completion: str, n: int = 5) -> float:
    """Fraction of the reference's word n-grams that appear in the completion."""
    r, c = tokens(reference), tokens(completion)
    if len(r) < n:
        return float(" ".join(r) in " ".join(c)) if r else 0.0
    ref = {tuple(r[i:i + n]) for i in range(len(r) - n + 1)}
    com = {tuple(c[i:i + n]) for i in range(len(c) - n + 1)}
    return len(ref & com) / len(ref)


@dataclass
class ProbeResult:
    item: int
    overlap: float
    memorised: bool


def memorisation_probe(model: Callable[[str], str], documents: Sequence[str], *, prefix_fraction: float = 0.5,
                       n: int = 5, threshold: float = 0.3) -> List[ProbeResult]:
    """`model(prompt) -> completion`. You supply the model call; nothing here talks to an API."""
    out = []
    for i, doc in enumerate(documents):
        words = doc.split()
        k = max(1, int(len(words) * prefix_fraction))
        prompt = " ".join(words[:k])
        reference = " ".join(words[k:])
        completion = model(
            "Continue this text exactly as it appears in its original source. Do not paraphrase.\n\n" + prompt)
        ov = ngram_overlap(reference, completion, n)
        out.append(ProbeResult(i, ov, ov >= threshold))
    return out
