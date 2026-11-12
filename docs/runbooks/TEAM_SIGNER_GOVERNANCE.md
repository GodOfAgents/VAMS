# Team signer bootstrap governance

**Networks:** Polygon Amoy (chain `80002`) and Cardano Pre-Prod (magic `1`)
**Governance mode:** `team-controlled-bootstrap` (owner decision 12, 2026-11-13)
**Posture:** restricted testnet, faucet-only. Not decentralized governance and
not independently reviewed.
**Last verified:** 2026-11-13 against `contracts/script/DeployTestnet.s.sol`
and `cardano/lib/vams/governance_v2.ak`

Ported from PR #4 (`docs/runbooks/TEAM_SIGNER_GOVERNANCE.md`, July 2026) after
the owner chose this model. Changes from the July draft: Cardano governance
seats added; VDSO guardian and recovery councils removed until the VDSO slice
is ported; evidence is checked by `scripts/audit/team_signer_governance.py`.
Readiness is NOT READY.

This runbook never collects a private key, seed phrase, hardware-wallet
screenshot, recovery share, email address, phone number or private emergency
channel. Only public addresses, public key hashes and sanitized, hash-bound
consent and rehearsal records belong in evidence.

## Seats

| Seat | Holder | Use |
|---|---|---|
| `ARCHITECT` | the owner | routine |
| `SIGNER_A`, `SIGNER_B`, `SIGNER_C` | three team members, UNKNOWN on 2026-11-13 | routine |
| `GOVERNANCE_RECOVERY` | offline key, 2-of-3 split custody by `SIGNER_A`–`SIGNER_C` | recovery only |
| `TREASURY_RECOVERY` | a different offline key, same custody | recovery only |

Each seat has one EVM address and one Cardano payment key hash. All six
addresses and all six key hashes must be distinct and must have no
relationship to the two decommissioned PEM identities of incident
VAMS-PEM-2026-001. Each person generates and holds their own key on a
hardware wallet or an isolated encrypted signing profile.

## Authorities

| Authority | Threshold | Members | Scope | Enforced by |
|---|---|---|---|---|
| `amoy-governance` | 3-of-5 | four routine seats + `GOVERNANCE_RECOVERY` | timelocked governance | `DeployTestnet._validateAuthorityIdentities` |
| `amoy-treasury` | 3-of-5 | four routine seats + `TREASURY_RECOVERY` | faucet-only treasury | same |
| `amoy-emergency` | 2-of-3 | `ARCHITECT`, `SIGNER_A`, `SIGNER_B` | pause only | same |
| `cardano-governance` | 3-of-5 | four routine seats + `GOVERNANCE_RECOVERY` | governance v2 members | `governance_v2.ak` (exactly five members, threshold 3) |

The governance timelock is also the settlement dispute resolver (owner
decision 10, P2), so the governance seats resolve disputes after the 48-hour
delay.

Still open: the insurance-fund guardian set and threshold, and the VDSO
guardian and recovery councils. No seat may be assigned to them until the
owner decides.

**Overlap.** With four people, one person can sit on every authority and two
people (`ARCHITECT`, `SIGNER_A`) can pause alone. Evidence and any public
wording must state this and must not describe the authorities as separated,
decentralized or independently reviewed. The checker rejects a report whose
limitations do not disclose the overlap.

## Recovery seats

Generate each recovery key in its own air-gapped ceremony and split it 2-of-3
among `SIGNER_A`–`SIGNER_C`, so no single person can rebuild it. Recovery seats
never sign routine transactions. Any reconstruction is an incident: write it
down, then replace the seat and rotate the key at once. Shares never go into
Git, chat, screenshots, cloud notes, the evidence bundle or one physical
location. Evidence records only the public address and key hash, the custody
policy, a sanitized ceremony hash and the reviewer's disposition.

## Consent and rehearsal

Before any Safe or Cardano authority is created, each routine seat holder
confirms that they understand what they approve, hold their key alone and will
never share it, completed a faucet-only Amoy signing rehearsal, recorded a
private emergency channel outside repository evidence, and will report loss
or compromise at once.

Nine rehearsals must pass and be recorded: Amoy governance 3-of-5, Amoy
treasury 3-of-5, Amoy emergency 2-of-3, Cardano governance 3-of-5, one
unavailable signer, one rejected transaction, lost-key replacement, recovery
split custody, and a human-readable transaction review. Record a positive
emergency response-time target.

## Creation boundary

Creating a Safe, timelock or Cardano authority changes external state and
needs the owner's approval of that specific transaction plus the signer
quorum; a general or bulk approval is not valid. Present the chain, Safe
release and factory (or Cardano script and parameters), owners, threshold,
transaction data and hash, fees, resulting address, postconditions and
rollback path first.

After creation, record the setup transaction, singleton and runtime hashes,
owners, threshold, nonce, enabled modules (none), guards (none), fallback
handler (none) and the full `ApproveHash` history. A zero nonce is only a
point-in-time observation; it does not prove a Safe was never used.

## Evidence

Write `team-signer-governance.json` (schema
`docs/audit/schemas/team-signer-governance.schema.json`, version 2.0.0) from
real public values and sanitized observations only, then check it:

```bash
cd ~/code/VAMS-testnet
~/.vams-tools/venv312/bin/python scripts/audit/team_signer_governance.py path/to/team-signer-governance.json
```

The checker enforces the exact seat list, the membership and threshold of
every authority, distinct keys, recovery-seat rules, all consents and
rehearsals, in-bundle evidence paths, the overlap disclosure, and `false` for
every decentralization, independent-review and external-audit claim. Run
without a file, it confirms the thresholds above still match the source; CI
runs that check. Do not commit a filled report to the release commit; ingest
it through the protected operational-evidence path.
