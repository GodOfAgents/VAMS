# Composer provision error mapping

## Behavior

`VAMSResourceComposer.provision()` translates only a `ValueError` from
`CandidateScorer.score()` into the fixed public domain error
`ComposerError("Invalid scoring input or configuration")`. The exception cause
is retained for internal diagnosis. The existing outer `ComposerError` path
records one failed simulation. Invalid scoring therefore fails before allocator
invocation or instance publication. The catch does not absorb policy guard,
allocator, callback, or result-construction errors.

No scoring formula, allocation weights, quote, fee, provider dispatch, registry
identity, transaction amount, or settlement behavior changes. This mapping
preserves the existing off-chain simulated Composer error family and counters.

## Evidence boundary

The source-bound fixture used the exact M77 `composer.py` baseline and actual
M77 scorer, models and allocator bytes. It added five standard-library methods:
negative weight with sum preserved; mutated NaN; existing allocator error;
valid local simulated instance; and empty-node early error. The baseline capture
had five methods, zero assertion failures, two errors, zero skips and native
exit 1; the separate evidence validator returned 0. The candidate capture had
five passes, zero failures/errors/skips/protected I/O, with native and validator
exit 0.

The fixture extracts `provision` and `ComposerError` from source using AST and
bypasses package initializers. Its runtime-policy guard, ID generator and
minimal enclosing class harness are stubs. It does not run the full Composer,
original pytest modules, framework/ASGI, gateway ingress, providers, payment,
settlement, credentials, live network, chain, or deployment paths. These five
fixture methods are separate from canonical M77's 18 actual-module methods and
must not be added to that count.

This note retains preparation-time evidence identities. Current integration and
gate status is authoritative in the exact source manifest and checkpoint. The
separate source package contains the composer change, one new test module, this
note and five prefix-plus-preserved-suffix documentation updates. Integration,
source checks and independent closeout remain separate acceptance steps.

## Invariant and readiness impact

INV-1 through INV-10 enforcement is unchanged. This small diagnostic change
supports the existing F11/F14 prerequisites and T07/T22/T24 traceability; it
closes no finding or track. Full A–G and both-chain qualification remain in
scope. Thirteen findings remain open and zero of 36 tracks are verified;
readiness remains NOT READY. No key release, signing, funding, role change,
provider call or deployment is authorized by this source change.
