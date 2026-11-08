# Strict decoding for the common action context

Date2026-10-31. Status: integrated;855Solidity/7Python/sizes pass; native Rust/Aiken and full qualification pending.

The established v1 frame is unchanged: ASCII VAMS:ACTION-CONTEXT:v1 plus NUL
(23bytes), followed by21fixed32-byte words, total695bytes. Thirteen commitments
precede eight unsigned256-bit words; SHA256 and existing workload hashing remain.
Python already decodes it. Rust and Aiken had encoding helpers; Solidity received
typed structs. This adds the inverse receiver boundary, without replacing any
existing VIR/receipt/governance version or hash domain.

Solidity ActionContextV1.tryDecode returns(bool,Context). Wrong exact length/domain
or invalid fields return false and an all-zero context. Its exact-length static
payload has only bytes32/uint256 ABI fields; no dynamic offset/address/bool decoding
is accepted. Rust decode_action_context_v1 returns Option<[[u8;32];21]> without
narrowing unsigned words to machine integers. Aiken decode_action_context_v1
returns Option<List<ByteArray>> after bounded fixed slices and existing validation.
The pinned retained source uses inclusive slice endpoints/list.range;23..694
produces exactly21words. These are parser contracts, not governance authority.

All decoders preserve the existing validator's constraints: required nonzero
commitments (model may be zero), EVM20-byte/Cardano28-byte zero-padded roots,
supported root scheme, nonzero epoch/version/capabilities/chain and increasing
validity times. Zero budget/full-width uint256 remain allowed at the wire layer,
as before; bounded policy/workload/provider budgets and live supported schemes
must still reject in their own callers. Scheme2 parsing does not authorize a
Cardano action in Solidity policy, which still supports only its reviewed route.

The original action-context-v1.json and all its bytes/hashes remain unchanged.
A separate33-vector corpus has6accepts and27rejects: base/Cardano/fulluint256/
zero-budget/start-zero/nonzero-model, exact frame/version/domain errors, every
required zero commitment, padding, scheme, authority/domain zeros and reversed/
equal time. Integers are frozen as exact words rather than lossy JSON numbers.
Native fixtures use those exact same literal bytes and expected SHA256 values.

Python's7local tests pass (4previous+3new), covering all33vectors and all decoded
fields in6accepted frames. Literal/source correspondence across the generated
Rust/Aiken/Solidity fixtures passes; this is NOT native-language behavioral parity.
Rust action_context module has35prepared tests, Aiken action_context module36,
Solidity decoder35(including2fuzz cases). Rust/Aiken have NOT_RUN native status;
no Aiken/Slot08 invocation occurred. Specific Aiken authorization remains absent.

An offline native feature probe against old Solidity exits1 because tryDecode
does not exist. It demonstrates a missing receiver API, not an exploit. The first
candidate command was expressly NOT_STARTED by automatic review due credits.
Later normal approval access succeeded on a read-only preflight: all6,685source
paths and12candidate paths matched. No assumption or approval bypass was needed.

The known not-started focused command then ran normally:35native Solidity tests
pass, including2fuzz tests with256runs each. The full candidate passes855tests in
49suites,0failures/skips, with the35new cases INCLUDED alongside820prior tests.
Thirty-six compiler warnings match the prior820-test full run exactly by code
and source location; no decoder warning. The focused run reports7of that subset.
One full-launch label was rejected before native execution and its error is
retained; the corrected required label ran once successfully. No gate weakened.
Native Rust/Aiken execution remains NOT_RUN; scoped Rust paths are absent, and
no Aiken/Slot08 authority or dependency acquisition was inferred. Fresh cache
reads confirm the2Aiken library sources match the retained slice/range semantics.
Canonical full native/copy-source tests and size checks follow guarded integration.

Local source-preservation review caught Windows CRLF insertion into newly
prepared files; exact earlier bytes/helper/failure were retained, then candidate
LF endings restored. Python7passes and literal correspondence rechecked afterward.
Historical encoder bodies, Python implementation, manifests and Cargo/Aiken locks
are unchanged. No new dependency was acquired or build-script lifecycle invoked.

Parsing grants no actor consent, policy membership, current host/root/revocation,
issuer enrollment, session scope, TEE/ZK/bridge/finality, DA retrieval, spending,
effect, checkpoint or settlement authority. No live factory/caller is enabled;
the integrated effect candidate's live-startup guard stays. Full native Rust
fmt/check/clippy/test/audit and Aiken/check/applied/ledger/budget campaigns remain
required. Solidity import metadata/artifact identities may change and must be
rebuilt/source-bound; old addresses or blueprints cannot be relabelled.

INV1-10 controls, economics, custody, session limits, OMS fail-closed, root proof
binding and bridge-proof/payload separation are unchanged. No new raw private
data is logged/persisted; actual receipt/runtime privacy review remains pending.
AllA-G/BOTHchain gates stay, with13open findings/0of36verified tracks. A wire
corpus is not authentic proof, live qualification, independent review or readiness.
NoR28/Aiken/Slot08/install/download/provider/external qualification/real signing/
funds/roles/deployment action was performed or authorized by this candidate.


Canonical verification2026-10-31: ACTION-WIRE-INTEGRATION-21 completed12guardedpaths/
5new, retaining precedingdirtyfiles/fullmanifest. Fresh read-only capture checked
all6,690sourcepaths and bound42inputs. Integrated native Solidity passes855tests/
49suites,0failures/skips; the35newdecoder cases are INCLUDED alongside820previous
tests. Focused35has2fuzzcases with256runs each. Candidate/focused/canonical counts
overlap, not additive.36full-run compilerwarning codes/locations match the earlier
820-test baseline exactly; no newdecoder warning or warning-debt closure claimed.

Offline build--sizes exits0. Policy runtime9,982/init17,322bytes; decoder test
harness1,992/init2,021bytes. Captured canonical Python7tests(4previous+3new) pass
all33vectors/decoded fields,0failures/errors/skips. Existing695-byte golden,
Pythoncodec,Cargo/Aikenlocks and consensus/receipt versions unchanged. Source
literal matching is not nativeRust/Aiken parity: Rustmodule35/Aikenmodule36cases
remainNOT_RUN; source cache reads only confirm inclusive slice/range definitions.
ScopedRust paths absent; approvedrunnerUNKNOWN. No Aiken/Slot08 authority inferred.

Focused approvedGitleaks8.30.1 scanned13exact diff/config inputs offline,exit0,
emptyreport. NOTfull-source/history/vendor/other scanner/frozenCI parity. Exact
tool/source/command/output/exit/limits retained in ACTION-WIRE records. Scanner/
test source identities precede this evidence-only documentation publication.
Freshly revalidated all15privacy20 source inputs against currentcanonical; its
source inventory/212decisionrows remain UNREVIEWED, not privacy acceptance.

Normalapproval access resumed through a read-only preflight before the formerly
NOT_STARTED candidate ran. Owner later confirmed credits available. A rejected
full-run label and a warning-summary assertion are retained separately; neither
started/repeated native tests or changed product source. No uncertain retry or
review bypass. No installs/downloads/R28/Aiken/Slot08/provider/external service/
real signing/funds/roles/deployment occurred. Parsing grants no authority/proof/
credential/finality/effect/settlement permission. Existing live-startup containment
and restricted economics stay. FullA-G/BOTHchains,13open/0of36verified remain.
