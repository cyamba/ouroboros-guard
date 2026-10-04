"""ouroboros-guard: leakage and circularity guardrails for agentic science, math and engineering.

The one rule: the outcome must never be an ancestor of the prediction,
and every check you report must have been able to fail.
"""

__version__ = "0.1.0"

from .timeutil import parse_when, Interval  # noqa: F401
from .ledger import Ledger, Event  # noqa: F401
from .graph import InfoGraph, Finding  # noqa: F401
from .firewall import TimeFirewall, Decision  # noqa: F401
from .commit import commit_payload, verify_payload  # noqa: F401
from .evidence import bayes_factor, weight_of_evidence_bits, posterior_probability  # noqa: F401
from .ceiling import binary_accuracy_ceiling, correlation_ceiling  # noqa: F401
