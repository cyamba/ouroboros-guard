"""oguard: command-line interface. Every command exits 1 when it finds a critical problem."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

from . import __version__
from .audit import run_audit, to_markdown, to_text
from .ceiling import binary_accuracy_ceiling, check_claim, correlation_ceiling
from .commit import commit_file, verify_file
from .config import TEMPLATE, load_config, resolve
from .controls import command_control
from .evidence import assess_check
from .firewall import TimeFirewall
from .graph import InfoGraph
from .lean import audit_axioms
from .ledger import EVENT_TYPES, Ledger, sha256_file
from .proofs import check_proof, load_proof
from .splits import audit_split


def _meta(pairs: List[str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for p in pairs or []:
        if "=" not in p:
            raise SystemExit(f"--meta expects key=value, got {p!r}")
        k, v = p.split("=", 1)
        try:
            out[k] = json.loads(v)
        except json.JSONDecodeError:
            out[k] = v
    return out


def _ledger(cfg) -> Ledger:
    return Ledger(resolve(cfg, cfg["ledger"]))


def cmd_init(a, cfg) -> int:
    p = Path("oguard.yaml")
    if p.exists() and not a.force:
        print("oguard.yaml already exists (use --force to overwrite)", file=sys.stderr)
        return 2
    p.write_text(TEMPLATE)
    Path(".oguard").mkdir(exist_ok=True)
    gi = Path(".gitignore")
    lines = gi.read_text().splitlines() if gi.exists() else []
    if "*.salt" not in lines:
        gi.write_text("\n".join(lines + ["# ouroboros-guard: keep commitment salts private until the reveal", "*.salt"]) + "\n")
    print("Wrote oguard.yaml and .oguard/. Salts (*.salt) are git-ignored until you reveal.")
    return 0


def cmd_log(a, cfg) -> int:
    sha = sha256_file(a.file) if a.file else None
    ev = _ledger(cfg).append(a.type, id=a.id, parents=a.parent, available_at=a.available_at, target=a.target,
                             source=a.source or (str(a.file) if a.file else None), content_sha256=sha, meta=_meta(a.meta))
    print(ev.id)
    return 0


def _print_findings(findings, as_json: bool) -> int:
    if as_json:
        print(json.dumps([f.as_dict() for f in findings], indent=2))
    elif not findings:
        print("No findings: the information graph is acyclic and no prediction can see its outcome.")
    else:
        for f in findings:
            print(f"[{f.severity:8}] {f.code}: {f.message}")
    return 1 if any(f.severity == "critical" for f in findings) else 0


def cmd_check(a, cfg) -> int:
    led = _ledger(cfg)
    problems = led.verify_chain()
    for p in problems:
        print(f"[critical] ledger: {p}")
    g = InfoGraph(led.read(), context_is_ancestor=cfg.get("context_is_ancestor", True))
    if a.prediction:
        findings = g.check_prediction(a.prediction, default_as_of=cfg.get("as_of"),
                                      missing_date_policy=cfg["missing_date_policy"])
    else:
        findings = g.check_all(default_as_of=cfg.get("as_of"), missing_date_policy=cfg["missing_date_policy"],
                               look_budget=cfg["budget"].get("test_looks"),
                               require_different_judge=cfg["judge"].get("require_different_model", True))
    rc = _print_findings(findings, a.json)
    return 1 if problems else rc


def cmd_commit(a, cfg) -> int:
    c = commit_file(Path(a.file))
    ev = _ledger(cfg).append("commit", parents=a.prediction, source=str(a.file),
                             meta={"digest": c.digest, "algo": c.algo})
    print(f"digest {c.digest}\nPublish {a.file}.commit.json now. Keep {a.file}.salt private until the reveal. "
          f"(ledger: {ev.id})")
    return 0


def cmd_verify(a, cfg) -> int:
    ok = verify_file(Path(a.file), a.salt)
    print("MATCH: the file is exactly what was committed." if ok else "MISMATCH: the file changed after it was committed.")
    return 0 if ok else 1


def cmd_firewall(a, cfg) -> int:
    fw = TimeFirewall(a.as_of or cfg.get("as_of"), missing_date_policy=a.policy or cfg["missing_date_policy"],
                      blocked_sources=(a.block or []) + list(cfg.get("blocked_sources") or []),
                      ledger=_ledger(cfg) if a.log else None)
    src = sys.stdin if a.input == "-" else open(a.input, encoding="utf-8")
    items = [json.loads(line) for line in src if line.strip()]
    kept = fw.filter(items)
    for it in kept:
        print(json.dumps(it, ensure_ascii=False))
    print(f"firewall: kept {len(kept)} of {len(items)} item(s) (as_of {fw.as_of})", file=sys.stderr)
    return 0


def cmd_split(a, cfg) -> int:
    read = lambda p: [ln for ln in Path(p).read_text(encoding="utf-8").splitlines() if ln.strip()]  # noqa: E731
    s = cfg["splits"]
    rep = audit_split(read(a.train), read(a.test), metric=a.metric, threshold=a.threshold or s["similarity_threshold"],
                      max_fraction_above=s["max_fraction_above"], n=a.n)
    print(rep.describe())
    if not a.no_save:
        print(f"saved {rep.save(resolve(cfg, cfg['evidence_dir']))}")
    return 1 if rep.leak_suspected else 0


def cmd_control(a, cfg) -> int:
    c = cfg["controls"]
    res = command_control(a.cmd, Path(a.labels), runs=a.runs or c["permutations"], seed=a.seed,
                          chance=a.chance if a.chance is not None else c.get("chance"),
                          tolerance=a.tolerance if a.tolerance is not None else c["tolerance"], name=a.name)
    print(res.describe())
    print(f"saved {res.save(resolve(cfg, cfg['evidence_dir']))}")
    return 1 if res.leak_suspected else 0


def cmd_ceiling(a, cfg) -> int:
    if a.claimed is None:
        if a.agreement is not None:
            print(f"binary accuracy ceiling: {binary_accuracy_ceiling(a.agreement):.4f}")
        elif a.retest_r is not None:
            print(f"correlation ceiling: {correlation_ceiling(a.retest_r):.4f}")
        else:
            print("give --agreement or --retest-r", file=sys.stderr)
            return 2
        return 0
    c = check_claim(a.claimed, replicate_agreement=a.agreement, test_retest_r=a.retest_r)
    print(c.describe())
    return 1 if c.suspicious else 0


def cmd_evidence(a, cfg) -> int:
    r = assess_check(a.p_pass_h, a.p_pass_not_h, a.prior)
    print(r.describe())
    return 1 if r.verdict == "circular" else 0


def cmd_proof(a, cfg) -> int:
    rep = check_proof(load_proof(Path(a.file)))
    if a.json:
        print(json.dumps({"valid": rep.valid, "findings": [f.as_dict() for f in rep.findings], "axioms": rep.axioms,
                          "assumptions": rep.assumptions, "cited": rep.cited, "unused": rep.unused, "depth": rep.depth},
                         indent=2))
    else:
        print(rep.describe())
    return 0 if rep.valid else 1


def cmd_lean(a, cfg) -> int:
    reports = audit_axioms(Path(a.file).read_text(), allowed=a.allow or [])
    bad = 0
    for r in reports:
        print(f"{r.theorem}: axioms {r.axioms or 'none'}")
        for f in r.findings:
            print(f"  [{f.severity}] {f.code}: {f.message}")
            bad += f.severity == "critical"
    if not reports:
        print("no `#print axioms` output found in the file", file=sys.stderr)
        return 2
    return 1 if bad else 0


def cmd_audit(a, cfg) -> int:
    rep = run_audit(cfg)
    text = {"json": lambda r: json.dumps(r, indent=2, default=str), "md": to_markdown, "text": to_text}[a.format](rep)
    if a.out:
        Path(a.out).write_text(text)
        print(f"wrote {a.out} ({rep['status']})")
    else:
        print(text)
    return 1 if rep["status"] == "fail" else 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="oguard", description="Leakage and circularity guardrails for agentic science, "
                                                           "math and engineering.")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    p.add_argument("--config", help="path to oguard.yaml (default: search upwards from the current directory)")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init", help="write oguard.yaml and .oguard/ in the current directory")
    s.add_argument("--force", action="store_true")
    s.set_defaults(fn=cmd_init)

    s = sub.add_parser("log", help="append an event to the provenance ledger")
    s.add_argument("type", choices=sorted(EVENT_TYPES))
    s.add_argument("--id")
    s.add_argument("--parent", action="append", default=[], help="an event this one was derived from (repeatable)")
    s.add_argument("--available-at", help="when this information existed (date or ISO time)")
    s.add_argument("--target", help="what the prediction or outcome is about")
    s.add_argument("--source")
    s.add_argument("--file", help="hash this file into the event")
    s.add_argument("--meta", action="append", default=[], help="key=value (value parsed as JSON when possible)")
    s.set_defaults(fn=cmd_log)

    s = sub.add_parser("check", help="check the information graph: Y must never be an ancestor of Y-hat")
    s.add_argument("--prediction")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_check)

    s = sub.add_parser("commit", help="commit to a predictions file before the outcome exists")
    s.add_argument("file")
    s.add_argument("--prediction", action="append", default=[], help="ledger id of a prediction in the file")
    s.set_defaults(fn=cmd_commit)

    s = sub.add_parser("verify", help="check a revealed predictions file against its commitment")
    s.add_argument("file")
    s.add_argument("--salt")
    s.set_defaults(fn=cmd_verify)

    s = sub.add_parser("firewall", help="filter JSON-lines documents to those that existed before as_of")
    s.add_argument("input", help="JSON-lines file, or - for stdin")
    s.add_argument("--as-of")
    s.add_argument("--policy", choices=["reject", "warn", "allow"])
    s.add_argument("--block", action="append", help="regular expression for a blocked source (repeatable)")
    s.add_argument("--log", action="store_true", help="log every allowed item as a retrieval event")
    s.set_defaults(fn=cmd_firewall)

    s = sub.add_parser("split-audit", help="find test items that are near-copies of training items")
    s.add_argument("--train", required=True, help="text file, one item per line")
    s.add_argument("--test", required=True, help="text file, one item per line")
    s.add_argument("--metric", default="jaccard", choices=["jaccard", "exact"])
    s.add_argument("--threshold", type=float)
    s.add_argument("--n", type=int, default=3, help="character n-gram size for jaccard")
    s.add_argument("--no-save", action="store_true")
    s.set_defaults(fn=cmd_split)

    s = sub.add_parser("control", help="negative control: rerun a whole pipeline on scrambled labels")
    s.add_argument("--cmd", required=True, help="command containing {labels}; it must print its score last")
    s.add_argument("--labels", required=True)
    s.add_argument("--runs", type=int)
    s.add_argument("--seed", type=int, default=0)
    s.add_argument("--chance", type=float)
    s.add_argument("--tolerance", type=float)
    s.add_argument("--name", default="command")
    s.set_defaults(fn=cmd_control)

    s = sub.add_parser("ceiling", help="best score any honest model can reach given replicate noise")
    s.add_argument("--agreement", type=float, help="binary outcomes: replicate agreement in [0.5, 1]")
    s.add_argument("--retest-r", type=float, help="continuous outcomes: test-retest correlation")
    s.add_argument("--claimed", type=float, help="a reported score to compare against the ceiling")
    s.set_defaults(fn=cmd_ceiling)

    s = sub.add_parser("evidence", help="how many bits of evidence a check carries")
    s.add_argument("--p-pass-h", type=float, required=True, help="P(check passes | hypothesis true)")
    s.add_argument("--p-pass-not-h", type=float, required=True, help="P(check passes | hypothesis false)")
    s.add_argument("--prior", type=float, default=0.5)
    s.set_defaults(fn=cmd_evidence)

    s = sub.add_parser("proof", help="check a proof dependency graph (YAML/JSON) for circularity")
    s.add_argument("file")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_proof)

    s = sub.add_parser("lean-axioms", help="audit Lean `#print axioms` output for sorry and assumed theorems")
    s.add_argument("file")
    s.add_argument("--allow", action="append", help="an axiom you accept (repeatable)")
    s.set_defaults(fn=cmd_lean)

    s = sub.add_parser("audit", help="answer the ten Ouroboros audit questions from the evidence on disk")
    s.add_argument("--format", choices=["text", "md", "json"], default="text")
    s.add_argument("--out")
    s.set_defaults(fn=cmd_audit)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    cfg = load_config(Path(args.config) if args.config else None)
    try:
        return int(args.fn(args, cfg) or 0)
    except (ValueError, FileNotFoundError, RuntimeError) as exc:
        print(f"oguard: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
