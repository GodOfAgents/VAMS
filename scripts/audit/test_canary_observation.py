"""Synthetic timestamp/report consistency tests, not observed canary evidence."""
from datetime import datetime,timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.audit import audit_program as audit


class FixedClock(datetime):
    @classmethod
    def now(cls,tz=None):return cls(2026,11,1,tzinfo=timezone.utc)


class CanaryObservationTests(unittest.TestCase):
    def report(self):
        return {'schema_version':'1.0.0','commit_sha':'a'*40,
            'started_at':'2026-10-24T00:00:00Z','ended_at':'2026-10-31T00:00:00Z',
            'consecutive_days':7,'stop_conditions_triggered':False,
            'drills':{name:True for name in audit.REQUIRED_DRILLS}}

    def check(self,report):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'canary-fixture.json';path.write_text(json.dumps(report),encoding='utf-8')
            with patch.object(audit,'datetime',FixedClock):
                return audit._validate_canary_report(path,'a'*40)

    def reject(self,report):self.assertTrue(self.check(report))

    def test_exact_seven_elapsed_days_pass(self):self.assertEqual(self.check(self.report()),[])

    def test_identical_endpoints_cannot_mean_seven_days(self):
        r=self.report();r['ended_at']=r['started_at'];self.reject(r)

    def test_one_second_short_does_not_round_up(self):
        r=self.report();r['ended_at']='2026-10-30T23:59:59Z';self.reject(r)

    def test_submicrosecond_shortfall_does_not_round_up(self):
        r=self.report();r['started_at']='2026-10-24T00:00:00.000000001Z';self.reject(r)

    def test_submicrosecond_interval_can_match_exactly(self):
        r=self.report();r['started_at']='2026-10-24T00:00:00.000000001Z'
        r['ended_at']='2026-10-31T00:00:00.000000001Z';self.assertEqual(self.check(r),[])

    def test_fractional_precision_cannot_hide_an_overclaimed_day(self):
        r=self.report();r['started_at']='2026-10-24T00:00:00.000000001Z'
        r['ended_at']='2026-11-01T00:00:00Z';r['consecutive_days']=8;self.reject(r)

    def test_missing_each_required_field_rejects(self):
        for field in self.report():
            r=self.report();del r[field]
            with self.subTest(field=field):self.reject(r)

    def test_claimed_count_must_be_an_integer(self):
        for days in (True,False,7.0,7.5,'7',None,[],{},float('nan'),float('inf')):
            r=self.report();r['consecutive_days']=days
            with self.subTest(days=repr(days)):self.reject(r)

    def test_count_cannot_exceed_elapsed_whole_days(self):
        r=self.report();r['consecutive_days']=8;self.reject(r)

    def test_extra_partial_day_is_not_a_complete_day(self):
        r=self.report();r['ended_at']='2026-10-31T23:59:59.999999Z';r['consecutive_days']=8;self.reject(r)

    def test_aware_offset_normalizes_to_the_same_elapsed_interval(self):
        r=self.report();r['started_at']='2026-10-24T05:30:00+05:30'
        self.assertEqual(self.check(r),[])

    def test_offset_difference_does_not_create_a_seventh_day(self):
        r=self.report();r['started_at']='2026-10-24T00:00:00-01:00';self.reject(r)

    def test_naive_invalid_and_non_rfc3339_dates_reject(self):
        for value in ('2026-10-24','2026-10-24T00:00:00','not-a-time','2026-02-30T00:00:00Z',
                '2026-W43-6T00:00:00Z','2026-10-24 00:00:00Z',
                '2026-10-24T01:00:00+00:60','2026-10-24T01:39:00+00:99',0,None):
            r=self.report();r['started_at']=value
            with self.subTest(value=value):self.reject(r)

    def test_reversed_time_rejects(self):
        r=self.report();r['started_at'],r['ended_at']=r['ended_at'],r['started_at'];self.reject(r)

    def test_future_end_cannot_claim_completed_observation(self):
        r=self.report();r['started_at']='2026-10-26T00:00:00Z';r['ended_at']='2026-11-02T00:00:00Z';self.reject(r)

    def test_end_equal_to_current_time_is_allowed(self):
        r=self.report();r['started_at']='2026-10-25T00:00:00Z';r['ended_at']='2026-11-01T00:00:00Z'
        self.assertEqual(self.check(r),[])

    def test_schema_version_and_unknown_top_level_keys_reject(self):
        r=self.report();r['schema_version']='0.0.0';self.reject(r)
        r=self.report();r['synthetic_override']=True;self.reject(r)

    def test_existing_stop_commit_and_drill_requirements_remain(self):
        for field,value in (('stop_conditions_triggered',True),('commit_sha','b'*40)):
            r=self.report();r[field]=value;self.reject(r)
        for drill in audit.REQUIRED_DRILLS:
            r=self.report();r['drills'][drill]=False;self.reject(r)

    def test_extra_boolean_drill_is_schema_compatible(self):
        r=self.report();r['drills']['extra-operator-drill']=True
        self.assertEqual(self.check(r),[])

    def test_extra_non_boolean_drill_rejects(self):
        r=self.report();r['drills']['extra-operator-drill']=1;self.reject(r)

    def test_no_actual_observation_or_signature_is_created(self):
        self.assertEqual(self.check(self.report()),[])
        # This helper validates consistency; it does not approve any real report.
        self.assertEqual(set(self.report()),{'schema_version','commit_sha','started_at','ended_at',
            'consecutive_days','stop_conditions_triggered','drills'})


if __name__=='__main__':unittest.main()
