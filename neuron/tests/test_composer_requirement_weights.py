"""Public scorer regressions for the fixed v0.8 requirement weight budgets."""
from dataclasses import asdict
import math
import unittest

from neuron.composer.models import InstanceBlueprint
from neuron.composer.scorer import CandidateScorer, RawNodeData, ScorerWeights


def node(name='fixture-node', price=1.0, skill=None):
    return RawNodeData(node_id=name,provider='fixture-provider',hw_class='GPU_A100',
        region='fixture-region',capacity_units=1,reservation_price=price,
        collateral_staked=0,benchmark_score_bps=8000,latency_ms=1.0,
        skill_profile=[1.0,0.0] if skill is None else skill,
        cognitive_profile={'M':1.0})


def blueprint(*,skills=False,cognitive=False):
    return InstanceBlueprint(name='fixture-ranking',min_sla_score_bps=0,
        skill_vector=[1.0,0.0] if skills else None,
        cognitive_requirements={'M':1.0} if cognitive else {})


class ComposerRequirementWeightTests(unittest.TestCase):
    # With one node the price/SLA/latency normalizations are 1, the neutral
    # regional score is 1/2, and requested matching alignment scores are 1.
    # Expected totals below are hand-calculated from the fixed 0.10 budgets
    # and base proportions 35:30:20:15, not from the scorer's effective weights.
    def test_prefilled_skill_weight_still_uses_ten_percent(self):
        weights=ScorerWeights(.28,.24,.16,.12,.20,0)
        result=CandidateScorer(weights).score(blueprint(skills=True),[node()])[0]
        self.assertAlmostEqual(result.total_score,.9325,places=12)
        self.assertEqual(result.skill_alignment_score,1.0)

    def test_prefilled_cognitive_weight_still_uses_ten_percent(self):
        weights=ScorerWeights(.175,.15,.10,.075,0,.50)
        result=CandidateScorer(weights).score(blueprint(cognitive=True),[node()])[0]
        self.assertAlmostEqual(result.total_score,.9325,places=12)
        self.assertEqual(result.cognitive_alignment_score,1.0)

    def test_both_prefilled_axes_use_ten_percent_each(self):
        weights=ScorerWeights(.21,.18,.12,.09,.25,.15)
        result=CandidateScorer(weights).score(blueprint(skills=True,cognitive=True),[node()])[0]
        self.assertAlmostEqual(result.total_score,.94,places=12)

    def test_absent_axis_gets_no_dynamic_budget(self):
        weights=ScorerWeights(.245,.21,.14,.105,.20,.10)
        result=CandidateScorer(weights).score(blueprint(skills=True),[node(skill=[-1.0,0.0])])[0]
        self.assertEqual(result.skill_alignment_score,0)
        # No cognitive requirement: its configured .10 cannot add a constant.
        self.assertAlmostEqual(result.total_score,.8325,places=12)

    def test_provider_ranking_follows_requirement_budget(self):
        weights=ScorerWeights(price=.20,sla=0,latency=0,regional=0,skill_alignment=.80)
        candidates=CandidateScorer(weights).score(blueprint(skills=True),[
            node('fixture-skilled',price=2.0),
            node('fixture-cheap',price=1.0,skill=[-1.0,0.0]),
        ])
        self.assertEqual([c.node_id for c in candidates],['fixture-cheap','fixture-skilled'])
        self.assertAlmostEqual(candidates[0].total_score,.90,places=12)
        self.assertAlmostEqual(candidates[1].total_score,.10,places=12)

    def test_no_requirements_preserves_custom_static_configuration(self):
        weights=ScorerWeights(.20,.10,.10,.10,.30,.20)
        result=CandidateScorer(weights).score(blueprint(),[node()])[0]
        self.assertAlmostEqual(result.total_score,.65,places=12)
        # A zero base budget is permitted for an entirely static config.
        static=ScorerWeights(0,0,0,0,0,1)
        self.assertEqual(CandidateScorer(static).score(blueprint(),[node()])[0].total_score,1)

    def test_active_requirements_reject_zero_base_sum(self):
        for skills,cognitive in ((True,False),(False,True),(True,True)):
            with self.subTest(skills=skills,cognitive=cognitive):
                scorer=CandidateScorer(ScorerWeights(0,0,0,0,.40,.60))
                with self.assertRaisesRegex(ValueError,'positive base'):
                    scorer.score(blueprint(skills=skills,cognitive=cognitive),[node()])

    def test_reusing_scorer_does_not_mutate_configuration(self):
        weights=ScorerWeights(.21,.18,.12,.09,.25,.15)
        before=asdict(weights);scorer=CandidateScorer(weights)
        for skills,cognitive,total in ((True,False,.9325),(False,True,.9325),(True,True,.94),(False,False,.705)):
            with self.subTest(skills=skills,cognitive=cognitive):
                result=scorer.score(blueprint(skills=skills,cognitive=cognitive),[node()])[0]
                self.assertAlmostEqual(result.total_score,total,places=12)
                self.assertEqual(asdict(weights),before)
                self.assertIs(scorer.weights,weights)

    def test_default_weight_and_empty_candidate_compatibility(self):
        scorer=CandidateScorer()
        self.assertAlmostEqual(scorer.score(blueprint(skills=True,cognitive=True),[node()])[0].total_score,.94,places=12)
        self.assertEqual(scorer.score(blueprint(skills=True,cognitive=True),[]),[])

    def test_tiny_finite_positive_base_still_normalizes_to_finite_scores(self):
        # These finite, nonnegative custom configs sum to 1 at float precision.
        # Their only base proportions are price, or price:SLA = 1:1. With all
        # single-node base scores equal to 1 and matching skill, total must be 1.
        # A large intermediate scale is not needed to represent that result.
        for price,sla in ((5e-324,0.0),(1e-320,0.0),(5e-324,5e-324),(1e-308,0.0)):
            with self.subTest(price=price,sla=sla):
                weights=ScorerWeights(price=price,sla=sla,latency=0,regional=0,skill_alignment=1)
                result=CandidateScorer(weights).score(blueprint(skills=True),[node()])[0]
                self.assertTrue(math.isfinite(result.total_score))
                self.assertAlmostEqual(result.total_score,1.0,places=12)


if __name__=='__main__':
    unittest.main()
