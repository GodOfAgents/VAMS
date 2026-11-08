# Closed-canary report time consistency

Date:2026-11-01. Prepared source for review/guarded integration. Existing public-stage seven-day canary observation requirement.
T36 monitoring remains assigned to G6. No new gate or restricted admission delay.

The existing schema1.0.0 required started_at/ended_at and integer consecutive_days,
but the readiness consumer checked only the day scalar. Missing/same/reversed/
short/future intervals and fractional/non-integer counts were not reliably rejected.
The old positive unit fixture itself omitted schema version and timestamps.

The consumer now enforces the existing seven fields/version/exact top-level shape,
timezone-aware RFC3339 start/end, at least7elapsed days, an integer count>=7 no
greater than elapsed whole days, and a completed/non-future end. Offset timestamps
normalize toUTC; fractional digits remain exact without float/microsecond rounding.
Existing stop=False, commit and seven required passed drills remain. Additional
boolean drill fields stay allowed as the existing schema permits. Unsupported
calendar/leap-second/out-of-range conversions reject with bounded field errors.

Public-stage call location and workflow signature checks are unchanged. Schema
version1.0.0/field encodings remain; deficient historical reports retain their old
identity and now reject. A timestamp check cannot prove real operation, independent
observation or host-clock accuracy. Signed/raw runtime/operator/drill evidence and
independent assurance remain required. No actual canary time/report/signature was
created, and a synthetic fixture never supplies observed days.

CANARY-39-BEFORE:18test methods,24failed subtest/results and4errors (bad scalar
types), no network/process work. Firstcandidate63testsPASS missed submicrosecond
truncation; three added tests exposed2failures in candidate02. Candidate05passes
66tests (21new+45existing audit-program cases INCLUDED),0fail/error/skip. Existing
canary fixture gains its already-required schema/time fields; assertions unchanged.
Candidate04 exposed two invalid-offset subcases because datetime normalizes out-of-range offset minutes; explicit hour/minute bounds fix them. Original source/tests/results and both candidate revisions remain in history.

The source-only worker imports real audit/release/privacy modules and uses current
read-only source data; eight exact read-only Git calls are allowed under an audit
hook, all other processes/network denied. Network-unshared/read-only worker/private
temp under pinned Python3.14.4/bwrap,45s bound; no explicitCPU/memory quotas. This
is not independentLinux3.12/fullCI/Sigstore/operator/actual observation evidence.
Fresh combined-source tests/gates must follow integration. Current900Solidity
result retains its own scope; all contract bytes are unchanged by this slice.

No INV1-10 executable protocol control, economic limit, role/48hour timelock,
quote/receipt/action/storage encoding or live backend is modified. All restricted
disablements remain. This source parser adds no report data field/event/channel;
the existing public timestamp/commit/drill metadata still needs real disposition
and privacy acceptance. No custody/provider/reviewer IDs or approvals are invented.

The full A--G/BOTH chains program stays NOT READY:13open/0of36verified. Native
runner/tool/PG/proof/provider/observer/custody/privacy/security inputs remainUNKNOWN;
actual7closed-canary and subsequent14public days remain. No R28/Slot08/Aiken,
acquisition/provider contact/real signing/funding/roles/deploy. The independent
source39audits also identify Composer simulation containment as the next ready
source slice; authentic registry/provider execution still requires implementation
and qualification. Latent unrestricted annual-emission catch-up semantics stay D2
owner-pending; restricted rewards/minter remain disabled. Do not silently change it.
