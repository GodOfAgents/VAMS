# F05.2a exact-mint mutation acceptance

remove_exact_mint_guard / mint_extra_name is accepted at synthetic transaction-simulator scope after independent review of corrected candidate r2.

Candidate: /home/GodOfAgents/vams-evidence/m3-f05-2a-exact-mint-mutation-20261002-r2/
Candidate manifest SHA-256: 9aa4174f9a34fa720085906b6ca849ccbc48a71123bb8dc223543827ab1a8cbc
Independent review: /home/GodOfAgents/vams-evidence/m3-f05-2a-exact-mint-independent-review-20261002-r2/REVIEW.json
Review SHA-256: 41527e54c3d3ae23c023291be8c2220b056e769542c381f2520cf473903371ea

Exact command:

PYTHONDONTWRITEBYTECODE=1 /home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python /home/GodOfAgents/vams-evidence/m3-f05-2a-exact-mint-mutation-20261002-r2/run_exact_mint_mutation.py

Result: exit 0. All eight original-valid, original-mint-extra-name-negative, mutant-valid, and mutant-mint-extra-name-negative cases pass across pinned Aiken 1.1.21 and 1.1.23 with target invocation and clean teardown. Stale-script and wrong-policy routing controls fail before target invocation. The disposable policy mutation removes only the exact mint-map predicate dict.to_pairs(assets.tokens(tx.mint, policy_id)) == [Pair(authority_asset_name, 1)]. The negative mints the authority NFT and one extra asset name under the applied policy; the authority output retains only the singleton NFT and sponsor change carries the extra token. Token output totals equal minted quantities, with no minted token inputs. ADA balances 17M inputs = 16M outputs + 1M fee. Funding witnesses match persisted resolved-input payment-key hashes.

Candidate r1 is preserved but receives no credit because its CBOR map helper invocation attempted to insert a missing key through an update-only function and stopped before simulation. Candidate r2 constructs the new map entry explicitly and passes independent review. mint_extra_name was already credited as a negative case; this mutation does not add a negative-case credit.

Counts: 42/55 negative cases PASS (13 pending, 0 failed); 16/21 mutations PASS (5 pending, 0 failed). Evidence is synthetic transaction-simulator evidence only. It establishes neither ledger admission nor live-network behavior. No canonical production source, applied policy identity, blueprint, or lock was changed. F05/M3 remain open and testnet readiness is not established; deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.
