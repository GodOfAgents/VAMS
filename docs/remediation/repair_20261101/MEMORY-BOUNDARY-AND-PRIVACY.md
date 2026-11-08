# Local memory failure and privacy boundary — source 43

This repair addresses source-visible F11/F14/T24--T26/T31--T34 inputs. It does
not close those findings/tracks, establish privacy approval or qualify a live
memory/provider/runtime backend. Full A--G and both chains remain NOT READY.

## Source and defects

Base checkpoint42: HEAD829ab544571f12efe50ecb5740f129c8acb3e16f, manifest
6a8d7d1568285ccfe5c344755c063aaa2efeb879b0a43b9c10281494b4168092,
6,733paths. REMAINING-INPUTS-43 captures296 relevant source/doc inputs; supplemental
shared-doc capture preserves STATUS/HANDOFF. Independent source reviews identify
both the current-policy backend mechanism gap and this ready memory/privacy repair.

SemanticMMU logged stable memory/workflow/entity/interrupt identifiers, paths,
content-hash prefixes and raw exceptions. HIPIF also returned exception text.
The L3 writer swallowed failures after opening the final page with truncation;
store/flush still published cache state, and HIPIF could delete its only raw trace
after the summary write failed. These are concrete local defects, independent of
missing deployment/provider identities.

## Implemented correction

- Logs use fixed operation/stage messages. HIPIF filesystem/folding failures return
  `HIPIF folding failed.` without interpolated errors. Invalid address/containment
  checks remain. Memory contents and successful folded summaries retain their data;
  this is diagnostic minimization, not blanket redaction of memory returned to callers.
- L3 pages use a non-identifying temporary sibling, unchanged JSON schema/encoding,
  flush/file-fsync/close and same-directory os.replace. Failure cleans only the owned
  temporary file and raises fixed MMUPersistenceError from None. A failed store/flush
  does not publish its new L3 cache record. HIPIF deletes its raw trace only after
  store succeeds; a write failure leaves it available for recovery.
- File-fsync/replace is a local complete-file boundary, not proof of parent-directory
  fsync, universal power-loss durability, concurrent-writer safety, authenticated
  checkpoints, actual remote DA, replica/backup recovery or live exactly-once effects.
  Crashes/cleanup failure can leave a plaintext temporary copy; unlink failure can
  leave both persisted summary and raw trace while returning generic failure.
- HORMA paths, serialized page/checkpoint fields, content hashes, V(m), SIRA,
  session reset, review-gated patch/purge and access-log semantics are preserved.
  Access logs still expose unsalted stable address hashes plus session/timing to
  their callers; these remain linkable and need owner/privacy disposition.

## Inventory reconciliation

The existing privacy-field-inventory-20261020.json becomes1.12-draft, unapproved.
Its R18 identity/prompt remain historical; current source-base and repaired-module
bindings are separate, with final combined manifest external to avoid self-reference.
Five changed Gateway/Sentinel/composer/model/registry sources are reconciled by
hash, anchor and behavior. The inventory has45source bindings/112anchors/13flows,
adding S-MMU storage/folding/checkpoint/access/diagnostic/temporary-copy behavior and
local unsigned object-policy calldata/witness fields. No RPC/publication is inferred
from calldata construction. Fixed7publisher inventory/schema are unchanged.

Twenty-one other SDK modules remain source-bound but pending detailed field/sink
review. The historical R31 effect packet retains15matching source hashes/16flows/
214+7UNKNOWN slots; its flow anchors/dispositions are not newly approved by this
reference. Recipients, legal/data classification, consent, access, retention,
deletion, backup/WAL, deployed sinks and independent privacy reviewers stay UNKNOWN.
This artifact is not a complete SDK audit or D4/privacy acceptance.

Source hashes now use explicit `{artifact, algorithm, digest}` records. The first
focused scan identified one generic-api-key match in the bare checksum assigned
to the gateway/request_auth.py source-map key. MEMORY-PUBLIC-DIGEST-43 independently
binds that checksum to the unchanged actual source bytes and historical checksum.
The original finding/file identity is retained; the unapproved draft's metadata
encoding is clarified without changing the checksum or scanner rules. All45source
records use the same typed shape, with updated hash/anchor regression checks.
Other historical secret-scan dispositions and full-source/history gates remain
unaccepted. This is source-specific checksum representation, not a credential
rotation, suppression, incident closure or blanket secret classification.

## Executed evidence and limits

Five original-API regressions fail on the original source. Before01 additionally
misclassified fd-relative temporary cleanup as outside TMP (no actual outside
write); corrected Before02 has5fail/0error/0network/process/outside-TMP attempts.
Candidate01:5PASS. Expanded Candidate02:17PASS. Candidate03:19PASS, adding checks
for all45inventory hashes/112line anchors and preserved unapproved status. No test
failure or skip is hidden. Original used source/test/worker bytes and raw streams
are retained or explicitly scoped in workspace records.

Tests load actual S-MMU/SIRA modules with optional provider discovery test-patched;
they use synthetic markers and private temporary files. They cover successful page
encoding/readback, cache/flush/trace behavior under JSON/fsync/replace failures,
owned-temp cleanup, HIPIF open/resolve/unlink outcomes, patch authorization/errors,
checkpoint payload preservation, integrity faults, hard reset and unchanged V(m).
They assert diagnostic privacy while deliberately preserving actual memory/access
data. Old pytest cognitive/AgentOS/x402/package-origin suites remain NOT_RUN here.

Approved LinuxPython3.14.4/bwrap/netoff/rootRO/privateTMP/45s bound. Exact command,
tool/loaded-source/stream hashes and complete source before/after checks retained;
0network/process/outside-private-TMP attempts in corrected/final tests. Explicit
CPU/memory quotas, real host filesystem/power-loss tests, independentLinux3.12,
full frozenCI and live provider behavior are not established. Focused scan,
non-author review, integration and fresh canonical checks are separate records.

## Full-program decisions and invariant impact

The user selected reserve-until-authenticated-resolution for late completed work.
ADR records it as a required future admission/settlement rule, not implemented
contract behavior. Expiry alone must not release an admitted unresolved obligation;
unreachable providers can keep funds reserved. No timeout, adjudication or emergency
release exception is inferred. Current native host authentication/finality and
terminal-evidence qualification remain explicit source/design dependencies.

No INV1--10 enforcement source/limit or economic/proof/receipt encoding changes.
All restricted disablements and48h governance remain. No native Cardano/R28/Slot08,
dependency acquisition, provider contact, credential use, signing, funding, live
roles or deployment. Broader cognitive/memory implementations remain replaceable;
no universal conscience, authentic checkpoint or dual-chain readiness is claimed.
