#!/usr/bin/env python3
"""Validate the sanitized M0.3c evidence package against closed schemas."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import m0_3c_adjudicator as m
import m0_3c_schema as schema


def validate(repo, evidence):
    return schema.validate(repo, evidence, m)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--evidence", required=True)
    args = parser.parse_args()
    try:
        result = validate(args.repo, args.evidence)
    except Exception as exc:
        print(json.dumps({
            "schema": "m0_3c_r5_validation",
            "status": "failure",
            "type": type(exc).__name__,
            "code": str(exc),
        }, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
