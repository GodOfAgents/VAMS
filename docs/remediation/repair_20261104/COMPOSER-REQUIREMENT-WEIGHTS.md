# Requirement-driven composer weights

The v0.8 architecture and repository instructions allocate 0.10 to each present
skill/cognitive requirement axis, then proportionally scale the four configured
base weights into the remaining budget. The scorer previously did this only when
an active axis's configured weight was exactly zero. A nonzero custom alignment
weight bypassed normalization and could reverse candidate rankings.

For example, a valid custom configuration with price 0.20 and skill 0.80 ranked
an expensive matching node above a cheaper nonmatching node. With a requested
skill vector, the specified allocation is price 0.90 and skill 0.10 for those base
proportions; the cheaper node must rank first. These are off-chain scores over
synthetic node data, not token amounts or authenticated provider acceptance.

R2 also repairs an intermediate overflow for valid finite inputs. With price
weight `5e-324`, other base weights zero and configured skill weight 1, the input
passes the existing sum check. Computing `0.9 / 5e-324` produces infinity; later
multiplication can produce nonfinite coefficients and totals. R2 instead computes
each coefficient as `(component / base_sum) * remaining`. The proportion is bounded
for valid nonnegative weights, and the expected result remains 0.90 price / 0.10
skill. No new weight policy or input fallback is introduced.

The repair always applies dynamic allocation whenever at least one nonempty
requirement is present: each present alignment axis receives 0.10, an absent axis
receives zero, and the four base weights retain their relative proportions. A
zero or negative aggregate base budget rejects rather than silently returning an
unnormalized result. Static custom scoring without requirements, empty eligible
candidate results, the cognitive shortfall and cosine formulas, public request
and result types, and the configured scorer object remain unchanged. Finite,
nonnegative caller weight validation beyond the existing configuration contract
is a separate concern; this slice does not establish it.

## Verification scope

Baseline: source75 manifest
`d4fc4400f98d227100f4e255ad4c2d96d360beac187b479f11012495330034be`.
The scorer baseline is
`1e42daeb3ed88664cd56192f4bb010176c5a428cdc3747f4f0479f014ed20846`;
the current models are
`7fe2a2e0ec198ee3d987a1fe72f5bf62d535e171b5c106a52f524de2aaa42865`.
The older Windows models copy has a different digest and was not used.

The final ten unittest methods call the actual public CandidateScorer.score API with
the actual current dataclasses. They assert independent hand-calculated totals,
the ranking reversal, present/absent axes, zero-base rejection, static behavior,
unchanged configuration across repeated scores, default weights and empty nodes.
The initial nine methods produced 11 failed assertions including subtests against
the source75 baseline and passed against R1. The ten-method R2 campaign, over that
explicitly unintegrated R1 overlay, then reproduced three finite-input numeric
boundary failures. All ten pass after the stable calculation, with zero errors,
skips or protected I/O attempts. These results retain separate source identities
and are not additive. Package initializers are bypassed to avoid unrelated
optional SDK imports; the complete scorer and model modules execute normally.
No AST substitution, provider stub, fabricated pytest runner or external service
participates in those checks.

Retained initial runs are COMPOSER-NORMALIZATION-76-LINUX-BEFORE-01 and AFTER-01;
the numeric campaigns are COMPOSER-NORMALIZATION-76-R2-LINUX-BEFORE-01 and AFTER-01. Their
JSON receipts bind exact commands, source/tool/runner/worker hashes, fixed minimal
environment, byte-preserving raw streams, terminal exits and unchanged inputs.
Approved existing Linux Python3.14/bwrap provides read-only source, private PID/
network namespaces and private temporary storage. This is not the independent
Linux3.12 environment or full frozen pytest qualification. Existing CHC/scorer
pytest files are captured unchanged but NOT RUN in this dependency-limited lane.
Source/test review, package review, scanning, canonical integration and fresh
combined checks remain separate evidence; this prepared note does not assert them.

## Traceability and limits

This repairs a bounded Brain/composer algorithm prerequisite. It gives no Heart
policy, credential, admission, effect, proof, payment or settlement authority.
Sentinel/cognitive telemetry remains observational and replaceable. Typed integer
transaction construction and registry-authoritative fee terms are unchanged.
All INV-1 through INV-10 enforcement, restricted disablements and old wire bytes
are preserved. F11/F14 and relevant source/security/component integration tracks
still require their complete acceptance evidence; no finding or track is closed.

Full A--G for Polygon Amoy AND Cardano Pre-Prod remains NOT READY, with 13 open
findings and 0 of 36 tracks verified. Unknown runner/provider/observer/hardware/
model/custody/privacy/human-review inputs remain unknown. No installation,
acquisition, provider contact, live signing/funding/roles/deployment, R28, Slot08
or Aiken execution is authorized or performed by this slice. Both-chain rehearsals,
independent assurance and actual seven-day canary / 14-day public observation
requirements remain due.
