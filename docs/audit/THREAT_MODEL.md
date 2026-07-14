# VAMS Testnet Threat Model

**Last verified:** 2026-07-13

## Assets And Trust Boundaries

| Boundary | Assets | Principal threats | Required controls |
| --- | --- | --- | --- |
| User/agent to Gateway | DID authority, session scope, request intent | Replay, forged identity, oversized input, credential theft | DID signatures, nonce cache, mTLS, limits, core-contract allowlists |
| Gateway to Neuron runtime | Routing and economic side effects | Prompt injection, duplicate execution, mock substitution | Capability checks, idempotency, live-mode deny rules, audit hashes |
| Runtime to DA/oracles | Evidence used for rewards and disputes | Forged receipt, stale value, outage fallback confusion | Real receipt verification, fixed stale fallback, proof/payload separation |
| Polygon contracts | Supply, escrow, rewards, insurance, roles | Reentrancy, cap bypass, insolvency, admin capture | INV-1..INV-9, CEI/guards, Safe/timelock, invariant tests |
| Cardano validators | Governance, bridge, insurance, identity | Datum substitution, replay, double satisfaction, signer confusion | Continuing-output checks, nonce properties, proof separation, multisig |
| Governance and recovery | Upgrade, treasury, pause authority | Single-key capture, malicious upgrade, permanent pause | Distinct 3-of-5 Safes, 48-hour delay, 2-of-3 pause-only council |
| Telemetry and memory | PII, prompts, cognitive and provider signals | Leakage, poisoning, unauthorized persistence or erasure | Schema allowlists, hashed identifiers, reviewer authorization, hard reset |
| Build and release | Source, dependencies, artifacts, evidence | Supply-chain compromise, stale claims, unsigned promotion | Pinned tools, secret scans, signed SBOM/evidence, commit/hash binding |

## Stop Conditions

Deployment stops on an unmitigated high/critical finding, invariant failure,
mock-backed live evidence, unsigned or commit-mismatched evidence, deployer-held
privilege, missing Safe/timelock proof, regional allocation above 30%, or any
canary exposure and concentration threshold in `testnet-profile.json`.

## Residual Risks

- Celestia/Near receipts, Gateway external tests, and chain deployment evidence
  do not exist until the controlled runtime ceremony is executed.
- Aiken transaction-level state-machine properties and independent reviews are
  still required.
- Staking rewards remain disabled; enabling them requires a separately reviewed
  solvency model rather than relying on the canary profile.
- Structural bridge and TEE tests do not replace production cryptographic
  verifier evidence.

## VDSO Canary Source Boundary

This section models the implemented VDSO canary foundation. It does not claim
that any VDSO contract, Transition VM, adapter, proof backend, encrypted
sidecar service, or hybrid authorization path is deployed or independently
assured.

| VDSO boundary | Principal threats | Required controls before canary |
| --- | --- | --- |
| Polygon Amoy ↔ Cardano Pre-Prod | Conflicting canonical histories, stale authority epoch, forged migration root, implicit Cardano demotion | Preserve dual-host roles; exactly one authoritative writer per state domain; governance-approved checkpoint and two independently reproduced migration roots |
| Intent builder ↔ deterministic kernel | Non-canonical encoding, replay, algorithm downgrade, compiler/prover substitution | Deterministic positional CBOR, domain-separated identifiers, nonce/expiry, signed suite ID, program/verifier binding, golden vectors |
| Kernel ↔ execution adapter | Capability lying, stale profile, proxy implementation substitution, proof/result divergence, silent security downgrade | Immutable direct implementation and code/verifier hash, expiring capability profile, conformance root, governance activation, identity-drift quarantine, fail-closed routing |
| Canonical host ↔ destination reservation | Delayed execution after recovery, old fencing token, timeout unlock, split-brain finality | Monotonic fencing token plus authority epoch, destination enforcement, authenticated abort or verified non-execution, ambiguity freeze |
| Public header ↔ encrypted sidecar | Detached sidecar substitution, plaintext PII/reasoning leakage, wrong-recipient disclosure, tamper, retention misstatement, metadata correlation | Signed sidecar-root/content-hash join, minimized headers, authenticated payload encryption, recipient-bound classical HPKE envelopes, selective disclosure roots, key-erasure records, log allowlists |
| Classical ↔ post-quantum authorization | Tier 2 downgrade, incomplete hybrid signature, blanket PQ proof claim | Require secp256k1 **and** ML-DSA-65 for Tier 2; classify authorization, proof, and settlement separately; reject inaccurate PQ labels |
| VDSO pause ↔ in-flight recovery | Pause strands value or fallback creates a second writer | Pause new reservations while preserving commit/recovery; reconciled checkpoint rollback; never auto-unlock or dual-write |

### VDSO Trust Assumptions

- The current Safe/timelock governance is trusted to activate adapters and
  change domain authority only after evidence gates pass. Interface-reported
  owners, thresholds, delays, or roles are not sufficient evidence: the
  ceremony must verify known implementation/instance bytecode and retain
  on-chain ownership and role-transfer records.
- Destination value execution is safe only when a VAMS-controlled adapter can
  enforce fencing tokens and prove finality or non-execution.
- RFC 9180 X25519 HPKE provides classical recipient confidentiality; it is not
  post-quantum confidentiality.
- SP1 and RISC Zero are not blanket post-quantum guarantees. Security is
  classified for the exact proof and compression mode used.
- Celestia and Near remain design candidates, but their current adapters are
  ineligible for VDSO live evidence. Mock or stub DA, OMS, Trails, TEE, bridge,
  and encrypted-ordering paths cannot establish canary readiness.
- Adapter and verifier addresses are trusted only for immutable direct
  deployments; address codehash alone cannot secure an upgradeable proxy.

### Additional VDSO Stop Conditions

Stop VDSO promotion if any state domain has two possible authoritative writers,
any reservation can unlock solely because time elapsed, any mandatory adapter
capability can be downgraded, any Tier 2 intent lacks either required signature,
any sensitive plaintext enters public evidence, any prover disagrees on a
semantic receipt, any DA receipt lacks exact-byte retrieval evidence, any
adapter/verifier implementation can change behind a pinned address, or any VDSO
route weakens INV-1 through INV-10. Promotion also stops if governance authority
is accepted only from self-reported interface shape without implementation and
instance evidence.
