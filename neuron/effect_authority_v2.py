"""Additive local v2 authority using the EXISTING PostgreSQL transaction owner.

Real PostgreSQL concurrency/restart qualification is REQUIRED and not replaced
by provider SQLite tests. No live route or DBOS schema is activated here.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
import hashlib
import json
import time

from neuron.effect_gate_v2 import require_local, record_json, read_record
from neuron.effect_proposal import (
    EffectProposalV2, AdmissionReceiptV2, FenceUpdateV2, FenceAcknowledgementV2,
    ProviderRecordV2, FencedAbsenceV2, ProtocolError, authenticate, verify_authentication,
    identifier, hash32, integer,
)


def principal_lock_key(principal):
    # This advisory lock is shared with v1 provisioning: retain its UTF-8
    # principal representation, including legacy DID and Unicode identifiers.
    if type(principal) is not str:
        raise ProtocolError("invalid legacy-compatible principal")
    try:
        encoded=principal.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ProtocolError("invalid legacy-compatible principal") from error
    return int.from_bytes(hashlib.sha256(
        b"VAMS:EFFECT-PRINCIPAL-LOCK:v2\0"+encoded).digest()[:8],
        "big",signed=True)


@dataclass(frozen=True)
class AuthorityScopeV2:
    principal_id: str
    principal_root: bytes
    intent_id: bytes
    capability_id: bytes
    target_domain: bytes
    target: str
    implementation_digest: bytes
    runtime_digest: bytes
    policy_root: bytes
    policy_revision: int
    authority_epoch: int
    fencing_token: int
    expires_at: int
    object_prefix: str
    budget_limit: int
    max_action_cost: int

    def validate(self):
        identifier(self.principal_id,"principal")
        identifier(self.target,"target")
        for name in ("principal_root","intent_id","capability_id","target_domain",
                     "implementation_digest","runtime_digest","policy_root"):
            hash32(getattr(self,name),name)
        for name in ("policy_revision","authority_epoch","fencing_token","expires_at",
                     "budget_limit","max_action_cost"):
            integer(getattr(self,name),name)
        if self.max_action_cost>self.budget_limit:
            raise ProtocolError("per-action cost exceeds scope budget")
        key=self.object_prefix
        if type(key) is not str or not key.startswith(self.principal_id+"/"):
            raise ProtocolError("scope prefix is outside principal")
        import re
        if len(key)>512 or not re.fullmatch(r"[A-Za-z0-9._/-]+",key,re.ASCII) or any(
                part in ("",".","..") for part in key.split("/")):
            raise ProtocolError("invalid scope prefix")

    def permits(self,proposal):
        self.validate()
        proposal.validate()
        for name in ("principal_id","principal_root","intent_id","capability_id",
                     "target_domain","target","implementation_digest","runtime_digest",
                     "policy_root","policy_revision","authority_epoch","fencing_token"):
            if getattr(self,name)!=getattr(proposal,name):
                raise ProtocolError("proposal exceeds current authority: "+name)
        if not (proposal.object_key==self.object_prefix or
                proposal.object_key.startswith(self.object_prefix+"/")):
            raise ProtocolError("proposal exceeds resource scope")
        if proposal.cost_units>self.max_action_cost or proposal.expires_at>self.expires_at:
            raise ProtocolError("proposal exceeds cost/expiry scope")


class PostgresEffectAuthorityV2:
    def __init__(self,repository,issuer,provider_id,provider_observation_key,*,clock=time.time):
        require_local()
        # Reuse the repository's reviewed commit/rollback ownership.
        from neuron.effect_canary import PostgresAuthorityRepository
        if type(repository) is not PostgresAuthorityRepository:
            raise ProtocolError("existing PostgreSQL authority repository required")
        identifier(provider_id,"provider")
        if type(provider_observation_key) is not bytes or len(provider_observation_key)<32:
            raise ProtocolError("provider observation verifier key is required")
        self.repository=repository
        self.issuer=issuer
        self.provider_id=provider_id
        self._provider_key=provider_observation_key
        self._clock=clock

    def _now(self):
        now=int(self._clock())
        integer(now,"authority clock")
        return now

    def initialize(self):
        require_local()
        self.repository.initialize()
        with self.repository._connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""CREATE TABLE IF NOT EXISTS vams_effect_v2_authority (
                    principal_id TEXT PRIMARY KEY, scope_json TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('active','draining','revoked')),
                    budget_reserved BIGINT NOT NULL DEFAULT 0 CHECK(budget_reserved>=0),
                    budget_spent BIGINT NOT NULL DEFAULT 0 CHECK(budget_spent>=0),
                    fence_update TEXT, fence_ack TEXT, schema_version INTEGER NOT NULL CHECK(schema_version=2))""")
                cur.execute("""CREATE TABLE IF NOT EXISTS vams_effect_v2_operations (
                    operation_id UUID PRIMARY KEY, principal_id TEXT NOT NULL
                    REFERENCES vams_effect_v2_authority(principal_id),
                    proposal_digest BYTEA NOT NULL, proposal_bytes BYTEA NOT NULL,
                    admission_json TEXT NOT NULL, nonce BYTEA UNIQUE NOT NULL,
                    cost_units BIGINT NOT NULL CHECK(cost_units>=0),
                    status TEXT NOT NULL CHECK(status IN ('reserved','indeterminate','committed','rejected')),
                    record_json TEXT, schema_version INTEGER NOT NULL CHECK(schema_version=2))""")

    def provision(self,scope):
        require_local()
        scope.validate()
        if scope.target!=self.provider_id or self._now()>=scope.expires_at:
            raise ProtocolError("wrong provider or expired scope")
        with self.repository._connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT pg_advisory_xact_lock(%s)",(principal_lock_key(scope.principal_id),))
                cur.execute("SELECT revoked FROM vams_effect_authority WHERE principal_id=%s FOR UPDATE",(scope.principal_id,))
                legacy=cur.fetchone()
                if legacy is not None and legacy[0] is not True:
                    raise ProtocolError("v1 writer must be revoked before v2 provisioning")
                cur.execute("SELECT COUNT(*) FROM vams_effect_operations WHERE action_json->>'principal_id'=%s AND status IN ('pending','indeterminate')",(scope.principal_id,))
                if cur.fetchone()[0]!=0:
                    raise ProtocolError("pending v1 effects require reconciliation")
                cur.execute("INSERT INTO vams_effect_v2_authority(principal_id,scope_json,status,schema_version) VALUES(%s,%s,'active',2) ON CONFLICT(principal_id) DO NOTHING",
                            (scope.principal_id,record_json(scope)))
                if cur.rowcount!=1:
                    raise ProtocolError("v2 authority already exists; no implicit reissue")

    def reserve(self,proposal):
        require_local()
        proposal.validate()
        with self.repository._connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT scope_json,status,budget_reserved,budget_spent FROM vams_effect_v2_authority WHERE principal_id=%s FOR UPDATE",(proposal.principal_id,))
                row=cur.fetchone()
                if row is None:
                    raise ProtocolError("v2 authority is not provisioned")
                cur.execute("SELECT proposal_digest,admission_json,status FROM vams_effect_v2_operations WHERE operation_id=%s",(proposal.operation_id,))
                old=cur.fetchone()
                if old:
                    if bytes(old[0])!=proposal.proposal_digest or old[2]=="rejected":
                        raise ProtocolError("operation is rejected or bound to another proposal")
                    admission=read_record(old[1],AdmissionReceiptV2)
                    self.issuer.verify(admission)
                    return admission
                scope=read_record(row[0],AuthorityScopeV2)
                scope.permits(proposal)
                if row[1]!="active" or self._now()>=proposal.expires_at:
                    raise ProtocolError("authority is stale, revoked or draining")
                if proposal.cost_units>scope.budget_limit-row[2]-row[3]:
                    raise ProtocolError("shared budget exhausted")
                admission=self.issuer.admit(proposal,reservation_id=proposal.operation_id)
                cur.execute("UPDATE vams_effect_v2_authority SET budget_reserved=budget_reserved+%s WHERE principal_id=%s",
                            (proposal.cost_units,proposal.principal_id))
                cur.execute("INSERT INTO vams_effect_v2_operations(operation_id,principal_id,proposal_digest,proposal_bytes,admission_json,nonce,cost_units,status,schema_version) VALUES(%s,%s,%s,%s,%s,%s,%s,'reserved',2)",
                            (proposal.operation_id,proposal.principal_id,proposal.proposal_digest,
                             proposal.canonical_bytes(),record_json(admission),proposal.nonce,proposal.cost_units))
        # The existing context manager committed before any receipt escapes.
        return admission

    def mark_indeterminate(self,proposal):
        require_local()
        with self.repository._connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE vams_effect_v2_operations SET status='indeterminate' WHERE operation_id=%s AND proposal_digest=%s AND status='reserved'",
                            (proposal.operation_id,proposal.proposal_digest))

    def accept_record(self,proposal,admission,record):
        require_local()
        self.issuer.verify(admission)
        if type(record) is not ProviderRecordV2:
            raise ProtocolError("typed provider execution record required")
        verify_authentication(record,self._provider_key)
        if (record.operation_id!=proposal.operation_id or record.proposal_digest!=proposal.proposal_digest or
            record.admission_digest!=admission.receipt_digest or record.content_hash!=proposal.content_hash or
            record.postcondition_digest!=proposal.expected_postcondition or record.state_version!=1 or
            record.provider_id!=self.provider_id or record.committed_at>=proposal.expires_at or
            admission.proposal_digest!=proposal.proposal_digest):
            raise ProtocolError("provider result does not close the authorized effect")
        with self.repository._connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT budget_reserved FROM vams_effect_v2_authority WHERE principal_id=%s FOR UPDATE",(proposal.principal_id,))
                authority=cur.fetchone()
                cur.execute("SELECT proposal_digest,admission_json,cost_units,status,record_json FROM vams_effect_v2_operations WHERE operation_id=%s FOR UPDATE",(proposal.operation_id,))
                row=cur.fetchone()
                if authority is None or row is None or bytes(row[0])!=proposal.proposal_digest:
                    raise ProtocolError("reservation identity missing or altered")
                if read_record(row[1],AdmissionReceiptV2)!=admission or row[2]!=proposal.cost_units:
                    raise ProtocolError("reservation differs from admitted obligation")
                if row[3]=="committed":
                    if read_record(row[4],ProviderRecordV2)!=record:
                        raise ProtocolError("conflicting committed provider record")
                    return record
                if row[3] not in ("reserved","indeterminate") or authority[0]<row[2]:
                    raise ProtocolError("operation is not reconcilable")
                cur.execute("UPDATE vams_effect_v2_authority SET budget_reserved=budget_reserved-%s,budget_spent=budget_spent+%s WHERE principal_id=%s",
                            (row[2],row[2],proposal.principal_id))
                cur.execute("UPDATE vams_effect_v2_operations SET status='committed',record_json=%s WHERE operation_id=%s",
                            (record_json(record),proposal.operation_id))
        return record

    def begin_revocation(self,principal,new_epoch,new_revision,new_fence,valid_until):
        require_local()
        for value in (new_epoch,new_revision,new_fence,valid_until): integer(value,"revocation")
        now=self._now()
        if not now<valid_until<=min(now+300,(1<<63)-1):
            raise ProtocolError("revocation delivery must have a bounded fresh window")
        with self.repository._connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT scope_json,status,fence_update FROM vams_effect_v2_authority WHERE principal_id=%s FOR UPDATE",(principal,))
                row=cur.fetchone()
                if row is None or row[1]!="active":
                    raise ProtocolError("authority is not active; reconcile retained revocation")
                scope=read_record(row[0],AuthorityScopeV2)
                if new_epoch<=scope.authority_epoch or new_revision<scope.policy_revision or new_fence<=scope.fencing_token:
                    raise ProtocolError("revocation must advance authority and fence")
                update=self.issuer._sign(FenceUpdateV2(
                    principal,scope.principal_root,scope.target_domain,scope.target,
                    new_epoch,new_revision,new_fence,valid_until,self.issuer.issuer_id,b"\0"*32))
                cur.execute("UPDATE vams_effect_v2_authority SET status='draining',fence_update=%s WHERE principal_id=%s",
                            (record_json(update),principal))
        return update

    def reconcile_fenced_absence(self,proposal,ack,absence):
        require_local()
        proposal.validate()
        if type(ack) is not FenceAcknowledgementV2 or type(absence) is not FencedAbsenceV2:
            raise ProtocolError("typed fencing and absence evidence required")
        verify_authentication(ack,self._provider_key)
        verify_authentication(absence,self._provider_key)
        if (absence.operation_id!=proposal.operation_id or absence.proposal_digest!=proposal.proposal_digest or
            absence.fence_ack_digest!=ack.receipt_digest or absence.provider_id!=self.provider_id or
            absence.observed_at<ack.observed_at or ack.provider_id!=self.provider_id or
            ack.authority_epoch<=proposal.authority_epoch or ack.fencing_token<=proposal.fencing_token):
            raise ProtocolError("absence does not prove this effect cannot execute")
        with self.repository._connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT status,fence_update,budget_reserved FROM vams_effect_v2_authority WHERE principal_id=%s FOR UPDATE",(proposal.principal_id,))
                authority=cur.fetchone()
                if authority is None or authority[0]!="draining":
                    raise ProtocolError("authority is not draining")
                update=read_record(authority[1],FenceUpdateV2)
                self.issuer.verify(update)
                if ack.update_digest!=update.receipt_digest:
                    raise ProtocolError("absence is bound to a different revocation")
                cur.execute("SELECT proposal_digest,cost_units,status FROM vams_effect_v2_operations WHERE operation_id=%s FOR UPDATE",(proposal.operation_id,))
                row=cur.fetchone()
                if row is None or bytes(row[0])!=proposal.proposal_digest or row[1]!=proposal.cost_units:
                    raise ProtocolError("absence reservation identity mismatch")
                if row[2]=="rejected":
                    return
                if row[2] not in ("reserved","indeterminate") or authority[2]<row[1]:
                    raise ProtocolError("committed or inconsistent operation cannot be released")
                cur.execute("UPDATE vams_effect_v2_authority SET budget_reserved=budget_reserved-%s WHERE principal_id=%s",(row[1],proposal.principal_id))
                cur.execute("UPDATE vams_effect_v2_operations SET status='rejected',record_json=%s WHERE operation_id=%s",(record_json(absence),proposal.operation_id))

    def complete_revocation(self,principal,ack):
        require_local()
        if type(ack) is not FenceAcknowledgementV2:
            raise ProtocolError("typed provider fencing acknowledgement required")
        verify_authentication(ack,self._provider_key)
        with self.repository._connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT status,fence_update FROM vams_effect_v2_authority WHERE principal_id=%s FOR UPDATE",(principal,))
                row=cur.fetchone()
                if row is None or row[0]!="draining":
                    raise ProtocolError("revocation is not draining")
                update=read_record(row[1],FenceUpdateV2)
                self.issuer.verify(update)
                if (ack.update_digest!=update.receipt_digest or ack.provider_id!=self.provider_id or
                    ack.authority_epoch!=update.authority_epoch or ack.policy_revision!=update.policy_revision or
                    ack.fencing_token!=update.fencing_token):
                    raise ProtocolError("acknowledgement differs from retained fence update")
                cur.execute("SELECT COUNT(*) FROM vams_effect_v2_operations WHERE principal_id=%s AND status IN ('reserved','indeterminate')",(principal,))
                if cur.fetchone()[0]!=0:
                    raise ProtocolError("outstanding effects must be reconciled; exposure retained")
                cur.execute("UPDATE vams_effect_v2_authority SET status='revoked',fence_ack=%s WHERE principal_id=%s",
                            (record_json(ack),principal))


def execute_local_v2(authority,provider,proposal,content):
    """One provider invocation; loss of acknowledgement uses lookup, never resend.

    Lookup recomputes the object hash, but the local provider and observer share
    an operator. This result is not independently observed or settlement-ready.
    """
    require_local()
    admission=authority.reserve(proposal)
    try:
        record=provider.commit(proposal,admission,content)
    except Exception:
        authority.mark_indeterminate(proposal)
        record=provider.lookup(proposal.operation_id)
        if record is None:
            raise ProtocolError("effect outcome unknown; reservation retained") from None
    provider.verify_record(record,proposal,admission)
    observed=provider.lookup(proposal.operation_id)
    if observed!=record:
        raise ProtocolError("exact object read-back is missing or conflicting")
    return authority.accept_record(proposal,admission,record)
