# Composed allocation completion status

Completion status repair, 2026-10-31: isFullyClaimed now requires an existing
allocation as well as all providers being paid. The baseline runtime campaign
reproduced4unknown/default-ID assertion failures while6known-state cases passed.
Unknown IDs now return false through the unchanged Boolean ABI. An earned but
unpaid share, partial claim, full refund or mixed refund/payment is incomplete;
all-paid allocations stay complete after pause/time changes. No payout, proof,
fee, policy, storage layout or restricted activation behavior changes.

Ten regression/property cases cover these states, including2fuzz campaigns and
the20provider boundary. Read exact matching COMPLETION-24 native results for
execution status; prepared cases are not assurance. Consumers found by the frozen
first-party source-name search were the interface, implementation and tests;
external/dynamic callers remain outside that search. New non-upgradeable runtime
identities require fresh release evidence under later deployment authority.
Official13open findings/0of36verified and the full A--G/BOTH-chain gates remain.

The previous getter compared default zero counts for an unknown mapping entry.
The regression demonstrates the wrong public result without assuming a deployed
consumer or claiming fund loss. The existence check uses the immutable nonzero
agent set by valid allocation creation. It adds no storage or new authorization.

The source review checked the15 captured inputs against all6,694 current source
hashes. The first WSL search attempt found no /usr/bin/rg executable and stopped
before capture or product execution; its original helper is retained. The standard
library completed the same manifest-filtered literal name search without acquiring
tools. This scope cannot establish safety of external or dynamically encoded calls.

Token, bond and proof collaborators in the new status suite are explicit fixtures.
Full native Solidity, scanners, authentic proofs, independent review, privacy and
live/operational qualification retain their separate acceptance requirements.
Existing domains, receipt versions, replay consumption, earned liabilities and
role/timelock controls are preserved; no deployment or mainnet claim is made.
