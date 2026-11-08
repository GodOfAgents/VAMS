# Local session credentials and live denial

Scoped update: 2026-11-01. Status: reviewed engineering source for guarded integration; native/live qualification remains open. This prepared bundle does not itself establish completed integration or a combined-source test pass.

## Defect and compatible repair

Stage D and GCA_ACCEPTANCE require policy enforcement before credentials are released, including direct callers. The retained Sequence facade rejected unimplemented real wallet/bundler operations, but SessionKeyManager.create_session_key could still reach entropy, Account.from_key and return private-key data in staging/testnet/production. Its cached scope predicate could return True for seeded live records without authenticated current policy/root/epoch authority. Earlier INV-3/INV-4 reviews establish local SDK behavior, not live grants or deployment authority.

Creation now requires the actual configured SequenceWalletManager and non-live immutable and current runtime policies. It checks before inputs, immediately before entropy/key operations, and before caching/returning credentials. Direct construction of a SessionKeyManager with an unqualified parent cannot bypass issuance admission. Live-bound managers cannot be relabelled by a non-live environment; non-live managers cannot issue after the environment becomes live or invalid. Cached verification returns False before cache access for live or unknown runtime contexts.

Existing non-live shapes, 1–24-hour creation limits, half-open expiry, allowlists and tier caps are preserved. Caller-mutable local dictionaries, float caps, synthetic addresses and seeded test records remain local metadata, not production grants. No economic-unit interpretation, real signing or bundler backend changes. Plaintext local private-key output is not qualified credential custody.

This containment does not complete or replace the required authentic session-grant/credential broker. Live eligibility still requires current host policy and actor/root/control-epoch authority, reviewed deployed contract/chain whitelist and integer budget, consent/revocation/restart semantics, isolated credential custody, actual ERC-4337 transaction enforcement and independent denied-route observation. Removing a guard or passing unit tests supplies none of those inputs.

## Retained evidence and local dependency resolution

The source32 capture checked all 6,709 paths against manifest `6e74f80c2b80a9929fd6aed24bc14966c6d765c28de473a2940c9479c523ba01`. Its ten new tests reproduced 23 failing subchecks, zero errors/skips, using non-signing doubles. Windows boundary selection passed 21 tests. The broader Windows selection stopped because Requests was absent; that failure and its original runner remain retained.

The later local Linux selection used the existing approved system Python 3.14, with pre-existing Requests 2.32.5 and its declared chardet/idna/urllib3/certifi dependencies. Direct hashes bind 233 system package/source/cache files; no package was installed, downloaded or replaced. Metadata had no distribution file list, so it was not treated as byte provenance. Installer/build provenance remains unaccepted. All six test modules and their assertions are unchanged; the original Requests HTTP-call guards remain. The existing missing-unused-eth_account import seam and patched non-signing Account/entropy fixtures are not actual eth_account cryptography.

SESSION-34-LINUX-CANDIDATE records 174 tests with zero failures/errors/skips: 11 facade, 59 caps, 37 allowlist, 50 expiry, seven value and ten live-boundary cases. The four previously blocked suites supply 153 cases; the prior 21 are INCLUDED, not additive. Candidate bytes, current canonical source and package files were unchanged. The worker binds 170 loaded Requests-family module/source/cache records. Three socket audit events were blocked, zero process-creation events were blocked; their origins were not captured and must not be attributed or restated as zero attempts. No successful external service use is demonstrated. Network isolation, read-only mounts, hidden home/reserved paths and a 60-second one-shot timeout bounded the run; explicit CPU/memory quotas were not established.

Non-author reviews accept the guard and this result for local source integration only. The pending local four-suite hold is satisfied in that Python 3.14 scope. Independent Linux Python 3.12, full frozen CI, dependency provenance/scanners, legacy genuine Account behavior and live wallet/credential qualification remain open. No local result clears those gates. The prior source reviews, failed Windows run and all original counts retain their source identities.

## Integration, invariants and privacy

The integration bundle rebases documentation onto the current 6,712-path manifest `14435aea6f106d8f5ecf5bb11bed6a58882e6e635bd7a8c56e69ffcbf668c75b`, preserving the separately integrated table/FK/trigger repair. A successful guarded integration journal and fresh canonical-copy tests must follow; this preparation claims neither step has completed.

INV-3/INV-4 are affected by live denial while their local cap/expiry/whitelist algorithms remain. INV-1, INV-2 and INV-5 through INV-10 executable controls are unchanged. No new persistent field, telemetry value, key export format, privacy decision, role, route or live factory is introduced. Actual credential/process/debugger/log privacy and operator review remain unqualified. Keep the existing 214 effect-field decisions and separate earned records UNREVIEWED; this session slice is not a full-project privacy inventory.

The guide's fixed automatic 5% builder-payment wording is corrected separately within this documentation bundle: builder terms are registry-authoritative, capped at 5,000bps and snapshotted at escrow creation; payment follows recognized delivery and the provider's claim. The separate 5bps protocol fee remains. This documentation change does not alter fee code or reopen earned entitlements.

Existing R3 and the consolidated qualification checklist remain the entry points. Both chains, all A--G requirements, restricted economics and disabled Deposit/Slash activation/ExecuteIntent/fiat/yield/rewards remain. No finding/track promotion, R28/Slot08/Aiken use, acquisition, provider contact, real signing or deployment is implied.
