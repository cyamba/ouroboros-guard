import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from ouroboros_guard.budget import BudgetExceeded, HoldoutGuard
from ouroboros_guard.contamination import memorisation_probe, ngram_overlap
from ouroboros_guard.controls import command_control, mask_entities, permutation_control, temporal_gap
from ouroboros_guard.lean import audit_axioms, parse_print_axioms
from ouroboros_guard.proofs import check_proof, load_proof
from ouroboros_guard.splits import audit_split, group_overlap, group_split, nearest_similarity, time_split

ROOT = Path(__file__).resolve().parents[1]
EX = ROOT / "examples"
sys.path.insert(0, str(EX / "feature_selection_leak"))


# ---------------------------------------------------------------- negative controls
def test_feature_selection_leak_is_caught():
    import run as fsl  # examples/feature_selection_leak/run.py
    res = fsl.main(runs=30)
    assert res["selection-before-split"].leak_suspected
    assert not res["selection-inside-folds"].leak_suspected


def test_permutation_control_honest_pipeline():
    rng = np.random.default_rng(0)
    X = rng.standard_normal((200, 3))
    y = (X[:, 0] > 0).astype(int)

    def pipe(X, y):  # nearest-mean on the first half, scored on the second half
        tr, te = slice(0, 100), slice(100, 200)
        m1, m0 = X[tr][y[tr] == 1].mean(0), X[tr][y[tr] == 0].mean(0)
        pred = (((X[te] - m1) ** 2).sum(1) < ((X[te] - m0) ** 2).sum(1)).astype(int)
        return float(np.mean(pred == y[te]))

    r = permutation_control(pipe, X, y, runs=50)
    assert not r.leak_suspected and r.real_score > 0.8 and r.p_value < 0.05


def test_command_control(tmp_path):
    labels = tmp_path / "labels.csv"
    labels.write_text("id,label\n" + "\n".join(f"r{i},{i % 2}" for i in range(40)) + "\n")
    # a "program" that cheats by reading the labels file and scoring itself against it
    prog = tmp_path / "cheat.py"
    prog.write_text("import sys\nrows=open(sys.argv[1]).read().split()[1:]\nprint('score', 1.0)\n")
    r = command_control(f"{sys.executable} {prog} {{labels}}", labels, runs=5)
    assert r.leak_suspected and r.real_score == 1.0


def test_mask_entities_and_temporal_gap():
    texts, mapping = mask_entities(["Compound Alpha-7 inhibits KX1; alpha-7 is potent."], ["Alpha-7", "KX1"])
    assert "Alpha-7" not in texts[0] and "alpha-7" not in texts[0] and mapping["KX1"].startswith("ENTITY_")
    rng = np.random.default_rng(1)
    dates = ["2023-05-01"] * 300 + ["2025-05-01"] * 300
    correct = list(rng.random(300) < 0.95) + list(rng.random(300) < 0.6)
    gap = temporal_gap(correct, dates, "2024-01-01")
    assert gap.memorisation_suspected and gap.gap > 0.25


# ---------------------------------------------------------------- splits
def test_split_audit_finds_near_duplicates():
    train = ["the quick brown fox jumps", "lorem ipsum dolor sit amet", "a b c d e f g"]
    test = ["the quick brown fox jumps!", "completely different sentence here"]
    rep = audit_split(train, test, threshold=0.8)
    assert rep.leak_suspected and rep.fraction_above == 0.5
    vecs = np.eye(4)
    assert np.allclose(nearest_similarity(vecs, vecs[:2], "cosine"), 1)
    bits = np.array([[1, 1, 0, 0], [0, 0, 1, 1]])
    assert np.allclose(nearest_similarity(bits, np.array([[1, 1, 0, 0]]), "tanimoto"), 1)


def test_group_and_time_splits():
    groups = ["a"] * 5 + ["b"] * 5 + ["c"] * 5 + ["d"] * 5
    mask = group_split(groups, 0.25, seed=3)
    test_groups = {g for g, m in zip(groups, mask) if m}
    train_groups = {g for g, m in zip(groups, mask) if not m}
    assert len(test_groups) == 1 and not group_overlap(train_groups, test_groups)["leak_suspected"]
    assert list(time_split(["2020", "2024", "2024-06-15"], "2024-06-01")) == [False, True, True]


# ---------------------------------------------------------------- budget
def test_holdout_guard_strict_and_thresholdout():
    y = np.array([0, 1] * 50)
    acc = lambda yt, yp: float(np.mean(np.asarray(yt) == np.asarray(yp)))  # noqa: E731
    g = HoldoutGuard(acc, y, budget=1)
    g.score(y)
    with pytest.raises(BudgetExceeded):
        g.score(y)
    t = HoldoutGuard(acc, y, budget=5, mode="thresholdout", seed=0)
    noise = np.random.default_rng(0).integers(0, 2, 100)
    # training score close to the holdout score -> the training score is returned and no budget is spent
    assert t.score(noise, train_score=acc(y, noise)) == acc(y, noise) and t.spent == 0
    # a training score far above the holdout score reveals overfitting and spends budget
    t.score(noise, train_score=0.99)
    assert t.spent == 1


# ---------------------------------------------------------------- proofs and Lean
@pytest.mark.parametrize("name,valid,codes", [
    ("sinx_lhopital.yaml", False, {"P1", "P2"}),
    ("sinx_squeeze.yaml", True, set()),
    ("parallel_wallis.yaml", False, {"P2", "P6"}),
    ("minus_one_equals_one.yaml", False, {"P1", "P4"}),
])
def test_proof_examples(name, valid, codes):
    rep = check_proof(load_proof(EX / "proofs" / name))
    assert rep.valid is valid
    assert codes <= {f.code.split("-")[0] for f in rep.findings}


def test_unjustified_and_dangling():
    rep = check_proof({"goal": "g", "statements": [
        {"id": "g", "kind": "goal", "uses": ["l", "ghost"]},
        {"id": "l", "kind": "lemma"},
    ]})
    codes = {f.code.split("-")[0] for f in rep.findings}
    assert {"P3", "P5"} <= codes and not rep.valid


def test_lean_axiom_audit():
    text = (EX / "lean" / "print_axioms_output.txt").read_text()
    parsed = parse_print_axioms(text)
    assert parsed["Demo.main_theorem"] == ["propext", "sorryAx", "Classical.choice", "Quot.sound"]
    assert parsed["Demo.trivial_fact"] == []
    codes = {f.code.split("-")[0] for r in audit_axioms(text) for f in r.findings}
    assert codes == {"L1", "L2", "L3"}


# ---------------------------------------------------------------- contamination
def test_memorisation_probe():
    doc = "the measured melting point of the sample was four hundred and twelve kelvin under standard pressure"
    parrot = lambda prompt: doc  # noqa: E731
    fresh = lambda prompt: "no idea what comes next in this text"  # noqa: E731
    assert memorisation_probe(parrot, [doc])[0].memorised
    assert not memorisation_probe(fresh, [doc])[0].memorised
    assert ngram_overlap("a b c d e f", "a b c d e f") == 1.0


# ---------------------------------------------------------------- hooks
def _hook(mode, event, cwd):
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(cwd)}
    return subprocess.run([sys.executable, str(ROOT / "hooks" / "claude" / "guard.py"), mode],
                          input=json.dumps(event), capture_output=True, text=True, env=env, cwd=cwd)


def test_claude_hook_blocks_sealed_paths(tmp_path):
    (tmp_path / "oguard.yaml").write_text(
        "sealed_paths:\n  - data/holdout/**\nblocked_sources:\n  - 'results\\.example\\.org'\n")
    (tmp_path / "data" / "holdout").mkdir(parents=True)
    (tmp_path / "data" / "holdout" / "y.csv").write_text("1\n")
    r = _hook("pre", {"tool_name": "Read", "tool_input": {"file_path": str(tmp_path / "data/holdout/y.csv")}}, tmp_path)
    assert r.returncode == 2 and "sealed" in r.stderr
    r = _hook("pre", {"tool_name": "Read", "tool_input": {"file_path": str(tmp_path / "README.md")}}, tmp_path)
    assert r.returncode == 0
    r = _hook("pre", {"tool_name": "Bash", "tool_input": {"command": "cat data/holdout/y.csv"}}, tmp_path)
    assert r.returncode == 2
    r = _hook("pre", {"tool_name": "Grep", "tool_input": {"pattern": "x"}}, tmp_path)
    assert r.returncode == 2
    r = _hook("pre", {"tool_name": "Grep", "tool_input": {"pattern": "x", "path": "src"}}, tmp_path)
    assert r.returncode == 0
    r = _hook("pre", {"tool_name": "WebFetch", "tool_input": {"url": "https://results.example.org/2026"}}, tmp_path)
    assert r.returncode == 2


def test_claude_hook_logs_and_stops(tmp_path):
    (tmp_path / "oguard.yaml").write_text("as_of: 2026-06-01\nsealed_paths: []\n")
    r = _hook("post", {"tool_name": "WebFetch", "session_id": "s1", "tool_input": {"url": "https://example.org/a"}},
              tmp_path)
    assert r.returncode == 0
    ledger = (tmp_path / ".oguard" / "ledger.jsonl").read_text().splitlines()
    assert json.loads(ledger[0])["type"] == "retrieval"
    # a leak in the ledger makes the Stop hook refuse once, then let go
    from ouroboros_guard.ledger import Ledger
    led = Ledger(tmp_path / ".oguard" / "ledger.jsonl")
    led.append("outcome", id="outcome:x", target="x")
    led.append("prediction", id="prediction:x", parents=["outcome:x"], target="x")
    assert _hook("stop", {}, tmp_path).returncode == 2
    assert _hook("stop", {"stop_hook_active": True}, tmp_path).returncode == 0
