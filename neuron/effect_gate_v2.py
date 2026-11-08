"""Atomic object-effect boundary for LOCAL v2 qualification only.

This SQLite provider does not establish independent operator observation, live
DA, real PostgreSQL authority, host containment, or testnet eligibility. The
authority signer and observer key are trusted dependencies outside the agent.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, replace
import hashlib
import json
import os
import sqlite3
import time

from neuron.effect_proposal import (
    EffectProposalV2, AdmissionReceiptV2, AuthoritySignerV2, FenceUpdateV2,
    FenceAcknowledgementV2, ProviderRecordV2, FencedAbsenceV2, ProtocolError, MAX_CONTENT_BYTES,
    authenticate, verify_authentication, hash32, integer, identifier, operation_id,
)


def require_local():
    if os.environ.get("VAMS_ENV") not in {"local", "test", "demo"}:
        raise ProtocolError("v2 effect qualification requires explicit local/test/demo mode")


def record_json(value):
    return json.dumps({key: item.hex() if type(item) is bytes else item
                       for key,item in asdict(value).items()},
                      sort_keys=True,separators=(",",":"))


def read_record(raw, cls):
    from dataclasses import fields
    data=json.loads(raw)
    if type(data) is not dict or set(data)!={f.name for f in fields(cls)}:
        raise ProtocolError("malformed persisted authenticated record")
    for field in fields(cls):
        # These are declared as bytes, with postponed annotations.
        if field.type in (bytes,"bytes"):
            try:
                data[field.name]=bytes.fromhex(data[field.name])
            except (ValueError,TypeError) as error:
                raise ProtocolError("malformed persisted commitment") from error
    return cls(**data)


class ObjectEffectBoundaryV2:
    """Local provider atomically joins admission, fencing and exact object write."""
    def __init__(self,database,provider_id,target_domain,implementation_digest,
                 issuer: AuthoritySignerV2,observer_key,*,clock=time.time):
        require_local()
        identifier(provider_id,"provider")
        hash32(target_domain,"domain")
        hash32(implementation_digest,"implementation")
        if type(observer_key) is not bytes or len(observer_key)<32:
            raise ProtocolError("invalid local observation key")
        if not isinstance(issuer,AuthoritySignerV2):
            raise ProtocolError("a trusted authority verifier is required")
        if not issuer.verifier_key_is_distinct(observer_key):
            raise ProtocolError("authority and provider observation keys must differ")
        self.database=database
        self.provider_id=provider_id
        self.target_domain=target_domain
        self.implementation_digest=implementation_digest
        self._issuer=issuer
        self._observer_key=observer_key
        self._clock=clock
        with self._transaction() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS vams_effect_v2_provider_meta
                (singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                 provider TEXT NOT NULL, domain BLOB NOT NULL,
                 implementation BLOB NOT NULL, issuer TEXT NOT NULL)""")
            old=db.execute("SELECT provider,domain,implementation,issuer FROM vams_effect_v2_provider_meta WHERE singleton=1").fetchone()
            expected=(provider_id,target_domain,implementation_digest,issuer.issuer_id)
            if old is None:
                db.execute("INSERT INTO vams_effect_v2_provider_meta VALUES(1,?,?,?,?)",expected)
            elif old!=expected:
                raise ProtocolError("provider database belongs to another bound implementation")
            db.execute("""CREATE TABLE IF NOT EXISTS vams_effect_v2_fences
                (principal TEXT PRIMARY KEY, root BLOB NOT NULL, epoch INTEGER NOT NULL,
                 revision INTEGER NOT NULL, fence INTEGER NOT NULL,
                 update_digest BLOB NOT NULL, acknowledgement TEXT NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS vams_effect_v2_objects
                (operation_id TEXT PRIMARY KEY, principal TEXT NOT NULL,
                 object_key TEXT NOT NULL, proposal_digest BLOB NOT NULL,
                 admission_digest BLOB NOT NULL, content BLOB NOT NULL,
                 record TEXT NOT NULL, UNIQUE(principal,object_key))""")
            db.execute("""CREATE TABLE IF NOT EXISTS vams_effect_v2_consumed_admissions
                (admission_digest BLOB PRIMARY KEY, operation_id TEXT UNIQUE NOT NULL,
                 nonce BLOB UNIQUE NOT NULL)""")

    @contextmanager
    def _transaction(self):
        require_local()
        db=sqlite3.connect(self.database,timeout=2,isolation_level=None)
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def _time(self):
        now=int(self._clock())
        integer(now,"provider clock")
        return now

    @property
    def contract(self):
        from neuron.effect_canary import ProviderEffectContract
        return ProviderEffectContract(self.provider_id,True,True,True)

    def _sign(self,value):
        return replace(value,authentication=authenticate(value,self._observer_key))

    def advance_fence(self,update: FenceUpdateV2):
        if type(update) is not FenceUpdateV2:
            raise ProtocolError("typed fence update required")
        self._issuer.verify(update)
        if update.target!=self.provider_id or update.target_domain!=self.target_domain:
            raise ProtocolError("fence targets another provider/domain")
        identifier(update.principal_id,"principal")
        hash32(update.principal_root,"root")
        for name in ("authority_epoch","policy_revision","fencing_token","expires_at"):
            integer(getattr(update,name),name)
        with self._transaction() as db:
            old=db.execute("SELECT root,epoch,revision,fence,update_digest,acknowledgement FROM vams_effect_v2_fences WHERE principal=?",(update.principal_id,)).fetchone()
            if old and old[4]==update.receipt_digest:
                ack=read_record(old[5],FenceAcknowledgementV2)
                self.verify_fence_ack(ack,update)
                return ack  # Historical idempotence remains readable after expiry.
            now=self._time()
            if now>=update.expires_at:
                raise ProtocolError("expired fencing authorization")
            if old and (old[0]!=update.principal_root or
                        update.authority_epoch<=old[1] or
                        update.policy_revision<old[2] or update.fencing_token<=old[3]):
                raise ProtocolError("authority/fence must advance monotonically")
            ack=self._sign(FenceAcknowledgementV2(
                update.receipt_digest,self.provider_id,update.authority_epoch,
                update.policy_revision,update.fencing_token,now,b"\0"*32))
            db.execute("INSERT OR REPLACE INTO vams_effect_v2_fences VALUES(?,?,?,?,?,?,?)",
                       (update.principal_id,update.principal_root,update.authority_epoch,
                        update.policy_revision,update.fencing_token,
                        update.receipt_digest,record_json(ack)))
            return ack

    def verify_fence_ack(self,ack,update):
        if type(ack) is not FenceAcknowledgementV2:
            raise ProtocolError("typed fencing acknowledgement required")
        verify_authentication(ack,self._observer_key)
        if (ack.update_digest!=update.receipt_digest or ack.provider_id!=self.provider_id or
            ack.authority_epoch!=update.authority_epoch or
            ack.policy_revision!=update.policy_revision or ack.fencing_token!=update.fencing_token):
            raise ProtocolError("fence acknowledgement concerns a different update")

    def _validate_admission(self,proposal,admission):
        if type(proposal) is not EffectProposalV2 or type(admission) is not AdmissionReceiptV2:
            raise ProtocolError("typed v2 proposal/admission required")
        proposal.validate()
        self._issuer.verify(admission)
        if (admission.proposal_digest!=proposal.proposal_digest or
            admission.reservation_id!=proposal.operation_id or
            admission.authority_epoch!=proposal.authority_epoch or
            admission.policy_revision!=proposal.policy_revision or
            admission.fencing_token!=proposal.fencing_token or
            admission.cost_units!=proposal.cost_units or admission.expires_at!=proposal.expires_at):
            raise ProtocolError("admission differs from exact effect proposal")
        if (proposal.target!=self.provider_id or proposal.target_domain!=self.target_domain or
            proposal.implementation_digest!=self.implementation_digest):
            raise ProtocolError("effect targets another provider or implementation")

    def commit(self,proposal,admission,content):
        self._validate_admission(proposal,admission)
        if (type(content) is not bytes or len(content)>MAX_CONTENT_BYTES or
            hashlib.sha256(content).digest()!=proposal.content_hash):
            raise ProtocolError("content differs from admitted effect")
        with self._transaction() as db:
            old=db.execute("SELECT proposal_digest,admission_digest,record FROM vams_effect_v2_objects WHERE operation_id=?",(proposal.operation_id,)).fetchone()
            if old:
                if old[:2]!=(proposal.proposal_digest,admission.receipt_digest):
                    raise ProtocolError("operation identity cannot be rebound")
                record=read_record(old[2],ProviderRecordV2)
                self.verify_record(record,proposal,admission)
                return record  # Historical read only, never a new effect.
            now=self._time()
            if now>=min(proposal.expires_at,admission.expires_at):
                raise ProtocolError("authority expired at atomic commit")
            fence=db.execute("SELECT root,epoch,revision,fence FROM vams_effect_v2_fences WHERE principal=?",(proposal.principal_id,)).fetchone()
            if fence!=(proposal.principal_root,proposal.authority_epoch,
                       proposal.policy_revision,proposal.fencing_token):
                raise ProtocolError("stale or missing provider-enforced fence")
            if db.execute("SELECT 1 FROM vams_effect_v2_objects WHERE principal=? AND object_key=?",
                          (proposal.principal_id,proposal.object_key)).fetchone():
                raise ProtocolError("immutable object already exists")
            record=self._sign(ProviderRecordV2(
                proposal.operation_id,proposal.proposal_digest,admission.receipt_digest,
                proposal.content_hash,proposal.expected_postcondition,1,now,
                self.provider_id,b"\0"*32))
            try:
                db.execute("INSERT INTO vams_effect_v2_consumed_admissions VALUES(?,?,?)",
                           (admission.receipt_digest,proposal.operation_id,proposal.nonce))
                db.execute("INSERT INTO vams_effect_v2_objects VALUES(?,?,?,?,?,?,?)",
                           (proposal.operation_id,proposal.principal_id,proposal.object_key,
                            proposal.proposal_digest,admission.receipt_digest,content,record_json(record)))
            except sqlite3.IntegrityError as error:
                raise ProtocolError("operation, admission or nonce already consumed") from error
            return record

    def verify_record(self,record,proposal,admission=None):
        require_local()
        if type(record) is not ProviderRecordV2:
            raise ProtocolError("typed provider record required")
        verify_authentication(record,self._observer_key)
        if (record.operation_id!=proposal.operation_id or
            record.proposal_digest!=proposal.proposal_digest or
            record.content_hash!=proposal.content_hash or
            record.postcondition_digest!=proposal.expected_postcondition or
            record.provider_id!=self.provider_id or record.state_version!=1 or
            (admission is not None and record.admission_digest!=admission.receipt_digest)):
            raise ProtocolError("provider record differs from expected effect")

    def lookup(self,operation):
        operation_id(operation)
        with self._transaction() as db:
            row=db.execute("SELECT record,content FROM vams_effect_v2_objects WHERE operation_id=?",(operation,)).fetchone()
            if row is None:
                return None
            record=read_record(row[0],ProviderRecordV2)
            verify_authentication(record,self._observer_key)
            if record.provider_id!=self.provider_id or hashlib.sha256(row[1]).digest()!=record.content_hash:
                raise ProtocolError("stored object differs from authenticated execution record")
            return record

    def effect_count(self):
        with self._transaction() as db:
            return db.execute("SELECT COUNT(*) FROM vams_effect_v2_objects").fetchone()[0]

    def observe_fenced_absence(self,proposal,ack,query_nonce):
        proposal.validate()
        hash32(query_nonce,"query nonce")
        if type(ack) is not FenceAcknowledgementV2:
            raise ProtocolError("typed fencing acknowledgement required")
        verify_authentication(ack,self._observer_key)
        if proposal.target!=self.provider_id or proposal.target_domain!=self.target_domain:
            raise ProtocolError("absence query targets another provider/domain")
        with self._transaction() as db:
            fence=db.execute("SELECT root,epoch,fence,acknowledgement FROM vams_effect_v2_fences WHERE principal=?",(proposal.principal_id,)).fetchone()
            if (fence is None or fence[0]!=proposal.principal_root or
                fence[1]<=proposal.authority_epoch or fence[2]<=proposal.fencing_token or
                read_record(fence[3],FenceAcknowledgementV2)!=ack):
                raise ProtocolError("absence is not protected by the current newer fence")
            if db.execute("SELECT 1 FROM vams_effect_v2_objects WHERE operation_id=?",(proposal.operation_id,)).fetchone():
                raise ProtocolError("operation exists; reconcile its execution record")
            return self._sign(FencedAbsenceV2(proposal.operation_id,proposal.proposal_digest,
                ack.receipt_digest,query_nonce,self.provider_id,self._time(),b"\0"*32))
