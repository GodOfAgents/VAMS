# F05.2a authority output quantity-two context case acceptance

The frozen registered case authority_output_quantity_two is accepted as context-only evidence after independent review. Mint remains quantity 1 while the authority output carries quantity 2, preserving the registered token-conservation invalidity.

Candidate evidence: /home/GodOfAgents/vams-evidence/m3-f05-2a-output-quantity-two-context-20261002-r1/
Candidate MANIFEST.sha256 SHA-256: 6dd5222bd8175e51382c37cf62d4550d33253ed101676989b76e6d6796a58ed9
Verification command:
PYTHONDONTWRITEBYTECODE=1 /home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python /home/GodOfAgents/vams-evidence/m3-f05-2a-output-quantity-two-context-20261002-r1/run_context_case.py
Verification script SHA-256: be2d8130d932a718d0497d08f3eb6510cbe4d999e3fddf664761951a04c04b42

Independent read-only review PASS. The reviewer verified the manifest; mint/output quantities; applied policy and script hash; funding signatures against resolved input payment credentials; both pinned Aiken runtime results; invocation, rejection, and clean teardown. Both Aiken 1.1.21 and 1.1.23 invoked Mint[0] and returned the recognized compiled_evaluation rejection; runner cleanup was clean.

Category totals now are transaction-simulator 41 PASS / 10 pending, context-only 2 PASS / 1 pending, routing-only 1 PASS / 0 pending. Registered cases total 44 PASS / 11 pending / 0 failed. Mutation total remains 17/21 PASS, four pending.

This is synthetic context-only evidence using an intentionally ledger-invalid quantity mismatch. It is not ledger-admission or live-network evidence; it adds no transaction-simulator negative rejection or mutation credit. The frozen R2 contract and source registry were not modified. Deployment, Deposit, Slash activation, and ExecuteIntent remain disabled; testnet readiness is not established.
