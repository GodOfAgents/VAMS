# Cardano input reference bounds and prepared caller regressions

Historical reference-width slice:88-case snapshot retained unchanged in the
implementation evidence. Current timing-amended fixtures have141prepared cases;
see CARDANO-TIMING.md. Earlier prefix/source claims below apply to that snapshot.

Date2026-10-30. Status: integrated uncompiled source; metadata consistent; native/ledger/budget acceptance NOT_RUN.

The frozen R7 parent specifies tx_id[32] || output_index[u32be] and all-transition
output_ref_width rejection. Current v2 bootstrap checks its seed, while the shared
transaction envelope does not explicitly check every ordinary/reference input's
transaction ID and index. This is a source-level boundary gap, not a reproduced
native failure or proof that such malformed references are ledger-admissible.

The candidate adds output_reference_valid and applies it to both input lists.
Exact32-byte IDs and indices0..4294967295 are required. It changes no datum,
identifier preimage, nonce, governance/insurance custody or selected48h delay.
Compiled hashes will necessarily change and need new applied/native review.

Twenty-four separate negative tests vary ordinary/reference input,31/33-byte ID
or negative/overflow index, and Vote transition/governor/receipt-policy caller.
The remaining valid fixture is preserved; governor receives its matching own_ref.
Separate negative tests prevent a rejecting caller from hiding another result.
Three positive synthetic u32max cases use unique references. They test the script
encoding boundary when executed later; they do not assert actual ledger reachability
of such an output index. All ledger/signature/budget evidence remains NOT_RUN.

The existing61 tests remain byte-for-byte as a prefix;88 cases are prepared in
this local file. The native matrix and source SHA match that candidate. One parent
row now has Vote representatives:29of81 rows have named representatives,52 do not.
This is not full coverage of29 obligations or native acceptance of any obligation.
The25asset_boundary_N parent labels do not define concrete field/byte mutations;
retain them as unresolved exact-vector/caller work rather than fabricate coverage.

The candidate was first prepared from source matching a retained manifest while
canonical approval review was unavailable. Credits were then restored; a fresh
whole-tree reconciliation checked6,676source paths and confirmed all four modified
baselines before rebasing global documentation. The native source is still not
compiled or executed. The earlier retained-only records remain historical and do
not claim a fresh read; CARDANO-WIDTH-CANONICAL-INPUTS supplies the new source read.

No Aiken, Slot08, R28, install/download, provider, network, live signing/fund/role or
deployment operation ran. Text/name/metadata checks are not Aiken parsing or tests.
Specific native authorization, approved runner/dependencies, full exact81-obligation
mutation/caller campaigns, applied parameters/budgets/ledger and independent review
remain. Insurance design is unchanged and still needs its independent revalidation.
ExecuteIntent stays disabled; all original A-G, both-chain, privacy/custody/proof/DA/
independent assurance and actual7-/14-day requirements remain. INV1-10 underlying
controls are unchanged. No finding/track is promoted by these prepared sources.


### Cardano input-reference bounds — source integration candidate,2026-10-30

The shared v2 transaction envelope now explicitly requires32-byte transaction IDs
and unsigned32-bit output indices on every ordinary/reference input. The frozen
encoding already declares that boundary; bootstrap seed checks alone did not cover
every transaction input. This is a source boundary repair, not a claim of a
ledger-admissible exploit or a reproduced native failure. Datum/hash preimages,
48h governance, authority/insurance custody and ExecuteIntent containment stay.

The native source campaign has88prepared cases:61existing cases preserved as exact
bytes plus24negative and3syntheticpositive reference-width cases. Negatives separate
ordinary/reference inputs,31/33-byte IDs,negative/overflow indices and Vote
transition/governor/receipt-policy callers. Matching own_ref prevents a different
governor guard masking the intended test. Positive u32max contexts do not establish
actual ledger reachability. ALL88remain NOT_RUN; no Aiken/Slot08 invocation.

Source SHA/native matrix/R7continuity and a detailed campaign match.29of81parent
rows now have named representatives, not29fullycovered/verified obligations.
Other lifecycles/callers,25underspecified asset-boundary mutations, compiled
entrypoints, actual signatures/applied scripts/ledger/budgets and independent
review remain. Metadata/name checks are not Aiken parsing or behavior evidence.

Credits were restored after the earlier review failure. Fresh all6,676source-path
reconciliation confirmed this candidate's baseline before rebasing these docs.
No native/external action or dependency acquisition occurred. Changed script hashes
must be compiled/applied/reviewed later; old blueprint/output cannot be relabelled.
All A-G/both-chain gates and UNKNOWN qualification inputs stay.13findings remain
open,0of36tracks verified; no official promotion. Existing insurance design remains
unchanged and still needs native/independent revalidation. No restricted activation.


Canonical source/metadata verification,2026-10-30: CARDANO-WIDTH-INTEGRATION completed
10guarded paths,2new; preceding dirty files/fullmanifest retained. All6,678source
paths rechecked. Native source file has88prepared cases;61old bytes are preserved
as a prefix. New27cases include24separate negative and3syntheticpositive cases
across Vote transition/governor/receipt-policy callers. Source SHA, native matrix,
R7continuity, exact caller naming and per-case NOT_RUN flags match. This is metadata
consistency, NOT Aiken parsing/compilation/validator/signature/ledger/budget evidence.
Native/ledger/budget executions remainZERO; specific Aiken/Slot08 authority stays
unestablished. No synthetic max-index fixture implies real ledger reachability.

Insurance source is unchanged. Earlier820Solidity/48suites/sizes,codec12 and143
runtime results retain their exact matching source scope; not rerun or added to
Cardano cases. Current sourced dependency interval module was read only, not run
or acquired; code/lock hashes are recorded separately from tool qualification.
Fresh source accesses resumed after credits restore. The blocked grant evidence
writer completed normally and its3doc outputs exactly match the prepared review.
No uncertain execution, alternate canonical access, install/download, provider,
external service, real keys/signing/funds/roles or deployment occurred.

No acceptance credit or official promotion:13open findings/0of36verified tracks.
Full81-obligation exact mutation/caller coverage, realistic ledger contexts,
applied identities/budgets, actual custody and independent review remain. Source
input-reference checks alone do not establish F01-F03 remediation or admission.
