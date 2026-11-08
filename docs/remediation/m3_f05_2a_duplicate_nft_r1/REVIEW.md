# F05.2a duplicate NFT output context case acceptance

The frozen authority_output_duplicate_nft case is accepted as context-only evidence after two independent read-only reviews.

Candidate: /home/GodOfAgents/vams-evidence/m3-f05-2a-duplicate-nft-context-20261002-r2/
MANIFEST.sha256 file SHA-256: 0ce6dd703794f3e24cc5ab3c7bb79c5df801a99e8bb418ec470f2fa7bd725b55

Exact command:
PYTHONDONTWRITEBYTECODE=1 /home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python /home/GodOfAgents/vams-evidence/m3-f05-2a-duplicate-nft-context-20261002-r2/run_duplicate_nft_context.py

Result: exit 0. Both pinned Aiken 1.1.21 and 1.1.23 invoked the original applied policy, returned the recognized compiled evaluation rejection, and cleaned up. The fixture preserves one minted authority NFT and duplicates the complete NFT-bearing output, changing only the duplicate payment credential to script credential 65 repeated 28 bytes. The original datum and PoPs are unchanged. A third synthetic funding input supplies the duplicate's 10M lovelace; three funding signatures bind to their resolved input credentials. ADA balances: 27M inputs = 26M outputs + 1M fee.

Reviewer one verified all manifest entries, exact output/address delta, one-mint/two-output context, funding construction, both recorded runtime outcomes, invocation, cleanup, and context-only classification. Reviewer two independently verified all three Ed25519 signatures against the body hash and vkey hashes against resolved input payment credentials; confirmed input references/values, ADA balance, unchanged datum/PoPs/applied policy, and native-token conservation invalidity. Neither reviewer independently replayed Aiken; the dual-runtime command above is the executed-test evidence. No reviewers edited files.

The intentional native-token conservation violation makes this synthetic context-only evidence, not ledger admission or live-network evidence. Counts: context-only 3/3 PASS; registered negatives 45/55 PASS (10 pending); transaction-simulator 41/51; routing-only 1/1. Mutations remain 18/21 PASS (3 pending). No transaction-simulator rejection or mutation credit is added.

Frozen contract, registry, canonical validator, applied policy, blueprint, and lock remain unchanged. Testnet readiness is not established; deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.
