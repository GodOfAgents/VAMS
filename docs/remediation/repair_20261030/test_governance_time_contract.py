"""Reference model checks. Never count these as native validator qualification."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import random
import unittest

from ..repair_20261028.governance_contract import (
    ContractError, DELAY_MS, LIFETIME_MS, add_lock, fixture, intent_preimage, queue_intent,
)
from .governance_time_contract import (
    MAX_WIDTH_MS, U64_MAX, ValidityWindow, entirely_at_or_after,
    entirely_before, expiry_allowed, queue_for_window,
)


class GovernanceTimeTests(unittest.TestCase):
    def setUp(self):
        self.config, p = fixture()
        self.passed = replace(add_lock(self.config, p, self.config.members[0], 100, True), passed=True)

    def test_source_counterexamples_are_removed_by_conservative_anchor(self):
        for lower, upper in ((2000, 2100), (2000, 302000)):
            with self.subTest(upper=upper):
                old = queue_intent(self.config, self.passed, lower)
                inclusion = upper - 1
                self.assertLess(old.execute_after - inclusion, DELAY_MS)
                new = queue_for_window(self.config, self.passed, ValidityWindow(lower, upper))
                self.assertGreaterEqual(new.execute_after - inclusion, DELAY_MS)
                self.assertEqual(new.queue_time, upper)

    def test_interval_normal_form_and_numeric_boundaries(self):
        for window in (ValidityWindow(2000, 2000), ValidityWindow(2001, 2000),
                       ValidityWindow(2000, 302001), ValidityWindow(-1, 100),
                       ValidityWindow(2000, U64_MAX + 1), ValidityWindow(True, 100),
                       ValidityWindow(2000.0, 2100), ValidityWindow(None, 2100),
                       ValidityWindow(2000, float('inf')), ValidityWindow(2000, 2100, False),
                       ValidityWindow(2000, 2100, True, True), ValidityWindow(2000, 2100, 1),
                       ValidityWindow(2000, 2100, True, 0)):
            with self.subTest(window=window), self.assertRaises(ContractError):
                window.validate()

    def test_one_millisecond_and_maximum_width_windows(self):
        for width in (1, MAX_WIDTH_MS):
            window = ValidityWindow(2000, 2000 + width)
            intent = queue_for_window(self.config, self.passed, window)
            self.assertEqual(intent.execute_after, window.upper + DELAY_MS)

    def test_latest_nonoverflowing_queue_anchor_and_next_millisecond(self):
        upper = U64_MAX - DELAY_MS - LIFETIME_MS
        intent = queue_for_window(self.config, self.passed, ValidityWindow(upper - 100, upper))
        self.assertEqual(intent.execute_after + intent.lifetime, U64_MAX)
        with self.assertRaises(ContractError):
            queue_for_window(self.config, self.passed, ValidityWindow(upper - 99, upper + 1))

    def test_vote_deadline_entire_window_semantics(self):
        self.assertTrue(entirely_before(ValidityWindow(1999, 2000), 2000))
        self.assertFalse(entirely_before(ValidityWindow(2000, 2001), 2000))
        self.assertFalse(entirely_before(ValidityWindow(1999, 2001), 2000))
        self.assertFalse(entirely_at_or_after(ValidityWindow(1999, 2001), 2000))
        self.assertTrue(entirely_at_or_after(ValidityWindow(2000, 2001), 2000))

    def test_queue_cannot_straddle_or_precede_voting_deadline(self):
        for window in (ValidityWindow(1900, 2000), ValidityWindow(1999, 2100)):
            with self.subTest(window=window), self.assertRaises(ContractError):
                queue_for_window(self.config, self.passed, window)
        queue_for_window(self.config, self.passed, ValidityWindow(2000, 2001))

    def test_expiry_uses_entire_window_after_conservative_lifetime(self):
        intent = queue_for_window(self.config, self.passed, ValidityWindow(2000, 2100))
        end = intent.execute_after + intent.lifetime
        self.assertEqual(end, 777602100)
        self.assertFalse(expiry_allowed(intent, ValidityWindow(end - 1, end)))
        self.assertFalse(expiry_allowed(intent, ValidityWindow(end - 1, end + 1)))
        self.assertTrue(expiry_allowed(intent, ValidityWindow(end, end + 1)))

    def test_seeded_inclusion_property(self):
        rng = random.Random(20261030)
        for _ in range(2000):
            lower = rng.randrange(2000, U64_MAX - DELAY_MS - LIFETIME_MS - MAX_WIDTH_MS)
            upper = lower + rng.randrange(1, MAX_WIDTH_MS + 1)
            intent = queue_for_window(self.config, self.passed, ValidityWindow(lower, upper))
            for inclusion in (lower, upper - 1, rng.randrange(lower, upper)):
                self.assertGreaterEqual(intent.execute_after - inclusion, DELAY_MS)
                self.assertLessEqual(intent.execute_after - inclusion, DELAY_MS + MAX_WIDTH_MS)

    def test_historical_and_upper_anchored_vectors_are_distinct_and_stable(self):
        vectors = json.loads((Path(__file__).parent / 'GOVERNANCE-TIME-VECTORS.json').read_text(encoding='utf-8'))
        for row, anchor in zip(vectors['asset_vectors'], (2000, 2100), strict=True):
            intent = queue_intent(self.config, self.passed, anchor)
            raw = intent_preimage(self.config, intent)
            self.assertEqual(raw.hex(), row['preimage_hex'])
            self.assertEqual(hashlib.blake2b(raw, digest_size=32).hexdigest(), row['digest_hex'])
        self.assertNotEqual(vectors['asset_vectors'][0]['digest_hex'], vectors['asset_vectors'][1]['digest_hex'])

    def test_queue_retains_proposal_and_authority_scope_checks(self):
        for config, proposal in ((replace(self.config, policy_epoch=3), self.passed),
                                 (self.config, replace(self.passed, passed=False)),
                                 (self.config, replace(self.passed, target_domain=b'other'))):
            with self.subTest(proposal=proposal, config=config), self.assertRaises(ContractError):
                queue_for_window(config, proposal, ValidityWindow(2000, 2100))
