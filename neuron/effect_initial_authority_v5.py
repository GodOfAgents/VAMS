"""Atomic initial local budget/admission writer, not native funded dispatch.

Fresh V5 scopes must already be installed and acknowledged under an authenticated
host policy. Scope installation/renewal, authenticated native funding, retry after
absence, provider dispatch and cross-host migration remain separate components.
This candidate has no live mode or automatic execution retry.
"""
from neuron.effect_attempt_journal_v5 import PostgresAttemptJournalV5, EVENT_INSERT
from neuron.effect_attempt_events_v5 import AttemptEventV5, reserved_payload
from neuron.effect_attempts_v5 import NativeObjectRowV1, ObjectAttemptV5, logical_work
from neuron.effect_authority_store_v5 import WORK5,ATTEMPTS5,HEADS5,MAX_GENERATION_ATTEMPTS5
from neuron.effect_authority_v3 import CurrentAuthorityPolicyV1,ReconciliationRequiredV3
from neuron.effect_protocol_v3 import (
    EffectV3Error,ObjectEffectV3,ObjectFenceV3,sign_receipt,verify_admission,
)
from neuron.signed_receipts import ReceiptSignerV3
from neuron.effect_provider_v3 import ObjectProviderIdentityV3


class PostgresInitialAttemptAuthorityV5(PostgresAttemptJournalV5):
    _immutable_runtime_fields=PostgresAttemptJournalV5._immutable_runtime_fields|frozenset({'_signer','_policy'})

    def __init__(self,database,identity,authority_signer,policy,**configuration):
        # Base construction binds the exact store/roles/check/native identity and
        # rejects live mode before any credential release, connection or signing.
        if type(identity) is not ObjectProviderIdentityV3:
            raise EffectV3Error('typed authority/provider public identity required')
        if type(authority_signer) is not ReceiptSignerV3 or authority_signer.verifier()!=identity.authority:
            raise EffectV3Error('matching distinct authority signer required')
        if not isinstance(policy,CurrentAuthorityPolicyV1):
            raise EffectV3Error('authenticated current host governance policy required')
        self._signer=authority_signer
        self._policy=policy
        super().__init__(database,identity,**configuration)

    def _current_policy(self,generation,proposal,now):
        if generation.status!='active':
            raise EffectV3Error('initial admission requires acknowledged active authority')
        scope=generation.scope
        scope.permits(proposal,now)
        if not scope.template.issued_at<=now<scope.template.expires_at:
            raise EffectV3Error('authority scope is no longer current')
        if self._policy.assert_scope_allowed(scope,now) is not None:
            raise EffectV3Error('unsupported governed scope decision')
        if self._policy.assert_allowed(proposal,now) is not None:
            raise EffectV3Error('unsupported current action decision')
        current=self._now()
        if current<now:raise EffectV3Error('clock moved backwards during admission validation')
        scope.permits(proposal,current)
        return current

    def reserve_initial_attempt(self,proposal,row):
        """Persist exact initial local obligation before returning its signature.

        This reserves non-token governed cost, not on-chain money. A returned
        admission never authorizes provider dispatch without authentic finalized
        native funding and fresh policy checks on both actual caller routes.
        """
        if type(proposal) is not ObjectEffectV3 or type(row) is not NativeObjectRowV1:
            raise EffectV3Error('typed object proposal and exact native row required')
        proposal.validate();row.validate()
        c=proposal.context;i=self.identity
        if (c.provider_id,c.host_domain,c.runtime_id,c.target,c.chain_id)!=(
                i.provider_id,i.host_domain,i.runtime_id,i.target,i.chain_id):
            raise EffectV3Error('proposal differs from configured authority/provider')
        if (row.chain_id,row.settlement)!=(c.chain_id,c.target):
            raise EffectV3Error('native row differs from proposal host')
        scope_id=ObjectFenceV3.from_context(c,proposal.fencing_token).scope_id
        proposal.require_current(self._now())
        with self.database.transaction() as cursor:
            # Same operation->scope order as terminal reconciliation. Immutable
            # facts never require UPDATE privileges or SELECT FOR UPDATE.
            self._lock_operation(cursor,proposal.operation_id)
            self._lock_scope(cursor,scope_id)
            head=self._load_head(cursor,scope_id,for_update=True)
            generation=self._load_generation(cursor,scope_id,head[0],self._now())
            if (head[1]!=c.budget_unit or head[2]!=generation.scope.budget_limit):
                raise EffectV3Error('head budget differs from canonical governed grant')
            self._current_policy(generation,proposal,self._now())
            cursor.execute(f'''SELECT attempt_id FROM {ATTEMPTS5} WHERE operation_id=%s
                ORDER BY attempt_no DESC LIMIT 2''',(proposal.operation_id,))  # nosec B608 # fixed SQL identifier; enforced by test_effect_sql_identifier_guard
            existing=cursor.fetchall()
            if type(existing) is not list or len(existing)>1:
                raise ReconciliationRequiredV3('existing attempt chain requires authenticated reconciliation')
            if existing:
                from neuron.effect_protocol_v3 import hash32
                if type(existing[0]) not in (tuple,list) or len(existing[0])!=1:
                    raise EffectV3Error('existing attempt lookup has invalid shape')
                existing_id=hash32(existing[0][0],'stored initial attempt')
                old,_,_=self._history(cursor,existing_id,self._now())
                if (old.attempt.ordinal!=1 or old.attempt.proposal!=proposal or old.attempt.row!=row or
                        old.events[-1].kind!='reserved' or old.scope_generation_id!=generation.generation_id):
                    raise ReconciliationRequiredV3('existing obligation is lookup-only; no automatic reissue')
                self._current_policy(generation,proposal,self._now())
                verify_admission(proposal,old.attempt.admission,self.identity.authority,self._now())
                result=old.attempt
            else:
                cursor.execute(f'SELECT logical_work FROM {WORK5} WHERE operation_id=%s',(proposal.operation_id,))  # nosec B608 # fixed SQL identifier; enforced by test_effect_sql_identifier_guard
                if cursor.fetchone() is not None or self._completion_row(cursor,proposal.operation_id) is not None:
                    raise ReconciliationRequiredV3('orphaned or completed logical work cannot be replaced')
                cost=proposal.cost_units
                if cost>head[2]-head[4]-head[3]:raise EffectV3Error('shared governed budget exhausted')
                cursor.execute(f'''SELECT COUNT(*) FROM {ATTEMPTS5}
                    WHERE scope_id=%s AND generation_id=%s''',(scope_id,generation.generation_id))  # nosec B608 # fixed SQL identifier; enforced by test_effect_sql_identifier_guard
                count=cursor.fetchone()
                from neuron.effect_protocol_v3 import integer
                if (type(count) not in (tuple,list) or len(count)!=1 or
                        integer(count[0])>=MAX_GENERATION_ATTEMPTS5):
                    raise EffectV3Error('generation reached its bounded closure capacity')
                now=self._current_policy(generation,proposal,self._now())
                admission=sign_receipt(self._signer,purpose=1,subject=proposal.digest,provider=c.provider_id,
                    epoch=c.authority_epoch,policy=c.policy_version,fence=proposal.fencing_token,
                    issued_at=now,expires_at=c.expires_at)
                result=ObjectAttemptV5(row,proposal,admission,1,None)
                result.authenticate_current(self.identity.authority,self._now())
                # Policy is re-read after signing too. A denial/unknown rolls
                # back; the signature never escapes this transaction method.
                self._current_policy(generation,proposal,self._now())
                cursor.execute(f'''INSERT INTO {WORK5}(operation_id,logical_work,initial_proposal_bytes,
                    initial_proposal_digest,postcondition,budget_unit,cost_units)
                    VALUES(%s,%s,%s,%s,%s,%s,%s)''',(  # nosec B608 # fixed SQL identifier; enforced by test_effect_sql_identifier_guard
                    proposal.operation_id,logical_work(proposal),proposal.canonical_bytes(),proposal.digest,
                    proposal.postcondition,c.budget_unit,cost))
                row_bytes=row.canonical_bytes()
                import hashlib
                cursor.execute(f'''INSERT INTO {ATTEMPTS5}(attempt_id,operation_id,attempt_no,logical_work,
                    predecessor_attempt_id,scope_id,generation_id,native_chain_id,native_contract,allocation_id,
                    allocation_index,row_bytes,row_digest,proposal_bytes,proposal_digest,admission_bytes,
                    admission_digest,nonce,budget_unit,cost_units)
                    VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',(  # nosec B608 # fixed SQL identifier; enforced by test_effect_sql_identifier_guard
                    result.attempt_id,proposal.operation_id,1,logical_work(proposal),None,scope_id,generation.generation_id,
                    row.chain_id,row.settlement,row.allocation_id,row.provider_index,row_bytes,hashlib.sha256(row_bytes).digest(),
                    proposal.canonical_bytes(),proposal.digest,admission.canonical_bytes(),admission.digest,c.nonce,c.budget_unit,cost))
                event=AttemptEventV5(result.attempt_id,1,None,'reserved',
                    reserved_payload(result.link_digest,generation.generation_id))
                cursor.execute(EVENT_INSERT,(proposal.operation_id,1,result.attempt_id,1,None,'reserved',
                    event.payload,event.payload_digest,event.digest))
                cursor.execute(f'''UPDATE {HEADS5} SET budget_reserved=budget_reserved+%s
                    WHERE scope_id=%s AND current_generation=%s
                    AND budget_reserved<=budget_limit-budget_spent-%s''',  # nosec B608 # fixed SQL identifier; enforced by test_effect_sql_identifier_guard
                    (cost,scope_id,generation.generation_id,cost))
                if cursor.rowcount!=1:raise EffectV3Error('governed reservation changed before commit')
        # A commit or close ambiguity raises the retained UNKNOWN error instead
        # of returning a credential or retrying. Recover by exact identity only.
        return result
