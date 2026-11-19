"""SQL-shape/transaction doubles and real public V5 cryptographic fixtures.

No PostgreSQL, native schema compilation, parallel database isolation, token,
provider, funding, signer custody or payment qualification follows. Only the
schema oracle and database transaction transport are replaced; journal._history
and policy/signature/current-generation verification execute unchanged.
"""
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal
from threading import RLock
import unittest
from unittest.mock import patch
import os

from cryptography.hazmat.primitives.asymmetric import ec

# Modules, not imported TestCase classes: avoid duplicate test collection.
from neuron.tests import test_payment_intent_v1 as P
from neuron.tests import test_effect_attempt_journal_v5 as F
from neuron.payments import ledger_v1 as L, ledger_schema_v1 as S
from neuron.effect_attempts_v5 import ObjectAttemptV5, NativeObjectRowV1
from neuron.effect_protocol_v3 import ObjectFenceV3, sign_receipt, fence_ack_subject
from neuron.effect_postgres_v3 import PostgresEffectDatabaseV3, EffectPersistenceErrorV3
from neuron.runtime_safety import RuntimeConfigurationError
from neuron.signed_receipts import ReceiptSignerV3


def synthetic_manifest():
    constraints = tuple(sorted((table, kind, 'SYNTHETIC-NOT-PG-COMPILED ' + str(n))
        for table, counts in S.CONSTRAINT_COUNTS.items()
        for kind, count in counts.items() for n in range(count)))
    return S.PaymentSchemaManifestV1(S.MIGRATION_HASH, P.h(b'SYNTHETIC compiler'),
        P.h(b'SYNTHETIC provenance'), 180000, constraints)


class PaymentCursor(F.JournalCursor):
    """Extends existing exact V5 read shapes with payment SQL; no SQL engine."""
    def __init__(self, rows, queries):
        super().__init__(rows)
        self.queries = queries

    def execute(self, query, params=()):
        self.queries.append((query, params))
        self.result = None; self.rowcount = -1
        if 'vams_payment_' not in query:
            return super().execute(query, params)
        if 'SELECT intent_bytes,approval_bytes' in query:
            row = self.rows.payments.get(params[0])
            self.result = None if row is None else tuple(row[n] for n in
                ('intent_bytes','approval_bytes','intent_id','amount','budget_id','state','credential_digest','revision'))
        elif 'SELECT key_digest' in query:
            self.result = next(((key,) for key, row in self.rows.payments.items()
                if row['operation_id'] == params[0] or row['attempt_id'] == params[1] or row['nonce_key'] == params[2]), None)
        elif 'SELECT denomination,reserved,revision' in query:
            self.result = self.rows.payment_budgets.get(params[0])
        elif 'SELECT amount' in query:
            self.result = [(row['amount'],) for row in self.rows.payments.values() if row['budget_id'] == params[0]][:257]
        elif 'SELECT event_seq,state' in query:
            self.result = list(self.rows.payment_events.get(params[0], []))[:33]
        elif query.lstrip().startswith('INSERT INTO public.vams_payment_budgets_v1'):
            assert params[0] not in self.rows.payment_budgets
            self.rows.payment_budgets[params[0]] = (params[1], Decimal(0), 0); self.rowcount = 1
        elif query.lstrip().startswith('UPDATE public.vams_payment_budgets_v1'):
            amount, revision, key, previous = params; row = self.rows.payment_budgets[key]
            self.rowcount = int(row[2] == previous)
            if self.rowcount: self.rows.payment_budgets[key] = (row[0], Decimal(amount), revision)
        elif query.lstrip().startswith('INSERT INTO public.vams_payment_intents_v1'):
            names = ('key_digest','operation_id','attempt_id','intent_id','budget_id','nonce_key','amount','intent_bytes','approval_bytes')
            row = dict(zip(names, params)); key = row['key_digest']
            assert key not in self.rows.payments
            assert row['operation_id'] in self.rows.work
            assert row['attempt_id'] in self.rows.attempts
            assert self.rows.attempts[row['attempt_id']][1] == row['operation_id']
            assert not any(old['operation_id'] == row['operation_id'] or old['attempt_id'] == row['attempt_id'] or
                           old['nonce_key'] == row['nonce_key'] for old in self.rows.payments.values())
            row.update(state='reserved', credential_digest=None, revision=1, amount=Decimal(row['amount']))
            self.rows.payments[key] = row; self.rowcount = 1
        elif query.lstrip().startswith('INSERT INTO public.vams_payment_events_v1'):
            intent, sequence, state, evidence, digest = params
            rows = self.rows.payment_events.setdefault(intent, [])
            assert not any(row[0] == sequence for row in rows)
            rows.append((sequence, state, evidence, digest)); self.rowcount = 1
        elif query.lstrip().startswith('UPDATE public.vams_payment_intents_v1'):
            if "state='exposed'" in query:
                credential, revision, key, previous = params; state = 'exposed'
            else:
                revision, key, previous = params; state = 'unknown'
                credential = self.rows.payments[key]['credential_digest']
            row = self.rows.payments[key]; self.rowcount = int(row['revision'] == previous)
            if self.rowcount: row.update(state=state, credential_digest=credential, revision=revision)
        else:
            raise AssertionError('unexpected payment SQL shape: ' + query)


class PaymentLedgerV1Tests(unittest.TestCase):
    def setUp(self):
        self.p = P.PaymentIntentV1Tests('runTest'); self.p.setUp(); self.addCleanup(self.p.doCleanups)
        self.f = F.AttemptJournalV5Test('runTest'); self.f.setUp(); self.addCleanup(self.f.doCleanups)
        self.rows = self.f.rows
        self.rows.payments = {}; self.rows.payment_budgets = {}; self.rows.payment_events = {}
        self.queries = []; self.guard = RLock(); self.commit_failure = None
        self.authority_signer = ReceiptSignerV3(ec.derive_private_key(1, ec.SECP256K1()))
        self.provider_signer = ReceiptSignerV3(ec.derive_private_key(2, ec.SECP256K1()))
        self.second_resource = P.h(b'SYNTHETIC second immutable object')
        self.f.scope = replace(self.f.scope, resources=tuple(sorted((self.f.proposal.resource_id, self.second_resource))))
        self.f.generation_id = F.J.commitment(F.J.GENERATION_DOMAIN_V5, self.f.scope.canonical_bytes())
        self.rows.attempts.clear(); self.rows.work.clear(); self.rows.generations.clear(); self.rows.heads.clear(); self.rows.events.clear()
        self.f._seed_attempt()
        self._active_generation()
        self.f.now = self.f.proposal.context.issued_at + 1
        self.p.attempt = self.f.attempt; self.p.intent = self.p.make_intent(); self.p.now = self.f.now
        self.schema = synthetic_manifest(); self.schema.validate()
        self.schema_calls = 0
        owner = self
        @contextmanager
        def transaction(database):
            assert database is owner.f.database
            with owner.guard:
                before = deepcopy(vars(owner.rows))
                try:
                    yield PaymentCursor(owner.rows, owner.queries)
                    if owner.commit_failure == 'uncertain':
                        # Simulate commit accepted by DB but acknowledgement lost.
                        raise EffectPersistenceErrorV3('COMMIT')
                    if owner.commit_failure == 'rollback':
                        raise RuntimeError('SYNTHETIC precommit failure')
                except BaseException:
                    if owner.commit_failure != 'uncertain':
                        vars(owner.rows).clear(); vars(owner.rows).update(before)
                    raise
        def schema_oracle(ledger, cursor):
            # Explicit replacement of native PG catalog/ACL/schema inspection.
            owner.schema_calls += 1
            ledger.schema_manifest.validate()
        self.tx = patch.object(PostgresEffectDatabaseV3, 'transaction', transaction); self.tx.start(); self.addCleanup(self.tx.stop)
        self.oracle = patch.object(L.PaymentLedgerV1, '_verify_schema', schema_oracle); self.oracle.start(); self.addCleanup(self.oracle.stop)
        self.no_connect = patch.object(PostgresEffectDatabaseV3, '_connect', side_effect=AssertionError('NO NATIVE CONNECTION IN FIXTURE'))
        self.no_connect.start(); self.addCleanup(self.no_connect.stop)
        self.ledger = self.build_ledger()
        self.key = self.key_for(b'purchase-one')

    def _active_generation(self):
        c = self.f.scope.template
        fence = ObjectFenceV3.from_context(c, self.f.scope.fencing_token)
        common = dict(provider=c.provider_id, epoch=c.authority_epoch, policy=c.policy_version,
                      fence=self.f.scope.fencing_token, issued_at=c.issued_at, expires_at=c.expires_at)
        update = sign_receipt(self.authority_signer, purpose=2, subject=fence.digest, **common)
        ack = sign_receipt(self.provider_signer, purpose=3, subject=fence_ack_subject(fence, update), **common)
        self.rows.generations[(self.f.scope.scope_id, self.f.generation_id)] = (
            self.f.scope.canonical_bytes(), 'active', fence.canonical_bytes(), update.canonical_bytes(),
            ack.canonical_bytes(), self.f.generation_id, 1, None, None, None)

    def build_ledger(self, policy=None, clock=None):
        return L.PaymentLedgerV1(self.f.database, self.f.journal, policy or self.p.binding(), self.schema,
                                 clock=clock or (lambda: self.f.now))

    def key_for(self, value):
        c = self.p.intent
        return L.PaymentIdempotencyKeyV1(c.actor_root, c.host_domain, P.h(b'SYNTHETIC immutable-object funding'), value)

    def reserve(self, *, ledger=None, key=None, intent=None, attempt=None):
        value = intent or self.p.intent
        return (ledger or self.ledger).reserve(key or self.key, value, attempt or self.p.attempt, self.p.approval(value))

    def second(self, *, amount=100, capability=None, nonce=None):
        old = self.f.proposal
        proposal = replace(old, resource_id=self.second_resource, context=replace(old.context, nonce=P.h(b'SYNTHETIC second object nonce')))
        proposal = replace(proposal, context=replace(proposal.context, action_hash=proposal.action_hash)); proposal.validate()
        c = proposal.context
        admission = sign_receipt(self.authority_signer, purpose=1, subject=proposal.digest, provider=c.provider_id,
            epoch=c.authority_epoch, policy=c.policy_version, fence=proposal.fencing_token, issued_at=c.issued_at, expires_at=c.expires_at)
        row = NativeObjectRowV1(c.chain_id, c.target, P.h(b'SYNTHETIC second allocation'), 0)
        attempt = ObjectAttemptV5(row, proposal, admission, 1, None)
        saved = self.f.proposal, self.f.attempt, self.f.native_row, self.f.receipts
        self.f.proposal, self.f.attempt, self.f.native_row = proposal, attempt, row
        self.f.receipts = dict(self.f.receipts, admission=admission)
        self.f._seed_attempt(); self._active_generation()
        self.f.proposal, self.f.attempt, self.f.native_row, self.f.receipts = saved
        head = self.rows.heads[self.f.scope.scope_id]
        self.rows.heads[self.f.scope.scope_id] = (head[0], head[1], head[2], sum(r[19] for r in self.rows.attempts.values()), 0)
        intent = self.p.make_intent(attempt=attempt, capability=capability, amount=amount,
                                    nonce=nonce or P.h(b'SYNTHETIC second payment nonce'))
        return attempt, intent

    def assert_no_payment(self):
        self.assertEqual(self.rows.payments, {}); self.assertEqual(self.rows.payment_budgets, {})
        self.assertEqual(self.rows.payment_events, {})

    def test_reservation_is_idempotent_and_never_a_release_capability(self):
        effect_head = deepcopy(self.rows.heads)
        first = self.reserve(); second = self.reserve()
        self.assertEqual(first, second); self.assertEqual(len(self.rows.payments), 1)
        self.assertEqual(len(self.rows.payment_events[first.intent.digest]), 1)
        self.assertEqual(self.rows.heads, effect_head)  # No second execution-cost reservation.
        self.assertFalse(first.signing_authorized); self.assertFalse(first.native_payment_verified)
        self.assertEqual(first.state, 'reserved'); self.assertGreater(self.schema_calls, 0)

    def test_changed_terms_same_key_conflict_preserves_original(self):
        first = self.reserve(); before = deepcopy(vars(self.rows))
        changed = self.p.make_intent(amount=99)
        with self.assertRaises(L.PaymentConflict): self.reserve(intent=changed)
        self.assertEqual(vars(self.rows), before); self.assertEqual(self.ledger.lookup(self.key), first)

    def test_another_key_cannot_fund_same_operation(self):
        self.reserve()
        with self.assertRaises(L.PaymentConflict): self.reserve(key=self.key_for(b'other-key'))
        self.assertEqual(len(self.rows.payments), 1)

    def test_same_chain_asset_payer_nonce_cannot_fund_second_operation(self):
        self.reserve(); attempt, intent = self.second(nonce=self.p.intent.nonce)
        with self.assertRaises(L.PaymentConflict): self.reserve(key=self.key_for(b'two'), intent=intent, attempt=attempt)
        self.assertEqual(len(self.rows.payments), 1)

    def test_shared_monetary_limit_and_locking_shapes(self):
        cap = replace(self.p.capability, max_aggregate=150)
        ledger = self.build_ledger(self.p.binding(capability=cap))
        first = self.p.make_intent(capability=cap); self.reserve(ledger=ledger, intent=first)
        attempt, second = self.second(capability=cap)
        with self.assertRaisesRegex(ValueError, 'budget exhausted'):
            self.reserve(ledger=ledger, key=self.key_for(b'two'), intent=second, attempt=attempt)
        self.assertEqual(self.rows.payment_budgets[first.budget_identity][1], Decimal(100))
        shapes = [q for q, _ in self.queries]
        self.assertTrue(any('pg_advisory_xact_lock' in q for q in shapes))
        self.assertTrue(any('SELECT denomination,reserved,revision' in q and 'FOR UPDATE' in q for q in shapes))
        self.assertTrue(any('revision=%s' in q and 'UPDATE public.vams_payment_budgets' in q for q in shapes))

    def test_uint256_maximum_is_preserved_as_exact_numeric(self):
        cap = replace(self.p.capability, max_per_call=S.UINT256_MAX, max_aggregate=S.UINT256_MAX)
        ledger = self.build_ledger(self.p.binding(capability=cap)); intent = self.p.make_intent(capability=cap, amount=S.UINT256_MAX)
        record = self.reserve(ledger=ledger, intent=intent)
        self.assertEqual(record.intent.amount, S.UINT256_MAX)
        self.assertEqual(self.rows.payment_budgets[intent.budget_identity][1], Decimal(S.UINT256_MAX))
        with self.assertRaises(ValueError): L._money(1.0)
        with self.assertRaises(ValueError): L._money(True)
        with self.assertRaises(ValueError): L._money(Decimal('1.1'))

    def test_denomination_cannot_change_under_existing_budget_identity(self):
        self.reserve()
        cap = replace(self.p.capability, asset=P.address(77))
        attempt, intent = self.second(capability=cap)
        with self.assertRaisesRegex(ValueError, 'denomination'):
            self.reserve(ledger=self.build_ledger(self.p.binding(capability=cap)), key=self.key_for(b'two'), intent=intent, attempt=attempt)

    def test_real_history_rejects_missing_forged_or_draining_facts(self):
        pristine = deepcopy(vars(self.rows))
        for defect in ('missing', 'forged', 'draining'):
            vars(self.rows).clear(); vars(self.rows).update(deepcopy(pristine))
            if defect == 'missing': self.rows.attempts.clear()
            elif defect == 'forged':
                row = list(self.rows.attempts[self.p.attempt.attempt_id]); row[16] = P.h(b'forged admission')
                self.rows.attempts[self.p.attempt.attempt_id] = tuple(row)
            else:
                key = (self.f.scope.scope_id, self.f.generation_id)
                row = list(self.rows.generations[key]); row[1] = 'draining'; self.rows.generations[key] = tuple(row)
            with self.subTest(defect=defect), self.assertRaises(ValueError): self.reserve()
            self.assert_no_payment()

    def test_current_policy_denies_before_writes_and_between_checks_rolls_back(self):
        for after in (False, True):
            state = self.p.state()
            source = P.FixturePolicy(state if after else replace(state, enabled=False), after=replace(state, enabled=False) if after else None)
            with self.subTest(after=after), self.assertRaises(ValueError):
                self.reserve(ledger=self.build_ledger(self.p.binding(source=source)))
            self.assert_no_payment()

    def test_policy_change_after_insert_rolls_back_reservation(self):
        state = self.p.state()
        class LaterPolicy(P.PaymentPolicySourceV1):
            reads = 0
            def read_current(self):
                self.reads += 1
                return state if self.reads <= 2 else replace(state, enabled=False)
        with self.assertRaises(ValueError): self.reserve(ledger=self.build_ledger(self.p.binding(source=LaterPolicy())))
        self.assert_no_payment()
        self.assertTrue(any(q.lstrip().startswith('INSERT INTO public.vams_payment_intents') for q, _ in self.queries))

    def test_expiry_and_policy_denial_leave_readonly_original_obligation(self):
        first = self.reserve(); self.f.now = first.intent.valid_before + 1
        disabled = self.build_ledger(self.p.binding(source=P.FixturePolicy(replace(self.p.state(), enabled=False))))
        self.assertEqual(disabled.lookup(self.key), first)
        self.assertEqual(self.reserve(ledger=disabled), first)  # Lookup retry cannot grant signing.
        with self.assertRaises(ValueError):
            disabled.mark_potentially_released(self.key, first.intent, self.p.attempt, self.p.approval(), P.h(b'credential'))
        self.assertEqual(self.rows.payment_budgets[first.intent.budget_identity][1], Decimal(100))

    def test_exposure_revalidates_and_second_credential_is_refused(self):
        self.reserve(); credential = P.h(b'potentially released credential')
        record = self.ledger.mark_potentially_released(self.key, self.p.intent, self.p.attempt, self.p.approval(), credential)
        self.assertEqual(record.state, 'exposed'); self.assertFalse(record.signing_authorized)
        self.assertEqual(self.ledger.mark_potentially_released(self.key, self.p.intent, self.p.attempt, self.p.approval(), credential), record)
        with self.assertRaises(ValueError):
            self.ledger.mark_potentially_released(self.key, self.p.intent, self.p.attempt, self.p.approval(), P.h(b'another credential'))
        self.assertEqual(self.ledger.lookup(self.key), record)

    def test_disabled_policy_blocks_new_exposure_without_erasing_reservation(self):
        self.reserve(); disabled = self.build_ledger(self.p.binding(source=P.FixturePolicy(replace(self.p.state(), enabled=False))))
        with self.assertRaises(ValueError):
            disabled.mark_potentially_released(self.key, self.p.intent, self.p.attempt, self.p.approval(), P.h(b'credential'))
        self.assertEqual(disabled.lookup(self.key).state, 'reserved')

    def test_unknown_is_durable_nonrelease_and_never_repaid_or_erased(self):
        self.reserve(); first = self.ledger.record_unknown(self.key, P.h(b'RPC timeout'))
        self.assertEqual(first.state, 'unknown'); self.assertFalse(first.signing_authorized)
        self.assertEqual(self.ledger.record_unknown(self.key, P.h(b'new observation')), first)
        with self.assertRaises(ValueError):
            self.ledger.mark_potentially_released(self.key, self.p.intent, self.p.attempt, self.p.approval(), P.h(b'credential'))
        self.assertEqual(self.rows.payment_budgets[first.intent.budget_identity][1], Decimal(100))

    def test_unknown_history_cannot_invent_or_rebind_credential(self):
        self.reserve(); self.ledger.record_unknown(self.key, P.h(b'uncertain'))
        self.rows.payments[self.key.digest]['credential_digest'] = P.h(b'invented')
        with self.assertRaises(ValueError): self.ledger.lookup(self.key)

    def test_unknown_after_exposure_preserves_original_credential(self):
        self.reserve(); original = P.h(b'original credential')
        self.ledger.mark_potentially_released(self.key, self.p.intent, self.p.attempt, self.p.approval(), original)
        self.ledger.record_unknown(self.key, P.h(b'uncertain'))
        self.assertEqual(self.ledger.lookup(self.key).credential_digest, original)
        for changed in (None, P.h(b'replacement credential')):
            self.rows.payments[self.key.digest]['credential_digest'] = changed
            with self.subTest(changed=changed), self.assertRaises(ValueError): self.ledger.lookup(self.key)

    def test_clock_regression_rolls_back_reservation_and_exposure(self):
        start = self.f.proposal.context.issued_at + 5
        values = iter((start, start - 1))
        with self.assertRaisesRegex(ValueError, 'clock moved backwards'):
            self.reserve(ledger=self.build_ledger(clock=lambda: next(values)))
        self.assert_no_payment(); self.reserve()
        values = iter((start, start - 1))
        with self.assertRaisesRegex(ValueError, 'clock moved backwards'):
            self.build_ledger(clock=lambda: next(values)).mark_potentially_released(
                self.key, self.p.intent, self.p.attempt, self.p.approval(), P.h(b'credential'))
        self.assertEqual(self.ledger.lookup(self.key).state, 'reserved')

    def test_commit_uncertainty_propagates_and_lookup_recovers_single_row(self):
        self.commit_failure = 'uncertain'
        with self.assertRaises(EffectPersistenceErrorV3) as raised: self.reserve()
        self.assertEqual(raised.exception.outcome, 'UNKNOWN')
        self.commit_failure = None
        self.assertEqual(self.ledger.lookup(self.key).state, 'reserved')
        self.assertEqual(self.reserve().revision, 1); self.assertEqual(len(self.rows.payments), 1)

    def test_precommit_exception_rolls_back_all_payment_writes(self):
        self.commit_failure = 'rollback'
        with self.assertRaisesRegex(RuntimeError, 'precommit'): self.reserve()
        self.assert_no_payment()

    def test_constructor_key_separation_and_live_guard(self):
        verifier = P.PaymentApprovalVerifierV1(self.f.identity.provider.public_key_bytes)
        with self.assertRaises(ValueError): self.build_ledger(self.p.binding(verifier=verifier))
        configured = self.p.binding()
        with patch.dict(os.environ, {'VAMS_ENV': 'testnet'}, clear=True):
            with self.assertRaises(RuntimeConfigurationError): self.build_ledger(configured)
            with self.assertRaises(RuntimeConfigurationError): self.ledger.lookup(self.key)

    def test_canonical_history_tamper_and_manifest_fk_contract(self):
        self.reserve(); rows = self.rows.payment_events[self.p.intent.digest]
        row = list(rows[0]); row[2] = P.h(b'changed evidence'); rows[0] = tuple(row)
        with self.assertRaises(ValueError): self.ledger.lookup(self.key)
        with self.assertRaises(ValueError): replace(self.schema, constraints=self.schema.constraints[:-1]).validate()
        changed = list(self.schema.constraints); table, _, definition = changed[0]; changed[0] = (table, 'f', definition)
        with self.assertRaises(ValueError): replace(self.schema, constraints=tuple(sorted(changed))).validate()
        ddl = '\n'.join(S.DDL)
        self.assertIn('REFERENCES public.vams_effect_v5_authority_work(operation_id)', ddl)
        self.assertIn('REFERENCES public.vams_effect_v5_authority_attempts(operation_id,attempt_id)', ddl)
        self.assertIn('NUMERIC(78,0)', ddl)
        self.assertNotIn("'paid'", ddl); self.assertNotIn("'released'", ddl)
        for name in ('pay', 'fund', 'release', 'confirm_payment', 'sign'):
            self.assertFalse(hasattr(self.ledger, name))


if __name__ == '__main__':
    unittest.main()
