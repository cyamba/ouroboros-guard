import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def oguard(*args, cwd):
    return subprocess.run([sys.executable, "-m", "ouroboros_guard.cli", *args], cwd=cwd, capture_output=True, text=True)


def test_end_to_end_cli(tmp_path):
    assert oguard("init", cwd=tmp_path).returncode == 0
    assert (tmp_path / "oguard.yaml").exists() and "*.salt" in (tmp_path / ".gitignore").read_text()

    inp = oguard("log", "input", "--id", "input:data", "--available-at", "2025-11-01", "--source", "data/x.csv",
                 cwd=tmp_path)
    assert inp.returncode == 0 and inp.stdout.strip() == "input:data"
    oguard("log", "prediction", "--id", "prediction:E1", "--parent", "input:data", "--target", "E1", cwd=tmp_path)

    preds = tmp_path / "preds.jsonl"
    preds.write_text('{"target": "E1", "y_hat": 1}\n')
    assert oguard("commit", "preds.jsonl", "--prediction", "prediction:E1", cwd=tmp_path).returncode == 0
    assert oguard("verify", "preds.jsonl", cwd=tmp_path).returncode == 0
    oguard("log", "outcome", "--id", "outcome:E1", "--target", "E1", cwd=tmp_path)

    chk = oguard("check", cwd=tmp_path)
    assert chk.returncode == 0, chk.stdout + chk.stderr

    audit = oguard("audit", "--format", "json", cwd=tmp_path)
    rep = json.loads(audit.stdout)
    assert rep["answers"][0]["status"] == "pass"
    md = oguard("audit", "--format", "md", "--out", "AUDIT.md", cwd=tmp_path)
    assert md.returncode in (0, 1) and (tmp_path / "AUDIT.md").read_text().startswith("# Ouroboros audit")

    # now leak: a derived summary of the outcome feeds a second prediction
    oguard("log", "derive", "--id", "derive:peek", "--parent", "outcome:E1", cwd=tmp_path)
    oguard("log", "prediction", "--id", "prediction:E1b", "--parent", "derive:peek", "--target", "E1", cwd=tmp_path)
    chk = oguard("check", cwd=tmp_path)
    assert chk.returncode == 1 and "G1-outcome-ancestor" in chk.stdout
    assert json.loads(oguard("audit", "--format", "json", cwd=tmp_path).stdout)["status"] == "fail"


def test_cli_tools(tmp_path):
    (tmp_path / "train.txt").write_text("alpha beta gamma\ndelta epsilon\n")
    (tmp_path / "test.txt").write_text("alpha beta gamma\nsomething new entirely\n")
    r = oguard("split-audit", "--train", "train.txt", "--test", "test.txt", cwd=tmp_path)
    assert r.returncode == 1 and (tmp_path / ".oguard" / "split_report.json").exists()

    docs = tmp_path / "docs.jsonl"
    docs.write_text('{"title": "a", "published_at": "2020-01-01"}\n{"title": "b", "published_at": "2030-01-01"}\n')
    r = oguard("firewall", "docs.jsonl", "--as-of", "2025-01-01", cwd=tmp_path)
    assert r.returncode == 0 and len(r.stdout.strip().splitlines()) == 1

    assert oguard("proof", str(ROOT / "examples/proofs/sinx_squeeze.yaml"), cwd=tmp_path).returncode == 0
    assert oguard("proof", str(ROOT / "examples/proofs/sinx_lhopital.yaml"), cwd=tmp_path).returncode == 1
    assert oguard("ceiling", "--agreement", "0.82", "--claimed", "0.97", cwd=tmp_path).returncode == 1
    assert oguard("evidence", "--p-pass-h", "1", "--p-pass-not-h", "1", cwd=tmp_path).returncode == 1
