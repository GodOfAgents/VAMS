# Normal-rotation body-key signature pair

This component implements the owner's OLD+NEW consent requirement at the key-possession boundary. Both language APIs take one base intent and one witness, the current/proposed principal records, and two raw64 low-S signatures. Each signature has its own fixed role byte. The decoder, principal/generation commitments and shared witness prevent mixing records, intents, roles or operation witnesses. The normal-only entrypoint rejects enrollment and recovery. Lost-key recovery still requires a separate real 48-hour governance execution and new-key consent; no ordinary rotation path substitutes for it.

The component has no issuer, credential, approval store, nonce consumption, authority reader, network client, registry write, route or deployment action. Successful signature verification alone authenticates none of those facts. Current-state comparison, policy revalidation after authority changes and atomic replay consumption belong to the later governed consumer. No decision is supplied for the following policy inputs:

- Allowed lifetime and freshness.
- Grace periods.
- Challenge origin and finality.
- Whether equal public keys are permitted.
- Withdrawal, replacement and relayer eligibility.
 V1 registry/policy pins and existing version encodings remain unchanged; no profile is activated.

## Local evidence and failures

The candidate is M78 with five source/test payloads. A real offline Forge attempt found stack-too-deep in the new library; the next revision compiled past that defect but found the same compiler limitation in a new test. Both terminal failures executed zero tests and remain preserved. The library now decodes normal-mode data in a private two-argument helper. The three new tests use a memory fixture; every assertion remains. Compiler settings were not changed.

The final isolated candidate passes 17 focused Solidity methods and the full 1,080-test/67-suite campaign, with zero failures/skips. The focused methods are included in the full count. Forge build --sizes also passes; exact sizes and raw streams are retained separately. These tests use synthetic keys and establish local EVM behavior only.

The initial installed-Linux cryptography attempt failed before tests because OpenSSL loaded an unbound legacy provider. A new profile bound the exact already-installed provider after inventory review, preserving the strict native-file guard. Its one-shot run passes 16 actual-module Python methods, including unchanged literal cross-language vectors, with zero failures/errors/skips. Package initializers are bypassed; the installed Python 3.14/cryptography snapshot is not approved independent Python 3.12, full ASGI/framework qualification, signed acquisition, authentic chain authority, DCAP/EZKL evidence or live proof. No dependencies were acquired.

Evidence under the retained implementation workspace: HEARTBEAT-CONSENT-PAIR-80-R4-FOCUSED-01.json, HEARTBEAT-CONSENT-PAIR-80-R4-FULL-01.json, HEARTBEAT-CONSENT-PAIR-80-R4-SIZES-01.json and HEARTBEAT-CONSENT-PAIR-80-R5-LOCAL-OS-PYTHON-01.json. Source/tool hashes, exact commands, separate raw streams, exits and limitations are retained there. Integration, combined checks and independent package review are separate steps; this document does not assert their completion.

## Invariants and remaining acceptance

INV-1 through INV-10 enforcement paths are unchanged. This body-key component is separate from root-EOA TEE binding (INV-6) and session capability/expiry controls (INV-3/4); it cannot widen either. It changes no economics, reward backing, oracle, supply, bridge proof/payload separation, identity issuer or live mock exclusion. F08/identity track evidence remains partial; no finding status changes or track closures follow from these tests.

Next, the versioned governed consumer must atomically check authentic current policy/authority, actual single-operation timelock context, post-ETA challenge, principal CAS, nonce and both roles before one state transition. Policy/authority changes must invalidate pending approvals. Cardano needs its own native state transition/current-authority/finality tests; this EVM component cannot authenticate it. Full-source/history Gitleaks, TruffleHog and the remaining CI/security gates remain unpassed. The broader current-tree gate is FAIL; focused scans cannot supersede it.

No R28, Slot 08, Aiken, install/download, providers, real keys/signing, role grant, funding, deployment or readiness promotion occurred. Both-chain restricted deployment remains NOT READY, with 13 open findings and 0/36 verified tracks. Independent assurance, real both-chain rehearsals, seven actual closed-canary days and subsequent 14-day public observation remain required.
