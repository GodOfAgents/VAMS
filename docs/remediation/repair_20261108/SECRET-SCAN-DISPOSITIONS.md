# Current-tree secret-scan dispositions — PROPOSED

Status: **PROPOSED, awaiting owner ruling** (owner decision 5 names the owner
as per-finding disposition authority). No allowlist, `.gitleaksignore` entry,
file removal or history rewrite has been applied. Per-finding records are in
`secret-scan-dispositions-proposed.json` (file, line, rule, Gitleaks
fingerprint, file SHA-256, group, proof); no token value is recorded anywhere.

## Scan

Pinned Gitleaks 8.30.1 (binary sha256 `88f91962…5509`, equal to the CI pin),
repository `.gitleaks.toml`, `--redact=100`, on a `git archive` of commit
`075f8d3` plus recursive submodules (6,849 files). The CI current-tree gate
`m0_4_vendor_baseline_gate.py` still fails: "first-party finding detected".

| | Count |
|---|---|
| All matches (all rule `generic-api-key`) | 1,117 |
| Vendor (`contracts/lib`, covered by the existing vendor baseline) | 479 |
| First-party | **638** in 68 files: 634 under `docs/remediation/` (38 retained evidence packages), 4 under `scripts/remediation/` |

None are in product source (`contracts/src`, `neuron`, `gateway`, `cardano`, `frontend-vite`).

## Groups and proofs

Every first-party match was classified by recomputing or structurally
verifying the value locally. 0 remain unresolved.

| Group | Count | What it is | Proof |
|---|---|---|---|
| A | 207 | Cardano validator script hashes | Equal to a validator `hash` in a compiled blueprint in the tree |
| B | 96 | File digests in evidence manifests | Equal to the SHA-256 of a file in the repo or retained evidence (28,982 files indexed) |
| C | 189 | F05 test committee **public** keys | Valid Ed25519 public point; produced by `_EphemeralEd25519Key` (`scripts/remediation/test_f05_2a_authority_bootstrap_public.py`), which generates each key with OpenSSL inside an anonymous `memfd`, never serializes the private key, and extracts only the DER public key |
| D | 134 | Lists of those public keys | Every element of the CBOR list or 32-byte concatenation is a valid Ed25519 public point (128); 6 are bad-length mutation fixtures with one deliberately truncated 31-byte entry |
| E | 2 | Digests of other values | Equal to SHA-256/BLAKE2b of another public value in the same file |
| F | 3 | F04 Cardano asset names | `test_fixture_contract.py` recomputes each as BLAKE2b-256 of a public fixture preimage (14/14 pass) |
| G | 5 | Cardano policy IDs of compiled test variants | Field `applied_variant_ids`; 28 bytes, a width no VAMS signing scheme uses for private keys (Ed25519 and secp256k1 secrets are 32 bytes). Compiled variant scripts were not retained, so the ID could not be recomputed |
| H | 2 | Python identifier strings | `datum_duplicate_key`-style case IDs, not key material |

Total: 638.

## What a ruling needs

For each group: **accept as non-credential**, **reject** (treat as a possible
credential: rotate/remove), or **needs more evidence**. Group G has the
weakest proof (width and field semantics only); C and D rest on code review
of the generator plus point validation.

## How accepted rulings would be applied (choose one)

1. **Exact-fingerprint ignore with re-proof (recommended).** Add each accepted
   finding's Gitleaks fingerprint (`file:rule:line`) to `.gitleaksignore`, and
   add a CI check that fails unless every ignored fingerprint still matches its
   recorded file SHA-256 and group proof. Any edit to an evidence file
   invalidates its entries instead of silently covering new content. No rule,
   path or regex allowlist is widened.
2. **Relocate historical evidence.** Move the 38 retained evidence packages out
   of the release source tree into a separate evidence archive with preserved
   hashes. This shrinks the release surface but changes many evidence
   references and still requires the dispositions above for the archive.

## Out of scope here

- **Complete-history Gitleaks and all-category TruffleHog** remain failing.
  History includes the earlier incident (869 findings; three PEM occurrences
  of two permanently decommissioned identities) that requires the coordinated
  all-ref rewrite already planned. That rewrite is destructive and needs its
  own explicit authorization.
- Independent review of these dispositions remains required before release.

Status unchanged: 13 findings open, 0 of 36 tracks verified, NOT READY.
