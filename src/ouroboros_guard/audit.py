"""The Ouroboros audit: ten questions, answered from evidence on disk.

Each answer is pass, fail, warn or unknown. "unknown" is an honest answer:
it means nothing in the ledger or the evidence directory speaks to the
question yet, and it tells you what to add.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List

from .ceiling import check_claim
from .config import resolve
from .graph import Finding, InfoGraph
from .ledger import Ledger
from .timeutil import is_before

QUESTIONS = [
    "Could the outcome have been known, anywhere, before the prediction was fixed?",
    "Was the outcome, or anything written about it, published before the model's training cut-off?",
    "Does every tool have an as-of date, and is every retrieved document logged with its date?",
    "Could each input have been recorded before the outcome existed?",
    "Are test items separated from training items by group or by time rather than at random?",
    "How many times has anyone, or any agent, looked at the test score?",
    "Is the judge independent of the generator, in model and in information?",
    "Are repeated reports of a single result counted once?",
    "Does the whole pipeline fall to chance on scrambled labels and masked identities?",
    "Is the reported accuracy below the replicate ceiling of the measurement?",
]


@dataclass
class Answer:
    q: int
    question: str
    status: str  # pass | warn | fail | unknown
    evidence: str


def _codes(findings: List[Finding], *codes: str) -> List[Finding]:
    return [f for f in findings if f.code.split("-")[0] in codes]


def run_audit(cfg: Dict[str, Any]) -> Dict[str, Any]:
    ledger = Ledger(resolve(cfg, cfg["ledger"]))
    events = ledger.read()
    chain = ledger.verify_chain()
    g = InfoGraph(events, context_is_ancestor=cfg.get("context_is_ancestor", True))
    findings = g.check_all(default_as_of=cfg.get("as_of"), missing_date_policy=cfg.get("missing_date_policy", "warn"),
                           look_budget=(cfg.get("budget") or {}).get("test_looks"),
                           require_different_judge=(cfg.get("judge") or {}).get("require_different_model", True))
    evdir = resolve(cfg, cfg.get("evidence_dir", ".oguard"))
    by_type: Dict[str, List[Any]] = {}
    for e in events:
        by_type.setdefault(e.type, []).append(e)
    preds = by_type.get("prediction", [])
    answers: List[Answer] = []

    def add(i: int, status: str, evidence: str) -> None:
        answers.append(Answer(i, QUESTIONS[i - 1], status, evidence))

    # Q1
    bad = _codes(findings, "G1", "G3", "G6")
    if bad:
        add(1, "fail", "; ".join(f.message for f in bad[:3]))
    elif not preds:
        add(1, "unknown", "No predictions in the ledger. Log them with `oguard log prediction --target ...`.")
    else:
        uncommitted = _codes(findings, "G5")
        add(1, "warn" if uncommitted else "pass",
            f"{len(preds)} prediction(s); no outcome or future information among their ancestors"
            + (f"; {len(uncommitted)} not committed before their outcome appeared" if uncommitted else "."))

    # Q2
    cutoff = cfg.get("model_training_cutoff")
    outs = by_type.get("outcome", [])
    if not cutoff:
        add(2, "unknown", "Set `model_training_cutoff` in oguard.yaml to test whether outcomes could be memorised.")
    elif not outs:
        add(2, "unknown", "No outcomes in the ledger yet.")
    else:
        pub = [o for o in outs if is_before(o.meta.get("published_at") or o.available_at, cutoff) is not False]
        status = "pass" if not pub else "warn"
        add(2, status, f"{len(pub)} of {len(outs)} outcome(s) were (or may have been) public before the model's "
                       f"training cut-off {cutoff}. Scores on those measure recall, not prediction."
            if pub else f"All {len(outs)} outcome(s) were published after the training cut-off {cutoff}.")

    # Q3
    rets = by_type.get("retrieval", [])
    undated = [r for r in rets if not r.available_at]
    if not rets:
        add(3, "unknown", "No retrievals logged. If the agent used search or RAG, route it through the firewall or the hooks.")
    else:
        add(3, "pass" if not undated else "warn",
            f"{len(rets)} retrieval(s) logged; {len(undated)} without a date"
            + (f"; firewall as_of = {cfg.get('as_of')}" if cfg.get("as_of") else "; no as_of configured"))

    # Q4
    inputs = by_type.get("input", [])
    future = [f for f in _codes(findings, "G3") if any(n.startswith("input") for n in f.nodes)]
    undated_in = [i for i in inputs if not i.available_at]
    if future:
        add(4, "fail", "; ".join(f.message for f in future[:3]))
    elif not inputs:
        add(4, "unknown", "No inputs registered. Log each dataset with `oguard log input --available-at ...`.")
    else:
        add(4, "warn" if undated_in else "pass",
            f"{len(inputs)} input(s); {len(undated_in)} without an availability date.")

    # Q5
    split = evdir / "split_report.json"
    if split.exists():
        s = json.loads(split.read_text())
        add(5, "fail" if s.get("leak_suspected") else "pass",
            f"{s['fraction_above']:.1%} of test items have a training neighbour with {s['metric']} similarity "
            f">= {s['threshold']} (max {s['max']:.2f}).")
    else:
        add(5, "unknown", "Run `oguard split-audit` on your train and test items.")

    # Q6
    looks = by_type.get("look", [])
    over = _codes(findings, "G8")
    budget = (cfg.get("budget") or {}).get("test_looks")
    if over:
        add(6, "fail" if any(f.severity == "critical" for f in over) else "warn", "; ".join(f.message for f in over))
    elif looks:
        add(6, "pass", f"{len(looks)} look(s) at evaluation sets, within the budget of {budget} per set.")
    else:
        add(6, "unknown", "No looks logged. Score the test set through HoldoutGuard or log each look.")

    # Q7
    judges = by_type.get("judge", [])
    selfg = _codes(findings, "G9")
    if selfg:
        add(7, "warn", "; ".join(f.message for f in selfg[:3]))
    elif judges:
        add(7, "pass", f"{len(judges)} judge verdict(s), none from the generating model.")
    else:
        add(7, "unknown", "No judge events logged.")

    # Q8
    echo = _codes(findings, "G10")
    with_origin = [r for r in rets if r.meta.get("origin")]
    if echo:
        add(8, "warn", "; ".join(f.message for f in echo[:3]))
    elif with_origin:
        add(8, "pass", f"{len(with_origin)} retrieval(s) carry an origin id; no origin is counted twice.")
    else:
        add(8, "unknown", "Record `origin` (the original study or dataset) on retrievals to detect citation echo.")

    # Q9
    ctrl = sorted((evdir / "controls").glob("*.json")) if (evdir / "controls").exists() else []
    if ctrl:
        res = [json.loads(p.read_text()) for p in ctrl]
        leaks = [r for r in res if r.get("leak_suspected")]
        add(9, "fail" if leaks else "pass",
            f"{len(res)} control(s); " + ("; ".join(f"{r['name']}: scrambled mean {r['null_mean']:.3f} vs chance "
                                                     f"{r['chance']}" for r in leaks) if leaks else "all fell to chance."))
    else:
        add(9, "unknown", "Run `oguard control` (or permutation_control in Python) on the whole pipeline.")

    # Q10
    metrics = evdir / "metrics.json"
    ceil = cfg.get("ceiling") or {}
    if metrics.exists() and (ceil.get("replicate_agreement") or ceil.get("test_retest_r")):
        m = json.loads(metrics.read_text())
        c = check_claim(float(m["value"]), replicate_agreement=ceil.get("replicate_agreement"),
                        test_retest_r=ceil.get("test_retest_r"))
        add(10, "fail" if c.suspicious else "pass", c.describe())
    else:
        add(10, "unknown", "Write .oguard/metrics.json ({\"value\": ...}) and set a ceiling in oguard.yaml.")

    status = "fail" if chain or any(a.status == "fail" for a in answers) else (
        "warn" if any(a.status == "warn" for a in answers) else "pass")
    return {
        "project": cfg.get("project"),
        "status": status,
        "ledger_integrity": chain or "intact",
        "answers": [asdict(a) for a in answers],
        "findings": [f.as_dict() for f in findings],
    }


ICON = {"pass": "PASS", "warn": "WARN", "fail": "FAIL", "unknown": "  ? "}


def to_markdown(report: Dict[str, Any]) -> str:
    lines = [f"# Ouroboros audit: {report['project']}", "",
             f"**Overall: {report['status'].upper()}**", ""]
    integ = report["ledger_integrity"]
    lines.append(f"Ledger integrity: {'intact' if integ == 'intact' else 'BROKEN: ' + '; '.join(integ)}")
    lines += ["", "| # | Question | Status | Evidence |", "|---|---|---|---|"]
    for a in report["answers"]:
        ev = a["evidence"].replace("|", "\\|")
        lines.append(f"| {a['q']} | {a['question']} | {a['status']} | {ev} |")
    if report["findings"]:
        lines += ["", "## Findings", ""]
        for f in report["findings"]:
            lines.append(f"- **{f['severity']}** `{f['code']}`: {f['message']}")
    return "\n".join(lines) + "\n"


def to_text(report: Dict[str, Any]) -> str:
    out = [f"Ouroboros audit: {report['project']}  ->  {report['status'].upper()}"]
    for a in report["answers"]:
        out.append(f" [{ICON[a['status']]}] {a['q']:>2}. {a['question']}\n         {a['evidence']}")
    return "\n".join(out)
