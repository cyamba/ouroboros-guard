"""Lean 4 integration: what does a formal proof actually rest on?

`#print axioms thm` lists every axiom a Lean proof depends on. A proof that
depends on `sorryAx` is incomplete; a proof that depends on a custom axiom is
only as good as that axiom, and if the axiom is the theorem (or an
equivalent), the proof is circular however long it is.
"""
from __future__ import annotations

import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .graph import Finding

STANDARD_AXIOMS = {"propext", "Classical.choice", "Quot.sound"}

_DEPENDS = re.compile(r"'([^']+)'\s+depends on axioms:\s*\[([^\]]*)\]", re.S)
_NONE = re.compile(r"'([^']+)'\s+does not depend on any axioms")


@dataclass
class AxiomReport:
    theorem: str
    axioms: List[str] = field(default_factory=list)
    findings: List[Finding] = field(default_factory=list)


def parse_print_axioms(text: str) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    for name, body in _DEPENDS.findall(text):
        out[name] = [a.strip() for a in body.replace("\n", " ").split(",") if a.strip()]
    for name in _NONE.findall(text):
        out[name] = []
    return out


def audit_axioms(text: str, allowed: Sequence[str] = ()) -> List[AxiomReport]:
    """Classify the axioms behind each theorem in `#print axioms` output."""
    ok = STANDARD_AXIOMS | set(allowed)
    reports = []
    for thm, axioms in parse_print_axioms(text).items():
        r = AxiomReport(thm, axioms)
        short = thm.split(".")[-1].lower()
        for ax in axioms:
            if ax == "sorryAx":
                r.findings.append(Finding("L1-sorry", "critical",
                                          f"{thm} depends on sorryAx: some step was never proved.", [thm]))
            elif ax.split(".")[-1].lower() == short:
                r.findings.append(Finding("L2-theorem-as-axiom", "critical",
                                          f"{thm} depends on an axiom named {ax!r}: the theorem was assumed.", [thm, ax]))
            elif ax not in ok:
                r.findings.append(Finding("L3-custom-axiom", "warn",
                                          f"{thm} depends on the non-standard axiom {ax!r}. Check that it is not "
                                          f"equivalent to the theorem or to something it is used to prove.", [thm, ax]))
        reports.append(r)
    return reports


def run_print_axioms(project_dir: Path, module: str, theorems: Sequence[str], timeout: float = 600) -> str:
    """Run `#print axioms` for each theorem inside a Lake project. Requires Lean 4 and Lake on PATH."""
    body = f"import {module}\n" + "\n".join(f"#print axioms {t}" for t in theorems) + "\n"
    with tempfile.NamedTemporaryFile("w", suffix=".lean", dir=project_dir, delete=False) as f:
        f.write(body)
        tmp = Path(f.name)
    try:
        proc = subprocess.run(["lake", "env", "lean", str(tmp)], cwd=project_dir, capture_output=True,
                              text=True, timeout=timeout)
    finally:
        tmp.unlink(missing_ok=True)
    return proc.stdout + proc.stderr
