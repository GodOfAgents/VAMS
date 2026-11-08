# F05.2a other-seed proof-domain case blocker - 2026-10-03

Status: BLOCKED; no registered-case or mutation credit.

## Scope and exact result

The single-case diagnostic attempted registered case r2_signature_for_other_seed using the public F05 helper and pinned Aiken 1.1.21+42babe5 (binary SHA-256 07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79). The isolated command used Python 3.12.14 and disabled network access:

    PYTHONDONTWRITEBYTECODE=1 bwrap --unshare-net --ro-bind / / --dev /dev --proc /proc --bind /tmp /tmp --bind <case-evidence-dir> <case-evidence-dir> --chdir <repo> <vams-py312>/bin/python <case-evidence-dir>/run_case.py --aiken <aiken-1.1.21> --output <case-evidence-dir>/RESULT.json

The wrapper exited 1 at its positive control before reaching the negative. Aiken uplc eval exited 101 with: Default Function not found - verifySignature. RUN.stdout is empty (SHA-256 e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855); RUN.stderr SHA-256 is 0f5a5616273ea0c27f6e06e44b4ad0fd5a449455f67ec263057bb27d02e0ac5a. No RESULT.json was produced. The exact wrapper SHA-256 is 5b2cf79c80c0d2662c2cfa09671926f1b70dcae49beedced49ca631c335e154d.

## Frozen acceptance requirement

The authoritative tx_sim_evidence_contract_r2.json (SHA-256 3510e127d369e9eab24a7ebe5a5dea10daaf55fd9589a297d78776bda940f6e9) requires category ledger_tx_sim, executor pinned Aiken tx simulate --cbor, rejection at compiled target Mint[0], and exact applied policy ID 9d669aafdc912fde12f7b6e47cd0010dfa48ea9766e60af220608731. The fixture contract has no private-key fixture; its ordered keys are generated fresh per test run. The public helper creates five fresh ephemeral keys, compiles a policy parameterized by those keys, and uses direct uplc eval with a synthetic ScriptContext. That route neither meets the registered CBOR transaction-simulation requirement nor binds to the accepted applied policy ID. The registered negative was not reached.

The contract and fixture hashes were independently checked:
- scripts/remediation/test_f05_2a_authority_bootstrap_public.py: 2d30427544ba58b41228c2236e306b23e4b8e3593987ed9bd451c6421da7e7dc
- scripts/remediation/f05_2a_tx_sim_runner_r3.py: 3088ade0a316f6af59c04fe3e1675733100b58be826fa22af3c25e40a086ea5c
- scripts/remediation/f05_2a_tx_sim_registry.py: c03230249c7e73f6929cc944b7af3e30d98b8168f8abd184fa39332a601a394e
- docs/remediation/m3_f05_2a/authority_bootstrap_public_fixtures.json: 98a05d24d476b1aee2754768322dc4b794e5afb5fabec28ade17a2888285467d
- cardano/validators/f05_authority_policy.ak: 5c01f9556d922a719a7dac348d8b7175d660ef387fdf2005979c27fb2e833b05

The accepted identity review records the original applied artifact and policy ID. Deriving alternate-seed Ed25519 signatures for that committee from public signatures is not available from the fixture; this is a cryptographic conclusion, not a key-recovery attempt. No secrets, keys, transactions, or network activity were created or used.

## Independent review

Read-only review by /root/f05_other_seed_blocker_review: PASS for blocker classification and evidence-contract analysis. The reviewer verified the captured failure, source and contract hashes, exact required policy ID and simulator, and absence of a private-key fixture. The reviewer did not rerun the command. The conclusion is that no current evidence can pass this case under the frozen contract.

## Smallest decision required

Choose one path before this registered case can advance:

1. Keep the frozen acceptance contract and authorize use of a controlled existing-committee signing path to produce alternate-seed proofs for the exact applied policy, without exporting private material; then run the required CBOR simulator and independent review.
2. Amend the evidence contract to accept a synthetic proof-domain test on a separately parameterized test-only policy. This would not count as ledger_tx_sim or as acceptance of the exact applied policy.

The test-only ephemeral-key path alone is not acceptance under the current contract. F05 counts remain 45/55 negative cases and 18/21 mutations; this diagnostic grants no count.

## Remaining blockers and next slice

F05.2a remains open. Four proof-domain cases and six applied-parameter variants remain pending; the latter retain their separate A/B/C owner decision. G1 remains failed; the captured 32-warning diagnostic identifies one F05 single-clause warning plus warnings in other dirty files. Next safe slice: inspect the two warnings in cardano/validators/insurance_fund.ak and test context; this does not resolve the separate evidence-contract decision for r2_signature_for_other_seed.
