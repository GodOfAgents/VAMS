#!/usr/bin/env python3
"""Validate the effective VAMS runtime mode at executable boundaries."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Mapping, Optional


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from neuron.runtime_safety import (  # noqa: E402
    LiveModeSafetyError,
    RuntimeMode,
    RuntimePolicy,
    load_runtime_policy,
)


def validate_runtime(
    environ: Optional[Mapping[str, str]] = None,
    *,
    require_live: bool = False,
    expected_mode: Optional[str] = None,
) -> RuntimePolicy:
    policy = load_runtime_policy(os.environ if environ is None else environ)
    if require_live and not policy.is_live:
        raise LiveModeSafetyError(
            f"Deployment preflight requires a live VAMS_ENV; got {policy.mode.value}"
        )
    if expected_mode is not None:
        try:
            expected = RuntimeMode(expected_mode)
        except ValueError as exc:
            raise LiveModeSafetyError(
                f"Deployment preflight expected mode is invalid: {expected_mode!r}"
            ) from exc
        if policy.mode is not expected:
            raise LiveModeSafetyError(
                "Deployment preflight mode mismatch: "
                f"expected {expected.value}, got {policy.mode.value}"
            )
    return policy


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-live", action="store_true")
    parser.add_argument("--expected-mode", choices=[mode.value for mode in RuntimeMode])
    args = parser.parse_args(argv)

    try:
        policy = validate_runtime(
            require_live=args.require_live,
            expected_mode=args.expected_mode,
        )
    except LiveModeSafetyError as exc:
        print(f"Runtime mode preflight failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(policy.sanitized_summary(), sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
