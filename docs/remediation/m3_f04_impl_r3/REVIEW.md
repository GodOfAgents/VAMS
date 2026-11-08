# M3 F04-R3 production identity remediation

Date: 2026-09-28
Status: PARTIAL / REVALIDATED_OPEN

## Scope and prerequisites

This scoped remediation addresses the independently reported R2 findings only. The R2 evidence package was strictly verified before editing:

- /home/GodOfAgents/vams-evidence/m3-f04-interface-r2-review-20260928T125433Z-829ab544571f
- SHA256SUMS digest: 862ba1156955e4b3658f7b8a9b965aaba181a18d87b18548d23b0c9654d458f0

The accepted R1 migration package was also verified:

- /home/GodOfAgents/vams-evidence/m3-f04-interface-migration-r1-20260928T123231Z-829ab544571f
- SHA256SUMS digest: 4ea732904a1d51005c57f9d5a4a59ccb42e761d253af4675bd0d1c9d1a3d7b67

Origin is https://github.com/GodOfAgents/VAMS.git, branch testnet/remediation-20260907, HEAD 829ab544571f12efe50ecb5740f129c8acb3e16f. The pre-existing dirty tree was preserved.

## Three-track result

Track A independently proved the pinned Aiken 1.1.21 compiler can compile one parameterized multipurpose validator with both mint and spend handlers, including policy-id and script-credential inspection. Track B found no repository evaluator or serialized ScriptContext seam: 0/49 public rows executed and 49 remain pending. Track C performed a read-only provenance/red-team pass; no independent compiled acceptance was available. Therefore this implementation is not independently accepted.

## Implemented R2 remediations

- cardano/validators/agent_registry.ak is the parameterized multipurpose identity policy/registry boundary. Mint and spend paths now bind identity policy id to the validator script context, require deterministic bootstrap-bound identity names, bind the minted unit to one registry output, require exact identity value/address topology, conserve the complete value on update, and return the complete input ADA/value on deregistration.
- Authority reference validation now requires exact singleton policy/token/quantity/value/address binding, reserve and authority credential lengths, and the declared datum hash to equal the serialized datum hash.
- DID validation now enforces the frozen lowercase hexadecimal representation and bounds.
- cardano/validators/agent_nft.ak is retained only as a legacy fail-closed policy; it cannot mint or burn identities outside the multipurpose boundary.
- cardano/plutus.json was regenerated with pinned Aiken 1.1.21.
- cardano/aiken-dependency-manifest.json and the narrowly scoped R9 verifier/tests were updated only for the intentional blueprint/source/lock provenance rebinding. The preserved dirty lockfile is bound at SHA-256 8fc8bf1ccf3cf0c91acc94232646ebabb23469eb7c2d4acb1f4f0b0b67f8213b; normalized digest remains f90d45886ca23d8661ae9973940ec03d9496ffc4e8caa9abe32fea69e938835a.

## Verification

Fresh local results:

- focused interface migration and accepted R5 contract suites: 21/21 passed;
- R9/R11/R13 provenance suite: 20/20 passed;
- pinned Aiken 1.1.21 check: exit 0, 808 checks, 0 errors, 31 warnings;
- pinned isolated provenance verifier: ok=true, check exit 0, build exit 0, blueprint program count 22;
- git diff --check: passed;
- compiled 49-row ScriptContext evaluator: not available, 0/49 executed, 49 pending;
- independent compiled mutation corpus and worst-state budget proof: not executed.

The missing evaluator is a deliberate fail-closed acceptance boundary, not a test pass. F04 cannot be closed from this slice.

## Status and safety

F04 = REVALIDATED_OPEN. F01-F03/F05 remain REVALIDATED_OPEN. Deposit and ExecuteIntent remain disabled. M3 remains OPEN, Pre-Prod admission is INCONCLUSIVE, and promotion is NOT READY. INV-1 through INV-10, M1/M2 containment, mock-mode behavior, deployment state, credentials, vendors and Git history are unchanged. This slice does not authorize F04-R4 acceptance or any deployment.
