#!/usr/bin/env python3
"""Regenerate deterministic accepted identity vectors using exact-path loading."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _load_validator():
    path = (ROOT / "validate_design.py").resolve(strict=True)
    name = "_m3_f04_identity_validator_" + uuid.uuid4().hex
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("validator module unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
        loaded = Path(module.__file__).resolve(strict=True)
        if loaded != path or hashlib.sha256(loaded.read_bytes()).digest() != hashlib.sha256(path.read_bytes()).digest():
            raise RuntimeError("validator path/hash mismatch")
        return module
    except BaseException:
        sys.modules.pop(name, None)
        raise


def main() -> None:
    validator = _load_validator()
    vectors = validator.load("ASSET_VECTORS.json", ROOT)
    rows = []
    for row in vectors["vectors"]:
        preimage, token = validator.derive(row)
        rows.append({"id": row["id"], "preimage_hex": preimage, "token_name": token})
    print(json.dumps({"schema_version": "m3-f04-r1-generated-vectors-v1", "vectors": rows}, sort_keys=True))


if __name__ == "__main__":
    main()
