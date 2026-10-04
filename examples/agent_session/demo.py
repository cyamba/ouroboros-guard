"""Two agent sessions, one honest and one leaky, written to ledgers and checked.

    python examples/agent_session/demo.py

The leaky agent searched the literature after the prediction time and its search returned
a paper reporting the very outcome it was asked to predict. The honest agent worked only
from inputs dated before the prediction time, committed its prediction, and only then was
the outcome revealed.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from ouroboros_guard.graph import InfoGraph
from ouroboros_guard.ledger import Ledger

AS_OF = "2026-03-01T00:00:00Z"


def honest(led: Ledger) -> None:
    d = led.append("input", id="input:assay-table", available_at="2026-01-15", source="data/inputs/assay_v3.csv")
    r = led.append("retrieval", id="retrieval:review-2025", available_at="2025-06", source="doi:10.0000/review.2025",
                   meta={"origin": "review-2025"})
    f = led.append("derive", id="derive:features", parents=[d.id], available_at="2026-02-01")
    p = led.append("prediction", id="prediction:E-12", parents=[f.id, r.id], target="E-12",
                   meta={"as_of": AS_OF, "model": "model-A"}, t="2026-02-20T10:00:00Z")
    led.append("commit", id="commit:batch-1", parents=[p.id], t="2026-02-20T10:05:00Z", meta={"digest": "…"})
    led.append("outcome", id="outcome:E-12", target="E-12", t="2026-04-02T09:00:00Z", available_at="2026-04-02")
    led.append("judge", id="judge:E-12", parents=[p.id], meta={"model": "model-B"})


def leaky(led: Ledger) -> None:
    d = led.append("input", id="input:assay-table", available_at="2026-01-15", source="data/inputs/assay_v3.csv")
    # the agent searched, and the search engine returned the paper that reports E-12's result
    led.append("retrieval", id="retrieval:results-paper", available_at="2026-04-10", source="doi:10.0000/results.2026",
               meta={"origin": "E-12-study"}, t="2026-04-11T08:00:00Z")
    led.append("retrieval", id="retrieval:press-release", available_at="2026-04-12", source="https://example.org/news",
               meta={"origin": "E-12-study"}, t="2026-04-12T08:00:00Z")
    o = led.append("outcome", id="outcome:E-12", target="E-12", t="2026-04-02T09:00:00Z", available_at="2026-04-02")
    p = led.append("prediction", id="prediction:E-12", parents=[d.id], target="E-12",
                   meta={"as_of": AS_OF, "model": "model-A"}, t="2026-04-12T09:00:00Z")
    led.append("commit", id="commit:batch-1", parents=[p.id], t="2026-04-12T09:05:00Z")
    led.append("judge", id="judge:E-12", parents=[p.id], meta={"model": "model-A"})


def run(name, builder):
    with tempfile.TemporaryDirectory() as tmp:
        led = Ledger(Path(tmp) / "ledger.jsonl")
        builder(led)
        findings = InfoGraph(led.read()).check_all(look_budget=1)
        print(f"\n== {name} session: {len(findings)} finding(s)")
        for f in findings:
            print(f"  [{f.severity:8}] {f.code}: {f.message}")
        return findings


if __name__ == "__main__":
    run("honest", honest)
    run("leaky", leaky)
