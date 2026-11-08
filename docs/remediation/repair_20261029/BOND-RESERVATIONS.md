# Composed settlement bond reservation lifecycle repair

Date: 2026-10-29. Status: implemented source with focused native regression
evidence; full gates, independent assurance and live qualification remain pending.

## Defects verified in current source

ComposedSettlement checked canAcceptRequest but never called acceptRequest or
completed/cancelled a reservation. Multiple allocations or repeated provider entries
could pass against the same unchanged collateral. ProviderBondRegistry overwrote
active request IDs, accepted reused completed IDs, and let any ESCROW_ROLE caller
complete another escrow's request. Six native regressions reproduced all six
cases against preserved code; token/proof collaborators were explicit fixtures.

## State and value contract

Each V2 allocation snapshots the actual bond registry. Its per-provider request ID
is stored once using the domain VAMS:COMPOSED-BOND-REQUEST:v1, chain ID, settlement
instance, allocation ID and provider index. Retries/terminal transitions use the
stored identity. Administrative registry changes apply to new allocations only.

After current-policy admission and exact incoming escrow funding, creation invokes
the actual registry acceptRequest for each provider. It atomically reserves the
gross amount; a late capacity/funding/role failure reverts all allocation, token
and reservation state. Per-provider claims atomically release their reservation
and pay the unchanged five-basis-point fee/builder/provider split. Expiry refunds
cancel only unclaimed reservations and return the corresponding escrow value.

The registry stores a permanent creating-escrow identity for each nonzero request
ID and rejects duplicate/reused IDs and zero values. Completion and cancellation
require that exact owner and provider, not any other holder of the escrow role.
The ID remains consumed after release. Completion retains legacy totalEarned
semantics: gross successfully completed request value, not net payout or reward
credit. Cancellation does not record delivery earnings. No reward is emitted.

Revoking ESCROW_ROLE denies new reservations. The recorded owner can still release
its existing bounded reservation after role revocation or registry pause. This
does not admit new work or bypass settlement policy/proof checks. The settlement
still authenticates current delivery policy before a claim; this repair does not
implement completed-effect reconciliation/earned claims across policy revocation.
Refund/recovery remains a separate path. No SLASHER_ROLE or slash activation is added.

## Storage, migration and remaining limits

The existing eight registry storage entries and nested struct shapes are preserved.
requestOwner consumes slot8; the gap moves from slot8/50 to slot9/49, preserving
exclusive end58. The initializer signature/body are byte-for-byte unchanged.
This local compiler comparison does not authorize an upgrade of an unknown proxy.
Existing ownerless active requests are not reinterpreted: they require explicit,
independently reviewed owner provenance/migration or draining on the original
instance before replacement. No migration/reinitializer or owner-adoption bypass
is supplied. Fresh instances are the supported candidate boundary. Unknown deployed
registries/proxies and their code/upgrade custody remain unqualified.

Changed non-upgradeable settlement requires a new instance; old allocations are
not imported. An address snapshot alone does not qualify an upgradeable registry's
future code or authority. The admitted registry/runtime and its ESCROW_ROLE grant
to the exact settlement remain deployment/assurance inputs. Legacy local stubs
continue to be stubs and do not prove backing. This is on-chain reservation
accounting, not a PostgreSQL/external-provider exactly-once result.

## Native evidence and invariant impact

All19 focused tests pass under retained hash-pinned Foundry1.7.1/solc0.8.24,
offline, with FFI/network disabled. The actual ProviderBondRegistry is exercised;
token and proof collaborators are explicit fixtures. Coverage includes cumulative
capacity, duplicate provider rollback, owned ID durability, successful/partial
claims, refunds without earnings, registry changes, revoked roles, paused recovery,
funding failure and identical allocation hashes across separate settlement instances.

The first candidate exposed a compiler stack-depth limit. Private completion/
cancellation helpers resolved it without changing compiler settings. A second
attempt compiled but Forge rejected a testFail-prefixed method name; it was renamed
without changing its assertions. Exact attempts, source overlays, native output/
exits and tool hashes are retained outside checkout in VAMS-implementation-20261029.
The before/current compiled layout and exact initializer comparisons are separate
evidence. Full canonical tests/build sizes follow guarded integration.

F13 and INV-9-adjacent backing/accounting are affected. Existing fee arithmetic,
reward solvency and disabled emissions/minter rules remain. INV1/2/3/4/5/6/7/8/10
are unchanged, including bridge-proof/payload separation. The new public owner/
reservation links and permanent on-chain retention need privacy inventory/review.
No finding/track is promoted; independent proof/backends, native Cardano, full
Python/Rust/frontend/scanners and both-chain operations remain incomplete.

## Original workstream still pending

The Polygon v1 release contract still requires ordinary governor/vesting and an
ordinary-governor proposer grant, contradicting the selected restricted deployment.
Its explicit restricted-profile migration and complete registry/policy/verifier/
settlement deployment bindings remain. The bond defect was found while tracing
those dependencies and needed repair first. No artifact or gate requirement is
quietly removed, and both-chain milestones/authorizations remain unchanged.


### Canonical verification — 2026-10-29

Full Solidity suite:767 tests across46 suites pass,0 failures/skips, exit0.
The19 focused cases are included in that total and are not added again. The
offline size build passes:ComposedSettlement15,455 runtime bytes and
ProviderBondRegistry11,065; compiler warnings are retained. Canonical source
remained unchanged during both commands. Local storage/initializer comparisons
are separate evidence and do not approve an unknown deployed proxy migration.

These are local native accounting/authorization results with stated collaborator
fixtures, not authentic hardware/ZK/live-chain or independent release assurance.
Slither and all other applicable frozen gates remain pending on approved inputs.
No Aiken, Slot08/R28, installation, provider, signing/fund/role or deployment action.
The Polygon restricted-profile migration and its registry ESCROW_ROLE/constructor/
policy/verifier/settlement bindings remain unfinished.13 findings remain OPEN;
0/36 tracks verified. Both-chain milestones and all unknown input requirements stay.
