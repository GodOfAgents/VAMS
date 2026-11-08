# M3.1b-R5 ADR amendment — bounded custody controls

Date: 2026-09-25
Status: local remediation; independent M3.1b-R6 review required

R4 identified four enabled-transition interval gaps, incomplete compiled-harness
coverage, an uncapped signer list, non-maximum public budget fixtures, and a
stale INV-10 source anchor. This amendment changes only those bounded controls.

The validator now applies one finite, ordered interval contract of at most
300,000 ms at Genesis, Submit, Approve, Payout, Cancel, and Expire. Existing
deadline rules remain unchanged: Submit derives expiry from the lower bound;
Approve/Payout end no later than claim expiry; Cancel is strictly before expiry;
Expire begins at or after expiry. Infinite and reversed ranges reject.

max_extra_signatories = 6: five configured guardians plus one claimant is the
smallest union of legitimate VAMS identities needed by the reviewed lifecycle.
The cap is enforced before signer searches at Genesis and spend entry. Typed
contexts do not provide a ledger uniqueness guarantee, so duplicate entries are
rejected explicitly. Inputs, outputs, non-lovelace assets, pending claims,
guardian/approver lists, and serialized datum size remain bounded by the existing
contract. Other traversed transaction collections are fixed by the typed ledger
context or are not traversed by this validator.

The public harness validates exact mint/spend/else blueprint entrypoints,
parameter order, datum/redeemer schema references, selected schema-definition
digest, and the regenerated compiled-byte digest. It exercises every enabled
transition at below/at/above interval width plus unbounded/reversed cases,
Deposit rejection, schema/identity/hash/asset/policy mutations, signer limits,
claim removal and duplicate approval. The maximum fixtures contain 16 inputs,
16 outputs, 16 non-lovelace assets, five guardians, two pending claims, and six
signers where applicable. The accepted datum boundary is 896 serialized bytes.

INV-10 traceability now validates the separate bridge_proof and payload_hash
Deposit fields, unconditional Deposit rejection, and absence of structural
bridge authorization in this custody validator. The bridge executor remains
the authority for bridge verification; this amendment does not redefine INV-10
or close F05.

Deposit remains disabled. F01 remains REVALIDATED_OPEN; F02-F05, M3 and all
promotion gates remain open. No deployment, network admission, funding, or
Pre-Prod budget claim is made.
