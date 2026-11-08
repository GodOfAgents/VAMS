# Deployment and rehearsal approval boundary

STATUS: NOT_APPROVED. This form is a template, not an authorization.

## Required before requesting any public-testnet broadcast

Specify exact source commit, test profile hash, enabled contracts/validators/adapters, artifact/image hashes, chain identities, signer-controlled transaction plan, test-asset maximum, allowed calls, network exposure and rollback/pause plan. Reproduce native regressions for every enabled high-risk path and obtain the required security review. Every unfinished in-scope requirement stays blocking; any exception needs a separate reviewed scope decision and cannot be called a fix.

State precisely whether the request is for a controlled rehearsal, canary admission or ongoing internal testing. The repository's gate may need deployed observations from an approved rehearsal before it can admit the canary. Do not falsify those observations or silently bypass the gate. Completion of a seven-day observation belongs after the approved start, not before its own prerequisites can exist.

## Human-controlled fields

Release commit:
Profile hash:
Approved networks / chain or genesis identities:
Approved contract/validator/code identities:
Approved operations and maximum faucet-asset use:
Signer/council identities and required thresholds:
Private-network, mTLS and revocation settings:
Independent observer/reviewer identities:
Rehearsal time window and abort conditions:
Rollback/backup/nonce reconciliation evidence:
Expected evidence artifact locations:
Approval decision / approving person / timestamp:

No private key, seed phrase, access token or reusable credential belongs in this form.

## After an approved rehearsal

Obtain actual chain transaction receipts, independent code/role/datum read-backs, real runtime/DA traces, privacy review and operational drill results. Bind evidence to the exact deployed code and configuration. Check finality, not just a submitted transaction hash.

Evaluate the actual canary gate using authentic artifacts and its current schema. Start a controlled soak only with its declared prerequisites. Record observed duration and incidents honestly; do not advance timestamps. Apply the current profile's reset/exit policy or propose one for owner review if missing.

An internal gateway does not make public chain state private. Use synthetic non-sensitive inputs and separate test-only wallets. Anvil keys are local fixtures only. No real capital, public launch, mainnet or TGE is authorized.
