from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .contracts import load_contract


def verify_artifacts(directory: Path) -> dict:
    directory = Path(directory)
    receipt = json.loads((directory / "run_receipt.json").read_text())
    required = set(load_contract()["required_outputs"])
    if receipt.get("status") != "PASS" or receipt.get("synthetic_only") is not True:
        raise ValueError("invalid success receipt")
    hashes = receipt.get("artifact_sha256", {})
    if set(hashes) != required:
        raise ValueError("artifact inventory mismatch")
    for name, expected in hashes.items():
        path = directory / name
        if Path(name).name != name or path.is_symlink() or not path.is_file():
            raise ValueError("invalid artifact path")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"artifact hash mismatch: {name}")
    return receipt
