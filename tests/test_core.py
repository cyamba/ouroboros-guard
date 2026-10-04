import json
from pathlib import Path

import numpy as np
import pytest

from ouroboros_guard.timeutil import is_before, parse_when
from ouroboros_guard.ledger import Ledger
from ouroboros_guard.graph import InfoGraph
from ouroboros_guard.firewall import TimeFirewall
from ouroboros_guard.commit import commit_payload, verify_payload, commit_file, verify_file
from ouroboros_guard.evidence import assess_check, bayes_factor, posterior_probability, weight_of_evidence_bits
from ouroboros_guard.ceiling import binary_accuracy_ceiling, check_claim, correlation_ceiling


# ---------------------------------------------------------------- time
def test_partial_dates_are_intervals():
    assert is_before("2024", "2025-01-01") is True
    assert is_before("2025", "2025-01-01") is False
    assert is_before("2024", "2024-06-01") is None          # straddles
    assert is_before("2024-05", "2024-06-01T00:00:00Z") is True
    assert is_before(None, "2024-06-01") is None
    assert parse_when("2024-02").end.month == 3


def test_is_before_instants():
    assert is_before("2026-01-01T10:00:00Z", "2026-01-01T10:00:01Z") is True
    assert is_before("2026-01-01T10:00:01Z", "2026-01-01T10:00:00Z") is False


# ---------------------------------------------------------------- ledger
def test_ledger_chain_detects_edits(tmp_path):
    led = Ledger(tmp_path / "l.jsonl")
    led.append("input", id="input:a", available_at="2025-01-01")
    led.append("prediction", id="prediction:x", parents=["input:a"], target="x")
    assert led.verify_chain() == []
    lines = led.path.read_text().splitlines()
    rec = json.loads(lines[0]); rec["available_at"] = "2027-01-01"
    lines[0] = json.dumps(rec)
    led.path.write_text("\n".join(lines) + "\n")
    problems = led.verify_chain()
    assert any("edited" in p for p in problems)


def test_ledger_rejects_unknown_type_and_duplicate_id(tmp_path):
    led = Ledger(tmp_path / "l.jsonl")
    with pytest.raises(ValueError):
        led.append("gossip")
    led.append("note", id="note:1")
    with pytest.raises(ValueError):
        led.append("note", id="note:1")


# ---------------------------------------------------------------- graph
def _codes(findings):
    return {f.code.split("-")[0] for f in findings}


def test_outcome_as_ancestor_is_critical(tmp_path):
    led = Ledger(tmp_path / "l.jsonl")
    led.append("outcome", id="outcome:x", target="x", available_at="2026-05-01")
    led.append("derive", id="derive:summary", parents=["outcome:x"])
    led.append("prediction", id="prediction:x", parents=["derive:summary"], target="x", meta={"as_of": "2026-06-01"})
    f = InfoGraph(led.read()).check_all()
    g1 = [x for x in f if x.code.startswith("G1")]
    assert g1 and g1[0].severity == "critical"
    assert "outcome:x -> derive:summary -> prediction:x" in g1[0].message


def test_training_labels_are_legitimate_ancestors(tmp_path):
    led = Ledger(tmp_path / "l.jsonl")
    led.append("label", id="label:train", available_at="2025-01-01")
    led.append("prediction", id="prediction:x", parents=["label:train"], target="x", meta={"as_of": "2026-01-01"})
    assert InfoGraph(led.read()).check_all() == []


def test_future_ancestor_and_commit_after_outcome(tmp_path):
    led = Ledger(tmp_path / "l.jsonl")
    led.append("input", id="input:late", available_at="2026-07-01")
    led.append("outcome", id="outcome:x", target="x", t="2026-06-15T00:00:00Z")
    led.append("prediction", id="prediction:x", parents=["input:late"], target="x", meta={"as_of": "2026-06-01"})
    led.append("commit", id="commit:1", parents=["prediction:x"], t="2026-06-20T00:00:00Z")
    codes = _codes(InfoGraph(led.read()).check_all())
    assert {"G3", "G6"} <= codes


def test_context_window_is_ancestor(tmp_path):
    led = Ledger(tmp_path / "l.jsonl")
    led.append("retrieval", id="retrieval:spoiler", available_at="2026-08-01", source="https://example.org/results")
    led.append("prediction", id="prediction:x", target="x", meta={"as_of": "2026-06-01"})
    assert "G3" in _codes(InfoGraph(led.read()).check_all())
    # a prediction made in an isolated, explicitly-specified context is not tainted by earlier retrievals
    led2 = Ledger(tmp_path / "l2.jsonl")
    led2.append("retrieval", id="retrieval:spoiler", available_at="2026-08-01")
    led2.append("prediction", id="prediction:x", target="x", meta={"as_of": "2026-06-01", "context": "isolated"})
    assert InfoGraph(led2.read()).check_all() == []


def test_cycle_detection(tmp_path):
    led = Ledger(tmp_path / "l.jsonl")
    led.append("derive", id="derive:a", parents=["derive:b"])
    led.append("derive", id="derive:b", parents=["derive:a"])
    assert "G7" in _codes(InfoGraph(led.read()).check_all())


def test_look_budget_and_self_grading(tmp_path):
    led = Ledger(tmp_path / "l.jsonl")
    led.append("prediction", id="prediction:x", target="x", meta={"model": "m1"})
    for _ in range(5):
        led.append("look", target="test", meta={"set": "test"})
    led.append("judge", id="judge:x", parents=["prediction:x"], meta={"model": "m1"})
    codes = _codes(InfoGraph(led.read()).check_all(look_budget=1))
    assert {"G8", "G9"} <= codes


def test_undated_retrieval_policy(tmp_path):
    led = Ledger(tmp_path / "l.jsonl")
    led.append("retrieval", id="retrieval:nodate", source="search: something")
    led.append("prediction", id="prediction:x", target="x", meta={"as_of": "2026-06-01"})
    g = InfoGraph(led.read())
    warn = [f for f in g.check_all(missing_date_policy="warn") if f.code.startswith("G2")]
    crit = [f for f in g.check_all(missing_date_policy="reject") if f.code.startswith("G2")]
    assert warn[0].severity == "warn" and crit[0].severity == "critical"
    assert not [f for f in g.check_all(missing_date_policy="allow") if f.code.startswith("G2")]


# ---------------------------------------------------------------- firewall
def test_firewall_dates_and_sources(tmp_path):
    led = Ledger(tmp_path / "l.jsonl")
    fw = TimeFirewall("2024-06-01", missing_date_policy="reject", blocked_sources=[r"answers\.example"], ledger=led)
    items = [
        {"title": "old", "published_at": "2023-11-02"},
        {"title": "new", "published_at": "2024-07-01"},
        {"title": "fuzzy", "year": 2024},
        {"title": "nodate"},
        {"title": "leak", "url": "https://answers.example/q1", "published_at": "2020"},
    ]
    kept = fw.filter(items)
    assert [k["title"] for k in kept] == ["old"]
    assert len(led.read()) == 1 and led.read()[0].type == "retrieval"
    warn_fw = TimeFirewall("2024-06-01", missing_date_policy="warn", blocked_sources=[r"answers\.example"])
    assert {k["title"] for k in warn_fw.filter(items)} == {"old", "fuzzy", "nodate"}


# ---------------------------------------------------------------- commit / reveal
def test_commit_reveal_roundtrip(tmp_path):
    c = commit_payload({"E-12": "active", "p": 0.81})
    assert verify_payload({"p": 0.81, "E-12": "active"}, c.salt, c.digest)  # key order does not matter
    assert not verify_payload({"E-12": "inactive", "p": 0.81}, c.salt, c.digest)
    f = tmp_path / "preds.jsonl"
    f.write_text('{"target": "E-12", "y_hat": 1}\n')
    commit_file(f)
    assert verify_file(f)
    f.write_text('{"target": "E-12", "y_hat": 0}\n')
    assert not verify_file(f)


# ---------------------------------------------------------------- evidence and ceilings
def test_circular_check_carries_zero_bits():
    r = assess_check(1.0, 1.0, prior=0.2)
    assert r.verdict == "circular" and r.bits == 0 and abs(r.posterior - 0.2) < 1e-12
    k = bayes_factor(0.9, 0.1)
    assert abs(k - 9) < 1e-12 and abs(weight_of_evidence_bits(k) - 3.1699) < 1e-3
    assert abs(posterior_probability(0.2, k) - 0.6923) < 1e-3


def test_ceilings():
    assert abs(binary_accuracy_ceiling(0.82) - 0.90) < 1e-9
    assert binary_accuracy_ceiling(1.0) == 1.0
    assert abs(correlation_ceiling(0.81) - 0.9) < 1e-12
    assert check_claim(0.97, replicate_agreement=0.82).suspicious
    assert not check_claim(0.88, replicate_agreement=0.82).suspicious
    # Monte Carlo: a model that knows the truth matches a noisy replicate at the ceiling
    rng = np.random.default_rng(0)
    q = 0.9
    truth = rng.integers(0, 2, 200_000)
    r1 = np.where(rng.random(truth.size) < q, truth, 1 - truth)
    r2 = np.where(rng.random(truth.size) < q, truth, 1 - truth)
    a = np.mean(r1 == r2)
    assert abs(binary_accuracy_ceiling(a) - np.mean(truth == r1)) < 0.005
