"""Public DA serialization regressions for bounded numerical input."""
import json
import unittest
from neuron.da.models import AuditReport, sanitize_public_telemetry

class AuditNumericBoundsTests(unittest.TestCase):
    def report(self, **updates):
        values = dict(node_id="synthetic-node", sentinel_id="synthetic-sentinel",
                      challenge_type="synthetic", metrics_score=1, passed=True,
                      kpis={"score": 1}, timestamp=1, duration=1.0)
        values.update(updates)
        return AuditReport(**values)

    def test_unrepresentable_integer_telemetry_is_omitted_without_crashing(self):
        for value in (10**400, -(10**400)):
            with self.subTest(sign=value > 0):
                result = sanitize_public_telemetry({
                    "worldStateFidelity": {"state_fidelity_score": value, "status": "telemetry_only", "first_state_divergence_step": 0, "first_invalid_action_step": 1},
                    "continualLearningGain": {"gain": value, "rewardImpact": "none"},
                    "activation_anomaly_score": value,
                })
                self.assertEqual(result, {"worldStateFidelity": {"status": "telemetry_only", "first_state_divergence_step": 0, "first_invalid_action_step": 1},
                                          "continualLearningGain": {"rewardImpact": "none"}})

    def test_serialization_drops_unrepresentable_integer_telemetry(self):
        report = self.report(telemetry={"activation_anomaly_score": 10**400})
        result = json.loads(report.serialize())
        self.assertEqual(result["telemetry"], {})
        self.assertEqual(result["duration"], 1.0)
        self.assertEqual(result["kpis"], {"score": 1})

    def test_unrepresentable_integer_duration_has_validation_error(self):
        for value in (10**400, -(10**400)):
            with self.subTest(sign=value > 0):
                with self.assertRaises(ValueError):
                    self.report(duration=value).serialize()
                raw = {"nodeId": "synthetic-node", "sentinelId": "synthetic-sentinel",
                       "challengeType": "synthetic", "metricsScore": 1,
                       "passed": True, "timestamp": 1, "duration": value}
                with self.assertRaises(ValueError):
                    AuditReport.from_sentinel_report(raw)

    def test_nonfinite_telemetry_omitted_and_duration_rejected(self):
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value):
                self.assertEqual(sanitize_public_telemetry({"activation_anomaly_score": value}), {})
                with self.assertRaises(ValueError):
                    self.report(duration=value).serialize()

    def test_just_outside_gain_limit_integers_are_omitted(self):
        for value in (10**18 + 1, -(10**18) - 1):
            with self.subTest(value=value):
                telemetry = {"continualLearningGain": {"gain": value}}
                self.assertEqual(sanitize_public_telemetry(telemetry), {})
                self.assertEqual(json.loads(self.report(telemetry=telemetry).serialize())["telemetry"], {})

    def test_existing_numeric_boundaries_are_preserved(self):
        for duration in (0, 86400, 0.5):
            with self.subTest(duration=duration):
                self.assertEqual(json.loads(self.report(duration=duration).serialize())["duration"], duration)
        telemetry = {"worldStateFidelity": {"state_fidelity_score": 1.0, "first_state_divergence_step": 0, "first_invalid_action_step": 1},
                     "continualLearningGain": {"gain": -(10**18), "statefulReward": 10**18},
                     "activation_anomaly_score": 10**12}
        self.assertEqual(sanitize_public_telemetry(telemetry), telemetry)
        for duration in (-1, 86401, True, "1"):
            with self.subTest(duration=duration), self.assertRaises(ValueError):
                self.report(duration=duration).serialize()

if __name__ == "__main__":
    unittest.main()
