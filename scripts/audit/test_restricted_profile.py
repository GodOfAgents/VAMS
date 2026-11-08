"""Frozen profile regressions: synthetic configuration, no custody/live evidence."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from scripts.audit import audit_program as audit
from scripts.audit import economic_concentration as economic
from scripts.audit import run_economic_adversarial as campaign
from scripts.audit.restricted_profile_v1 import validate_testnet_profile

PROFILE = json.loads((Path(__file__).resolve().parents[2] / 'docs/audit/testnet-profile.json').read_text())


def balanced_snapshot():
    return {'providers': [dict(beneficial_owner=f'fixture-{region}-{owner}', region=f'region-{region}',
         reward=1, capacity=1) for region in range(4) for owner in range(5)], 'region_controls': {}}


class RestrictedProfileConsumerTests(unittest.TestCase):
    def audit_errors(self, profile):
        original = audit._load_json
        with patch.object(audit, '_load_json', side_effect=lambda path: profile if path == audit.PROFILE_PATH else original(path)):
            return audit.validate_program()

    def test_unchanged_profile_passes_program_and_economic_consumers(self):
        before = copy.deepcopy(PROFILE)
        self.assertEqual(self.audit_errors(PROFILE), [])
        self.assertTrue(economic.evaluate(balanced_snapshot(), PROFILE)['passed'])
        self.assertTrue(campaign.run_campaign(10, 20260711, PROFILE)['passed'])
        self.assertEqual(PROFILE, before)

    def test_unchecked_selected_constraints_cannot_be_relaxed_at_program_gate(self):
        changes = (
            ('asset_policy', 'real-value'), ('real_fiat_enabled', True), ('real_yield_capital_enabled', True),
            ('concentration_stop_conditions.top_four_provider_share_bps', 10000),
            ('concentration_stop_conditions.linked_operator_share_bps', 10000),
            ('concentration_stop_conditions.hhi', float('nan')),
            ('thin_liquidity.minimum_independent_providers', 1),
            ('thin_liquidity.require_hardware_cost_weighted_floor_below_minimum', False),
            ('exposure_limits.daily_aggregate_insurance_reserve_bps', 10000),
            ('governance.safe_owners', 3), ('governance.emergency_threshold', 1),
            ('governance.emergency_owners', 1), ('governance.emergency_scope', 'unrestricted'),
            ('soak_periods.closed_canary_days', 0), ('soak_periods.public_testnet_days', 0),
        )
        for path, value in changes:
            with self.subTest(path=path):
                profile = copy.deepcopy(PROFILE)
                target = profile
                names = path.split('.')
                for name in names[:-1]:target = target[name]
                target[names[-1]] = value
                self.assertTrue(self.audit_errors(profile))

    def test_direct_economic_caller_cannot_bypass_frozen_thresholds(self):
        for path, value in (('hhi', float('nan')), ('hhi', float('inf')),
                            ('top_four_provider_share_bps', 10000), ('linked_operator_share_bps', True)):
            with self.subTest(path=path, value=repr(value)):
                profile = copy.deepcopy(PROFILE)
                profile['concentration_stop_conditions'][path] = value
                with self.assertRaises(ValueError):
                    economic.evaluate(balanced_snapshot(), profile)

    def test_campaign_cannot_emit_a_pass_under_relaxed_profile(self):
        profile = copy.deepcopy(PROFILE)
        profile['governance']['emergency_scope'] = 'unrestricted'
        with self.assertRaises(ValueError):
            campaign.run_campaign(10, 20260711, profile)

    def test_malformed_sections_reject_at_gate_without_type_errors(self):
        for section in ('governance', 'concentration_stop_conditions', 'exposure_limits', 'vdso', 'soak_periods', 'thin_liquidity'):
            for value in (None, False, 1, [], 'bad'):
                with self.subTest(section=section, value=value):
                    profile = copy.deepcopy(PROFILE);profile[section] = value
                    self.assertTrue(self.audit_errors(profile))

    def test_invalid_profile_is_rejected_before_snapshot_access(self):
        class UnreadableSnapshot:
            def get(self, *args):
                raise AssertionError('snapshot must not be read before profile validation')
        profile = copy.deepcopy(PROFILE);profile['asset_policy'] = 'unqualified'
        with self.assertRaises(ValueError):
            economic.evaluate(UnreadableSnapshot(), profile)

    def test_campaign_rejects_before_rng_or_profile_serialization(self):
        profile = copy.deepcopy(PROFILE);profile['profile_version'] = 'unqualified'
        with patch.object(campaign.random, 'Random', side_effect=AssertionError('rng reached')) as rng, \
             patch.object(campaign.json, 'dumps', side_effect=AssertionError('serialization reached')) as encode:
            with self.assertRaises(ValueError):
                campaign.run_campaign(10, 20260711, profile)
        rng.assert_not_called();encode.assert_not_called()

    def test_valid_campaign_keeps_canonical_profile_hash(self):
        import hashlib
        expected = hashlib.sha256(json.dumps(PROFILE, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        report = campaign.run_campaign(10, 20260711, PROFILE)
        self.assertEqual(report['profile_sha256'], expected)

    def metric_violations(self, weights):
        # Provider/floor declarations below are synthetic, not attestations.
        snapshot = {'providers': [dict(beneficial_owner=f'fixture-{i}', region=f'region-{i}',
            reward=w, capacity=w) for i, w in enumerate(weights)],
            'region_controls': {f'region-{i}': {'hardware_floor_enforced': True} for i in range(len(weights))}}
        return economic.evaluate(snapshot, PROFILE)['violations']

    def test_linked_share_boundary_stays_strictly_above_twenty_percent(self):
        self.assertFalse(any('linked-operator share' in s for s in self.metric_violations([4] + [1]*16)))
        self.assertTrue(any('linked-operator share' in s for s in self.metric_violations([4.001] + [1]*16)))

    def test_top_four_boundary_stays_strictly_above_fifty_percent(self):
        self.assertFalse(any('top-four share' in s for s in self.metric_violations([2]*4 + [1]*8)))
        self.assertTrue(any('top-four share' in s for s in self.metric_violations([2.001] + [2]*3 + [1]*8)))

    def test_hhi_boundary_stays_at_or_above_one_quarter(self):
        self.assertFalse(any('HHI' in s for s in self.metric_violations([1]*5)))
        self.assertTrue(any('HHI' in s for s in self.metric_violations([1]*4)))

    def test_regional_boundary_stays_strictly_above_thirty_percent(self):
        self.assertFalse(any('region region-0 reward share' in s for s in self.metric_violations([3] + [1]*7)))
        self.assertTrue(any('region region-0 reward share' in s for s in self.metric_violations([3.001] + [1]*7)))


def fields(obj=PROFILE, prefix=()):
    for key, value in obj.items():
        path = prefix + (key,)
        yield path, value
        if type(value) is dict:
            yield from fields(value, path)


def parent(profile, path):
    for key in path[:-1]:profile = profile[key]
    return profile


class RestrictedProfileContractTests(unittest.TestCase):
    def test_current_profile_is_accepted_without_mutation(self):
        before = copy.deepcopy(PROFILE)
        self.assertEqual(validate_testnet_profile(PROFILE), [])
        self.assertEqual(PROFILE, before)

    def test_every_leaf_wrong_value_and_json_type_is_rejected(self):
        for path, value in fields():
            if type(value) is dict:continue
            wrong = not value if type(value) is bool else value + 1 if type(value) in (int, float) else value + '-changed'
            for replacement in (wrong, None, False, True, 0, 1, 1.0, '', [], {}):
                if type(replacement) is type(value) and replacement == value:continue
                with self.subTest(path='.'.join(path), value=repr(replacement)):
                    profile = copy.deepcopy(PROFILE);parent(profile, path)[path[-1]] = replacement
                    self.assertTrue(validate_testnet_profile(profile))

    def test_every_field_is_required(self):
        for path, _ in fields():
            with self.subTest(path='.'.join(path)):
                profile = copy.deepcopy(PROFILE);del parent(profile, path)[path[-1]]
                self.assertTrue(validate_testnet_profile(profile))

    def test_every_object_rejects_unknown_fields(self):
        for path in [()] + [path for path, value in fields() if type(value) is dict]:
            with self.subTest(path='.'.join(path)):
                profile = copy.deepcopy(PROFILE);target = profile
                for key in path:target = target[key]
                target['unqualified_extension'] = False
                self.assertTrue(validate_testnet_profile(profile))

    def test_non_object_roots_and_sections_reject_without_coercion(self):
        for value in (None, False, True, 1, 1.0, '', [], ()):
            with self.subTest(value=value):
                self.assertTrue(validate_testnet_profile(value))

    def test_nonfinite_hhi_and_integral_float_controls_reject(self):
        for value in (float('nan'), float('inf'), float('-inf'), '0.25', True):
            with self.subTest(value=repr(value)):
                profile = copy.deepcopy(PROFILE);profile['concentration_stop_conditions']['hhi'] = value
                self.assertTrue(validate_testnet_profile(profile))
        profile = copy.deepcopy(PROFILE);profile['governance']['timelock_seconds'] = 172800.0
        self.assertTrue(validate_testnet_profile(profile))

    def test_stricter_alternative_is_not_silently_reinterpreted_as_profile_v1(self):
        for section, key, value in (('governance', 'timelock_seconds', 259200),
                                    ('exposure_limits', 'daily_aggregate_insurance_reserve_bps', 500),
                                    ('thin_liquidity', 'minimum_independent_providers', 6)):
            profile = copy.deepcopy(PROFILE);profile[section][key] = value
            self.assertTrue(validate_testnet_profile(profile))

    def test_error_order_is_deterministic_and_diagnostics_do_not_echo_untrusted_fields(self):
        profile = copy.deepcopy(PROFILE);profile['UNTRUSTED_DIAGNOSTIC_SENTINEL'] = 'not-for-diagnostics'
        del profile['asset_policy'];profile['vdso']['mode'] = 'not-for-diagnostics'
        errors = validate_testnet_profile(profile)
        self.assertEqual(errors, validate_testnet_profile(profile))
        self.assertNotIn('UNTRUSTED_DIAGNOSTIC_SENTINEL', str(errors))
        self.assertNotIn('not-for-diagnostics', str(errors))


if __name__ == '__main__':
    unittest.main()
