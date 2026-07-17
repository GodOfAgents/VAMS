# Team Signer Bootstrap Governance

**Network:** Polygon Amoy, chain ID `80002`
**Governance mode:** `team-controlled-bootstrap`
**Posture:** Faucet-only, experimental, not decentralized community governance
**Last verified:** 2026-07-17

This runbook defines the four-person bootstrap authority design. It never
collects a private key, seed phrase, hardware-wallet screenshot, recovery
share, email address, phone number, or private emergency channel. Only public
addresses and sanitized, hash-bound consent and rehearsal records belong in
the evidence bundle.

## Stable signer roles

- `ARCHITECT`: Aseem's routine signing address.
- `SIGNER_A`, `SIGNER_B`, `SIGNER_C`: the three team signer addresses.
- `GOVERNANCE_RECOVERY`: a separate offline recovery address for governance.
- `TREASURY_RECOVERY`: a different offline recovery address for treasury.

Each human generates and controls an independent hardware-wallet or isolated
encrypted signing profile. The four routine addresses and two recovery
addresses must be distinct and must have no relationship to the historical PEM
identities. A signer provides only a public address and a sanitized consent
record.

## Exact authorities

| Authority | Threshold | Members | Scope |
| --- | --- | --- | --- |
| Governance | 3-of-5 | `ARCHITECT`, `SIGNER_A`, `SIGNER_B`, `SIGNER_C`, `GOVERNANCE_RECOVERY` | Timelocked governance |
| Treasury | 3-of-5 | `ARCHITECT`, `SIGNER_A`, `SIGNER_B`, `SIGNER_C`, `TREASURY_RECOVERY` | Faucet-only treasury |
| Emergency | 2-of-3 | `ARCHITECT`, `SIGNER_A`, `SIGNER_B` | Pause only |
| VDSO guardian | 2-of-3 | `SIGNER_A`, `SIGNER_B`, `SIGNER_C` | VDSO quarantine only |
| VDSO recovery | 2-of-3 | `ARCHITECT`, `SIGNER_B`, `SIGNER_C` | Explicit VDSO recovery role only |

Signer overlap is unavoidable with four humans. Evidence and public disclosure
must state the exact overlap and must not describe these authorities as fully
separated or decentralized. The VDSO recovery execution path remains disabled
until a separately reviewed, independently verifiable non-execution backend
exists.

## Offline recovery controls

Generate the two recovery keys in separate air-gapped ceremonies. Each secret
is divided through 2-of-3 split custody held by `SIGNER_A`, `SIGNER_B`, and
`SIGNER_C`; no one person may reconstruct it. Recovery seats are never used for
routine approvals. Any reconstruction is an incident, requires a written
record, and is followed immediately by owner replacement and key rotation.

Do not put recovery shares in Git, chat, screenshots, cloud notes, the evidence
bundle, or the same physical location. Evidence records only the public
recovery address, custody policy, sanitized ceremony hash, and reviewer
disposition.

## Consent and rehearsal gate

Before creating a production-intended Safe, each human must confirm that they:

- understand the authority and human-readable transaction being approved;
- independently control their key and will never share signing material;
- completed a faucet-only Amoy signing rehearsal;
- recorded a private emergency availability channel outside repository evidence;
- will report loss or compromise immediately.

The evidence bundle must contain all nine successful scenarios required by
`team-signer-governance.schema.json`: governance 3-of-5, each 2-of-3 council,
one unavailable signer, one rejected transaction, lost-key replacement,
recovery split custody, and human-readable transaction review. It must also
record a positive emergency response-time target.

## Safe creation boundary

Safe and timelock creation changes external state. For each proxy or timelock,
present the exact chain, approved Safe release/factory, owners, threshold,
transaction data/hash, fees, resulting address, postconditions, and rollback
path. Obtain transaction-specific Architect approval and the required signer
quorum. A general or bulk approval is invalid.

After creation, bind the setup transaction, singleton and runtime hashes,
owners, threshold, zero handoff nonce, zero enabled modules, zero transaction
guard, zero module guard, zero fallback handler, and complete `ApproveHash`
history. Zero nonce is only a point-in-time observation and never proves a
historically pristine Safe.

## Evidence output

Create `team-signer-governance.json` only from real public addresses and
sanitized observations. Validate it through the audit program. Do not commit a
filled operational report to the release SHA; ingest it through the protected
operational-evidence workflow.
