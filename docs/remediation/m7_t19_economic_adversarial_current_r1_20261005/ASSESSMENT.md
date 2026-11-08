# M7/T19 economic adversarial campaign  2026-10-05

The deterministic offline campaign ran 100,000 epochs with seed 20260711 under pinned Python 3.12.14 and network-isolated bubblewrap. It passed with zero baseline false positives and detected all five attack classes 20,000/20,000 each: linked reward capture, linked capacity capture, regional reward capture, thin liquidity without a hardware-cost floor, and wash-return flows.

The focused test file `scripts/audit/test_economic_adversarial.py` passed 2/2. The capture is bound to the current runner, economic module, and testnet profile hashes in RUN.json.

This is synthetic economic-model evidence only. It does not establish Solidity runtime behavior, Forge/Slither acceptance, ledger admission, governance capture resistance, live beneficial-owner attestations, Cardano/Polygon chain behavior, or deployment readiness. It supplies no direct acceptance for INV-1, INV-2, INV-8, or INV-9; those still require the Solidity/Forge gates. No source, credentials, vendors, policy, ledger, or activation state changed.
