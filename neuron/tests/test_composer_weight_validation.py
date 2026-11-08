"""Stdlib regressions for finite nonnegative composer weight validation."""
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from neuron.composer.models import InstanceBlueprint
from neuron.composer.scorer import CandidateScorer, RawNodeData, ScorerWeights


WEIGHT_FIELDS = (
    "price",
    "sla",
    "latency",
    "regional",
    "skill_alignment",
    "cognitive_alignment",
)


def valid_weights(**changes):
    values = {
        "price": 0.35,
        "sla": 0.30,
        "latency": 0.20,
        "regional": 0.15,
        "skill_alignment": 0.0,
        "cognitive_alignment": 0.0,
    }
    values.update(changes)
    return ScorerWeights(**values)


def matching_skill_fixture():
    blueprint = InstanceBlueprint(name="weight-validation", min_sla_score_bps=0)
    blueprint.skill_vector = [1.0, 0.0]
    node = RawNodeData(
        node_id="eligible",
        provider="fixture-provider",
        hw_class="GPU_A100",
        region="test-region",
        capacity_units=1,
        reservation_price=2.0,
        collateral_staked=0.0,
        benchmark_score_bps=9000,
        latency_ms=5.0,
        skill_profile=[1.0, 0.0],
    )
    return blueprint, node


class ScorerWeightValidationTests(unittest.TestCase):
    def test_every_weight_rejects_negative_values_with_sum_preserved(self):
        for field in WEIGHT_FIELDS:
            with self.subTest(field=field):
                # Keep the legacy total exactly 1.0 so the old sum-only
                # validator accepts these inputs and this test isolates the
                # new per-field nonnegative check.
                balancing_field = "sla" if field != "sla" else "price"
                values = {name: 0.0 for name in WEIGHT_FIELDS}
                values[field] = -0.01
                values[balancing_field] = 1.01
                weights = ScorerWeights(**values)
                with self.assertRaisesRegex(ValueError, f"{field}.*finite nonnegative"):
                    CandidateScorer(weights)

    def test_every_weight_rejects_nan_and_both_infinities(self):
        for field in WEIGHT_FIELDS:
            for invalid in (math.nan, math.inf, -math.inf):
                with self.subTest(field=field, invalid=invalid):
                    weights = valid_weights(**{field: invalid})
                    with self.assertRaisesRegex(ValueError, f"{field}.*finite nonnegative"):
                        weights.validate()

    def test_every_weight_rejects_non_numeric_and_boolean_values(self):
        for field in WEIGHT_FIELDS:
            for invalid in ("0.1", True, None):
                with self.subTest(field=field, invalid=invalid):
                    weights = valid_weights(**{field: invalid})
                    with self.assertRaisesRegex(ValueError, f"{field}.*finite nonnegative"):
                        weights.validate()

    def test_mutated_weights_are_checked_at_score_boundary_even_when_empty(self):
        scorer = CandidateScorer()
        scorer.weights.price = -0.1
        blueprint, _node = matching_skill_fixture()
        with self.assertRaisesRegex(ValueError, "price.*finite nonnegative"):
            scorer.score(blueprint, [])

        scorer.weights = valid_weights()
        scorer.weights.cognitive_alignment = math.nan
        with self.assertRaisesRegex(ValueError, "cognitive_alignment.*finite nonnegative"):
            scorer.score(blueprint, [])

    def test_sum_tolerance_is_preserved_for_finite_nonnegative_weights(self):
        valid_weights(price=0.3509).validate()
        with self.assertRaisesRegex(ValueError, "must sum to 1.0"):
            valid_weights(price=0.3511).validate()

    def test_large_integer_weight_fails_with_value_error(self):
        with self.assertRaisesRegex(ValueError, "must sum to 1.0"):
            valid_weights(price=10**400).validate()

    def test_static_zero_base_configuration_remains_valid_without_requirements(self):
        weights = ScorerWeights(0, 0, 0, 0, 0, 1)
        scorer = CandidateScorer(weights)
        blueprint, node = matching_skill_fixture()
        blueprint.skill_vector = None
        result = scorer.score(blueprint, [node])[0]
        self.assertEqual(result.total_score, 1.0)

    def test_smallest_positive_subnormal_remains_valid_and_scores_finitely(self):
        tiny = float.fromhex("0x0.0000000000001p-1022")
        weights = ScorerWeights(
            price=tiny,
            sla=0.0,
            latency=0.0,
            regional=0.0,
            skill_alignment=1.0,
            cognitive_alignment=0.0,
        )
        weights.validate()
        blueprint, node = matching_skill_fixture()
        result = CandidateScorer(weights).score(blueprint, [node])[0]
        self.assertTrue(math.isfinite(result.total_score))
        self.assertAlmostEqual(result.total_score, 1.0, places=12)


if __name__ == "__main__":
    unittest.main()
