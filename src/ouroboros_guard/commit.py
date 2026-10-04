"""Commit, then reveal.

Publish c = SHA-256(canonical(payload) || salt) before the outcome exists.
The salt (32 random bytes) makes the commitment hiding: nobody can recover or
brute-force the prediction from c. SHA-256's collision resistance makes it
binding: you cannot later find a different payload with the same c.
"""
from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

from .ledger import canonical
from .timeutil import now_utc


@dataclass
class Commitment:
    digest: str
    salt: str
    created_at: str
    algo: str = "sha256(canonical_json || salt_hex)"

    def public(self) -> Dict[str, str]:
        """What you publish now. Keep the salt private until the reveal."""
        return {"digest": self.digest, "created_at": self.created_at, "algo": self.algo}


def _digest(payload_text: str, salt: str) -> str:
    return hashlib.sha256((payload_text + salt).encode("utf-8")).hexdigest()


def commit_payload(payload: Any, salt: str | None = None) -> Commitment:
    salt = salt or secrets.token_hex(32)
    return Commitment(_digest(canonical(payload), salt), salt, now_utc())


def verify_payload(payload: Any, salt: str, digest: str) -> bool:
    return secrets.compare_digest(_digest(canonical(payload), salt), digest)


def load_predictions(path: Path) -> Any:
    """Read a predictions file as data. JSON, JSON-lines, CSV and anything else (raw text) are supported."""
    text = Path(path).read_text(encoding="utf-8")
    suffix = Path(path).suffix.lower()
    if suffix == ".json":
        return json.loads(text)
    if suffix in (".jsonl", ".ndjson"):
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    return {"raw_text": text}


def commit_file(path: Path) -> Commitment:
    """Commit to a predictions file. Writes <file>.commit.json (public) and <file>.salt (private)."""
    path = Path(path)
    c = commit_payload(load_predictions(path))
    Path(str(path) + ".commit.json").write_text(json.dumps({**c.public(), "file": path.name}, indent=2) + "\n")
    salt_path = Path(str(path) + ".salt")
    salt_path.write_text(c.salt + "\n")
    try:
        salt_path.chmod(0o600)
    except OSError:
        pass
    return c


def verify_file(path: Path, salt: str | None = None) -> bool:
    path = Path(path)
    pub = json.loads(Path(str(path) + ".commit.json").read_text())
    salt = salt or Path(str(path) + ".salt").read_text().strip()
    return verify_payload(load_predictions(path), salt, pub["digest"])
