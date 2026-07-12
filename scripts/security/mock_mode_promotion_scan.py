#!/usr/bin/env python3
"""Verify live-mode mock guards are present at known VAMS integration boundaries."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REQUIRED_GUARDS = {
    "gateway/server.py": ('require_not_live_mock("Gateway DA audit log"',),
    "neuron/da/performance_audit.py": ('require_not_live_mock("PerformanceAuditLog"',),
    "neuron/da/adapters/avail_adapter.py": ('require_not_live_mock("AvailDAAdapter"',),
    "neuron/da/adapters/eigenda_adapter.py": ('require_not_live_mock("EigenDAAdapter"',),
    "neuron/sdk/oms_identity.py": ('require_not_live_mock("OMSIdentityVerifier"',),
    "neuron/sdk/trails_client.py": ('require_not_live_mock("TrailsClient"',),
    "neuron/payments/coinme_client.py": ('require_not_live_mock("CoinmeClient"',),
    "neuron/sdk/avail_substrate.py": ('require_not_live_mock("AvailDASDK"',),
    "neuron/sdk/eigenda_kzg.py": ('require_not_live_mock("EigenDASDK"',),
    "neuron/sdk/iagon_storage.py": ('require_not_live_mock("IagonStorageSDK"',),
    "neuron/sdk/phala_tee.py": ('require_not_live_mock("PhalaTEE enclave execution"',),
    "neuron/sdk/interrupt_handler.py": ('require_not_live_mock("InterruptVectorTable"',),
    "neuron/storage/arweave.py": ('require_not_live_mock("ArweaveStorage upload"',),
    "neuron/bridge_executor.py": (
        'require_not_live_mock("BridgeExecutor"',
        'require_not_live_mock("MultiISMVerifier"',
    ),
}


def main() -> int:
    missing: list[str] = []

    for rel_path, snippets in REQUIRED_GUARDS.items():
        path = ROOT / rel_path
        if not path.exists():
            missing.append(f"{rel_path}: file missing")
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for snippet in snippets:
            if snippet not in text:
                missing.append(f"{rel_path}: missing guard `{snippet}`")

    if missing:
        print("Mock-mode promotion scan failed:")
        for item in missing:
            print(f"  - {item}")
        return 1

    print("Mock-mode promotion scan passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
