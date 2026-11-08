# F05.2a singleton quantity guard mutation acceptance

Accepted paired strictly with context-only authority_output_quantity_two. The only disposable validator source change replaces the frozen predicate requiring authority output quantity == 1 with expect True.

Candidate: /home/GodOfAgents/vams-evidence/m3-f05-2a-singleton-quantity-mutation-20261002-r2/
MANIFEST.sha256 file SHA-256: 4ae8070810a5c34c5f2a1f46419f14e0f741a6b5395c1263b6b12b893bd93db4

Exact command:
PYTHONDONTWRITEBYTECODE=1 /home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python /home/GodOfAgents/vams-evidence/m3-f05-2a-singleton-quantity-mutation-20261002-r2/run_singleton_quantity_mutation.py

Result: exit 0. Eight triad cases pass across pinned Aiken 1.1.21 and 1.1.23: original valid accepted, original quantity-two rejected, mutant valid accepted, mutant quantity-two accepted. Two routing controls fail before target invocation; cleanup is clean. Base policy ID 9d669aafdc912fde12f7b6e47cd0010dfa48ea9766e60af220608731; mutant policy ID 8233b77906d1d3db3546c46de65c1663f00dc217533fbce0c2c6b832.

Independent reviews were performed by two read-only reviewers. Reviewer one verified all 169 manifest entries, exact source delta, policy IDs, recorded dual-runtime results, invocation classification, and routing controls, but could not replay Aiken or verify signatures in its Windows environment. Reviewer two independently verified all eight Ed25519 funding signatures against each transaction body and each vkey hash against the persisted resolved-input payment credential across all four fixtures; it did not replay Aiken. The candidate execution is the primary dual-runtime test evidence. Both reviewers made no file changes.

The pair deliberately preserves mint quantity 1 and output quantity 2, which violates token conservation. This is synthetic context-only mutation evidence, not ledger-valid evidence. No negative case, ordinary transaction-simulator rejection, ledger admission, or live-network credit is added. Negative counts remain 44/55 PASS (11 pending); transaction-simulator 41/51; context-only 2/3; routing-only 1/1. Mutations advance to 18/21 PASS (3 pending).

Canonical validator, applied policy, blueprint, lock, source registry, and frozen evidence contract remain unchanged. Readiness is not established. Deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.
