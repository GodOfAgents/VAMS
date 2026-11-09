# F11, F14, F15: advisory-only containment (2026-11-09)

Status: **TWO DEFECTS FIXED IN SOURCE; non-author review pending.** All
three findings stay REVALIDATED_OPEN. Their full repairs (authenticated
quorum anchoring, calibrated detectors, real provider execution evidence)
are not attempted here. This slice shows that, on the restricted profile,
these signals cannot authorize anything, and it removes two places where
they overstated what they know. Readiness is unchanged: 13 findings open,
0 of 36 tracks verified, NOT READY.

## Where each signal can reach (verified in source)

| Signal | Producer | Consumers | Can it authorize an action or payment? |
|---|---|---|---|
| Cognitive synchronization result (F11) | `neuron` sync / IVT | Already contained by M1: simulation only; live construction and IVT sync reject before any effect | No |
| Activation anomaly score and `adversarial_flag` (F14) | `neuron/intelligence/anomaly_detector.py` via `neuron/sentinel/sentinel_node.py` | Added to a sentinel audit report, sanitized by `neuron/da/models.py`, published as telemetry. `VAMSSentinelNode` refuses live mode, and SLA submission is unavailable | No. Nothing reads the flag as a pass |
| Node health and declared profile: region, price, credit score, passports, skills, cognitive profile (F15) | Signed `/heartbeat` (`gateway/server.py`) | The `/nodes` view and the dashboard. The Resource Composer runs only in demo simulation (`_require_composer_simulation`). Payment requires an on-chain challenge plus evidence verified by `ActionDeliveryVerifierV1` (`F13-SETTLEMENT-ACCEPTANCE.md`), and escrow providers must be timelock-governed eligible routes in `RestrictedTestnetPolicyV1` | No. CHC scoring ranks eligible candidates after the hard filter (`_filter_eligible`) and never admits or pays |

## Defect 1 (F14): malformed input read as "not adversarial"

**Before.** In `ActivationAnomalyDetector`, a NaN or infinite activation
produced a NaN Mahalanobis distance. `max(NaN, 0.0)` returns NaN, and
`NaN > threshold` is False, so `is_adversarial` returned **False**. A
malformed or corrupted activation was classified as normal: a fail-open
detector. A NaN threshold passed the `value <= 0` guard and made every input
"not adversarial". Threshold arguments passed per call were never validated.

**After.** Every entry point rejects nonfinite input with `ValueError`
instead of classifying it: `score_anomaly`, `score_anomaly_batch`,
`is_adversarial` and `get_anomaly_report`. That covers NaN, ±inf, empty
input, wrong dimensionality and a nonfinite intermediate distance.
Thresholds must be finite positive numbers wherever they enter: the
constructor, the setter and per-call arguments. Booleans and strings are
refused.

In the sentinel, an exception from the detector leaves the report with **no**
flag at all, never a `False` that reads as clean.

**Tests:** `neuron/tests/test_anomaly_detector.py::TestNonFiniteInputFailsClosed`
(12 cases, including parametrized ones). A far outlier is still flagged after validation.

This does not make the detector a calibrated or constitutional guarantee. The
audit's held-out FP/FN distributions, OOD evaluation and per-model
calibration remain open.

## Defect 2 (F15): invented trust claims for nodes that declared nothing

**Before.** In `gateway/server.py`, a node whose signed heartbeat omitted its
profile was recorded with values it never stated:

- passport `"ERC-8004 Phala TEE"`;
- credit score 750;
- skills `["token-swap","arbitrage-analysis"]`;
- a high cognitive profile (0.75–0.95 on most dimensions);
- region `us-east-1` and price 0.15;
- network `mocha-4`, on every node.

The `/nodes` API and the dashboard then displayed a TEE attestation label,
and other claims, for any node that sent only an ID and a key.

**After.**

- Defaults are neutral: region `unknown`, price 0, score 0, no passport, no
  skills and an empty profile.
- `network` is no longer hardcoded to `mocha-4`. It is also not copied from
  the payload, because that would add a newly captured field the privacy
  review (T33) has not seen. It stays empty.
- The privacy field inventory was re-bound: the `gateway/server.py` digest,
  the re-mapped line ranges, updated flow text, and a dated
  `anchor_rebinding_20261109` entry. No new field, recipient or flow was
  added. This is not privacy approval; T33 stays BLOCKED.
- Every node view carries `"verification": "unverified-self-declared"` and
  the list of self-declared fields. A valid heartbeat signature
  authenticates the sender, not the claims.
- Declared values are still recorded as declared.

**Tests:** `neuron/tests/test_gateway_current.py`:

- `test_undeclared_profile_fields_get_neutral_defaults_not_invented_claims`
- `test_declared_passport_is_kept_but_reported_as_unverified`

## Results

The focused suites pass: 80 passed, 1 skip that was already there. They are:

- anomaly detector;
- sentinel and sentinel publication boundary;
- gateway current, dashboard boundary and root.

The full Python suite and Bandit results are in the commit message.

## Not done (remains for each finding)

- **F11.** Authenticated quorum and epoch rules, durable finalized anchoring,
  and real multi-process reconciliation.
- **F14.** Calibration with held-out FP/FN distributions and confidence
  intervals; OOD and adversarial evaluation; capture provenance; and a policy
  for closed models without hidden states.
- **F15.** Distinct discovered / reachable / authenticated / qualified /
  attested / executing / verified states; one real allowlisted provider
  adapter; and signed benchmark provenance.

## Invariants

No change to INV-1 to INV-10. INV-5 (OMS fail-closed) and INV-6 (TEE bound
to root identity) are unaffected: no passport field feeds either.
