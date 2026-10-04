"""Project configuration (oguard.yaml) with safe defaults."""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

CONFIG_NAMES = ("oguard.yaml", "oguard.yml", ".oguard.yaml")

DEFAULTS: Dict[str, Any] = {
    "project": "unnamed-study",
    # Prediction time: information must have existed before this instant.
    # Individual prediction events may carry their own `as_of`.
    "as_of": None,
    # Training cut-off of the language model(s) the agent uses, if known.
    "model_training_cutoff": None,
    "ledger": ".oguard/ledger.jsonl",
    "evidence_dir": ".oguard",
    # Paths an agent must never read (outcomes, holdout labels, answer keys).
    "sealed_paths": ["data/holdout/**", "data/outcomes/**", "**/*.answers.*"],
    # URL or source patterns that are known to publish outcomes (regular expressions).
    "blocked_sources": [],
    # What to do with information whose date is missing or straddles the cut-off.
    "missing_date_policy": "warn",  # reject | warn | allow
    "budget": {"test_looks": 1},
    "controls": {"permutations": 200, "tolerance": 0.05, "chance": None},
    "splits": {"similarity_threshold": 0.9, "max_fraction_above": 0.0},
    "ceiling": {"replicate_agreement": None, "test_retest_r": None},
    "judge": {"require_different_model": True},
    # Treat everything an agent retrieved or ran before a prediction as an ancestor of it.
    "context_is_ancestor": True,
}


def _merge(base: Dict[str, Any], over: Dict[str, Any]) -> Dict[str, Any]:
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def find_config(start: Optional[Path] = None) -> Optional[Path]:
    """Walk up from `start` (default: cwd) to find an oguard config file."""
    here = (start or Path.cwd()).resolve()
    for d in [here, *here.parents]:
        for name in CONFIG_NAMES:
            p = d / name
            if p.is_file():
                return p
    return None


def load_config(path: Optional[Path] = None) -> Dict[str, Any]:
    """Load config merged over defaults. `_root` is the directory holding the config."""
    p = Path(path) if path else find_config()
    data: Dict[str, Any] = {}
    root = Path.cwd()
    if p is not None and p.is_file():
        data = yaml.safe_load(p.read_text()) or {}
        root = p.parent
    cfg = _merge(DEFAULTS, data)
    cfg["_root"] = str(root.resolve())
    cfg["_config_path"] = str(p) if p else None
    return cfg


def resolve(cfg: Dict[str, Any], rel: str) -> Path:
    p = Path(rel)
    return p if p.is_absolute() else Path(cfg["_root"]) / p


TEMPLATE = """\
# ouroboros-guard configuration. See docs/ARCHITECTURE.md for every field.
project: my-study

# Prediction time. Every input an agent uses must have existed before this instant.
# Individual predictions can override it with their own `as_of`.
as_of: 2026-01-01T00:00:00Z

# Training cut-off of the language model(s) in the loop, if known. Outcomes published
# before this date may be memorised, so evaluations on them test recall.
model_training_cutoff: null

ledger: .oguard/ledger.jsonl

# Paths that hold outcomes, holdout labels or answer keys. Agents must never read them.
sealed_paths:
  - data/holdout/**
  - data/outcomes/**
  - "**/*.answers.*"

# Regular expressions for sources that publish the outcomes you are predicting.
blocked_sources: []

# reject | warn | allow : information with no date, or a date that straddles as_of.
missing_date_policy: warn

budget:
  test_looks: 1          # how many times anyone may score against the final test set

controls:
  permutations: 200      # scrambled-label runs for the negative control
  tolerance: 0.05        # how far above chance a scrambled run may score before we call it a leak
  chance: null           # null = majority-class rate, computed from the labels

splits:
  similarity_threshold: 0.9   # a test item this similar to a training item counts as a near-duplicate
  max_fraction_above: 0.0

ceiling:
  replicate_agreement: null   # binary outcomes: how often two runs of the same experiment agree
  test_retest_r: null         # continuous outcomes: correlation between two runs

judge:
  require_different_model: true

# An LLM agent's context window is shared: anything it retrieved or ran before a prediction
# could have influenced it. Keep this on unless predictions are made in fresh, isolated contexts.
context_is_ancestor: true
"""
