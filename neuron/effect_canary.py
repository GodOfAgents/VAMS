"""Local qualification workflow for exact, authorized provider effects.

This is not a deployment adapter. Database authority is PostgreSQL; the
independently operated object provider has its own atomic object/effect ledger.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import uuid
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Callable, Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener
from urllib.parse import urlsplit

from neuron.effect_runtime import LocalEffectRuntimeBoundary

SCHEMA_VERSION = 1
MAX_OBJECT_BYTES = 1_048_576
ACTION_DOMAIN = b"VAMS:EFFECT-ACTION:v1\0"


class EffectError(RuntimeError):
    pass


class EffectStatus(str, Enum):
    PENDING = "pending"
    COMMITTED = "committed"
    REJECTED = "rejected"
    INDETERMINATE = "indeterminate"


@dataclass(frozen=True)
class ResolvedImplementation:
    name: str
    version: str
    digest: str
    schema_version: int = SCHEMA_VERSION


@dataclass(frozen=True)
class ApprovedAction:
    principal_id: str
    task_id: str
    operation_id: str
    target: str
    implementation: ResolvedImplementation
    object_key: str
    content_hash: str
    cost_units: int
    policy_revision: int
    authority_epoch: int
    expires_at: int
    schema_version: int = SCHEMA_VERSION

    def canonical_bytes(self) -> bytes:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":")).encode()

    @property
    def action_digest(self) -> str:
        return hashlib.sha256(ACTION_DOMAIN + self.canonical_bytes()).hexdigest()

    def validate(self) -> None:
        if self.schema_version != SCHEMA_VERSION or self.implementation.schema_version != SCHEMA_VERSION:
            raise EffectError("unsupported action or implementation schema")
        for name in ("principal_id", "task_id", "target", "object_key"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value or len(value) > 256 or value.strip() != value:
                raise EffectError(f"invalid {name}")
        try:
            if str(uuid.UUID(self.operation_id)) != self.operation_id:
                raise ValueError
        except (ValueError, TypeError, AttributeError) as exc:
            raise EffectError("operation_id must be a canonical UUID") from exc
        if not _is_hash(self.implementation.digest) or not _is_hash(self.content_hash):
            raise EffectError("implementation and content digests must be lowercase SHA-256")
        if isinstance(self.cost_units, bool) or not isinstance(self.cost_units, int) or self.cost_units < 0:
            raise EffectError("cost_units must be a nonnegative integer")
        for field in ("policy_revision", "authority_epoch", "expires_at"):
            value = getattr(self, field)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise EffectError(f"{field} must be a nonnegative integer")


def _is_hash(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


@dataclass(frozen=True)
class AttenuatedCapability:
    principal_id: str
    task_id: str
    target: str
    implementation_digest: str
    max_cost_units: int
    policy_revision: int
    authority_epoch: int
    expires_at: int
    object_prefix: str
    schema_version: int = SCHEMA_VERSION


@dataclass(frozen=True)
class ProviderEffectContract:
    provider_id: str
    supports_idempotency: bool
    supports_lookup: bool
    atomic_object_and_ledger: bool
    schema_version: int = SCHEMA_VERSION


@dataclass(frozen=True)
class BudgetReservation:
    operation_id: str
    principal_id: str
    cost_units: int
    status: EffectStatus


@dataclass(frozen=True)
class EffectOutcome:
    operation_id: str
    status: EffectStatus
    receipt: str | None = None


@dataclass(frozen=True)
class ObservationReceipt:
    operation_id: str
    object_hash: str
    provider_record_hash: str
    observed_at: int
    source: str
    schema_version: int = SCHEMA_VERSION


class AuthorityRepository(Protocol):
    def initialize(self) -> None: ...
    def revoke(self, principal_id: str, new_epoch: int, new_policy_revision: int) -> None: ...
    def provision_capability(self, capability: AttenuatedCapability, budget_units: int) -> None: ...
    def reserve(self, action: ApprovedAction, now: int) -> BudgetReservation: ...
    def commit_if_current(self, action: ApprovedAction, effect: Callable[[], str]) -> EffectOutcome: ...
    def mark_indeterminate(self, operation_id: str) -> None: ...
    def record_observation(self, receipt: ObservationReceipt) -> None: ...


class PostgresAuthorityRepository(LocalEffectRuntimeBoundary):
    """Application-owned PostgreSQL tables, separate from DBOS system tables."""

    def __init__(self, dsn: str):
        self._bind_local_effect_runtime()
        if not dsn or not dsn.startswith(("postgres://", "postgresql://")):
            raise EffectError("VAMS_EFFECT_DATABASE_URL must be a PostgreSQL DSN")
        self.dsn = dsn

    def versioned_effects(self, issuer, provider_id, observation_key, *, clock=time.time):
        """Build a local v2 authority sharing this repository's transactions."""
        self._require_local_effect_runtime()
        from neuron.effect_authority_v2 import PostgresEffectAuthorityV2
        return PostgresEffectAuthorityV2(self, issuer, provider_id, observation_key, clock=clock)

    def _connect(self):
        self._require_local_effect_runtime()
        try:
            import psycopg2
        except ImportError as exc:
            raise EffectError("psycopg2 is required for PostgreSQL effect storage") from exc
        return psycopg2.connect(self.dsn)

    from contextlib import contextmanager

    @contextmanager
    def _connection(self):
        self._require_local_effect_runtime()
        conn = self._connect()
        try:
            yield conn
        except BaseException:
            # Keep the operation error primary if cleanup itself also fails.
            try:
                conn.rollback()
            except BaseException:
                pass
            try:
                conn.close()
            except BaseException:
                pass
            raise
        else:
            try:
                conn.commit()
            except BaseException:
                # A failed commit is never a successful repository outcome. A
                # provider effect may already exist, so callers must reconcile
                # it by the same operation ID before retrying.
                try:
                    conn.rollback()
                except BaseException:
                    pass
                try:
                    conn.close()
                except BaseException:
                    pass
                raise
            conn.close()

    def initialize(self) -> None:
        self._require_local_effect_runtime()
        statements = (
            "CREATE TABLE IF NOT EXISTS vams_effect_schema (singleton SMALLINT PRIMARY KEY CHECK(singleton=1), version INTEGER NOT NULL)",
            "CREATE TABLE IF NOT EXISTS vams_effect_authority (principal_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, target TEXT NOT NULL, implementation_digest CHAR(64) NOT NULL, object_prefix TEXT NOT NULL, budget_limit BIGINT NOT NULL CHECK(budget_limit>=0), max_action_cost BIGINT NOT NULL CHECK(max_action_cost>=0), budget_reserved BIGINT NOT NULL DEFAULT 0 CHECK(budget_reserved>=0), budget_spent BIGINT NOT NULL DEFAULT 0 CHECK(budget_spent>=0), policy_revision BIGINT NOT NULL CHECK(policy_revision>=0), authority_epoch BIGINT NOT NULL CHECK(authority_epoch>=0), expires_at BIGINT NOT NULL CHECK(expires_at>=0), revoked BOOLEAN NOT NULL DEFAULT FALSE, schema_version INTEGER NOT NULL CHECK(schema_version=1))",
            "CREATE TABLE IF NOT EXISTS vams_effect_operations (operation_id UUID PRIMARY KEY, action_digest CHAR(64) NOT NULL, action_json JSONB NOT NULL, status TEXT NOT NULL CHECK(status IN ('pending','committed','rejected','indeterminate')), cost_units BIGINT NOT NULL CHECK(cost_units>=0), receipt TEXT, created_at BIGINT NOT NULL, updated_at BIGINT NOT NULL, schema_version INTEGER NOT NULL CHECK(schema_version=1))",
            "CREATE TABLE IF NOT EXISTS vams_effect_observations (operation_id UUID PRIMARY KEY REFERENCES vams_effect_operations(operation_id), object_hash CHAR(64) NOT NULL, provider_record_hash CHAR(64) NOT NULL, observed_at BIGINT NOT NULL, source TEXT NOT NULL, schema_version INTEGER NOT NULL CHECK(schema_version=1))",
            "INSERT INTO vams_effect_schema(singleton,version) VALUES(1,1) ON CONFLICT(singleton) DO NOTHING",
        )
        with self._connection() as conn:
            with conn.cursor() as cur:
                for statement in statements:
                    cur.execute(statement)
                cur.execute("SELECT version FROM vams_effect_schema WHERE singleton=1")
                row = cur.fetchone()
                if row is None or row[0] != SCHEMA_VERSION:
                    raise EffectError("unsupported PostgreSQL effect schema version")

    def provision_capability(self, capability: AttenuatedCapability, budget_units: int) -> None:
        self._require_local_effect_runtime()
        if capability.schema_version != SCHEMA_VERSION or budget_units < 0 or capability.max_cost_units > budget_units:
            raise EffectError("invalid capability or budget")
        if not _is_hash(capability.implementation_digest) or not capability.object_prefix.startswith(capability.principal_id + "/"):
            raise EffectError("capability requires a pinned implementation and principal-scoped object prefix")
        if min(capability.max_cost_units, capability.policy_revision, capability.authority_epoch, capability.expires_at) < 0:
            raise EffectError("capability limits and epochs must be nonnegative")
        with self._connection() as conn:
            with conn.cursor() as cur:
                from neuron.effect_authority_v2 import principal_lock_key
                cur.execute("SELECT pg_advisory_xact_lock(%s)", (principal_lock_key(capability.principal_id),))
                cur.execute("SELECT to_regclass('vams_effect_v2_authority')")
                if cur.fetchone()[0] is not None:
                    cur.execute("SELECT 1 FROM vams_effect_v2_authority WHERE principal_id=%s", (capability.principal_id,))
                    if cur.fetchone() is not None:
                        raise EffectError("principal has v2 authority; v1 writer cannot be provisioned")
                cur.execute(
                    "INSERT INTO vams_effect_authority(principal_id,task_id,target,implementation_digest,object_prefix,budget_limit,max_action_cost,policy_revision,authority_epoch,expires_at,schema_version) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1) ON CONFLICT(principal_id) DO NOTHING",
                    (capability.principal_id, capability.task_id, capability.target, capability.implementation_digest, capability.object_prefix, budget_units, capability.max_cost_units, capability.policy_revision, capability.authority_epoch, capability.expires_at),
                )
                if cur.rowcount != 1:
                    raise EffectError("principal capability already exists; explicit reissue required")

    def reserve(self, action: ApprovedAction, now: int) -> BudgetReservation:
        self._require_local_effect_runtime()
        action.validate()
        data = json.loads(action.canonical_bytes())
        try:
            from psycopg2.extras import Json
        except ImportError as exc:
            raise EffectError("psycopg2 is required for PostgreSQL effect storage") from exc
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT action_digest,status,cost_units FROM vams_effect_operations WHERE operation_id=%s", (action.operation_id,))
                old = cur.fetchone()
                if old:
                    if old[0] != action.action_digest:
                        raise EffectError("operation ID reused with changed action")
                    return BudgetReservation(action.operation_id, action.principal_id, old[2], EffectStatus(old[1]))
                cur.execute(
                    "SELECT task_id,target,implementation_digest,object_prefix,budget_limit,max_action_cost,budget_reserved,budget_spent,policy_revision,authority_epoch,expires_at,revoked FROM vams_effect_authority WHERE principal_id=%s FOR UPDATE",
                    (action.principal_id,),
                )
                row = cur.fetchone()
                if not row:
                    raise EffectError("no authority provisioned")
                task,target,digest,prefix,limit,max_cost,reserved,spent,revision,epoch,expiry,revoked = row
                in_scope = action.object_key == prefix.rstrip("/") or action.object_key.startswith(prefix.rstrip("/") + "/")
                if revoked or task != action.task_id or target != action.target or digest != action.implementation.digest or not in_scope:
                    raise EffectError("action exceeds current capability")
                if revision != action.policy_revision or epoch != action.authority_epoch or now >= min(expiry, action.expires_at):
                    raise EffectError("authority expired or changed")
                if action.cost_units > max_cost or action.cost_units > limit-reserved-spent:
                    raise EffectError("shared budget exhausted or per-action ceiling exceeded")
                cur.execute("UPDATE vams_effect_authority SET budget_reserved=budget_reserved+%s WHERE principal_id=%s", (action.cost_units, action.principal_id))
                cur.execute(
                    "INSERT INTO vams_effect_operations(operation_id,action_digest,action_json,status,cost_units,created_at,updated_at,schema_version) VALUES(%s,%s,%s,'pending',%s,%s,%s,1)",
                    (action.operation_id, action.action_digest, Json(data), action.cost_units, now, now),
                )
        return BudgetReservation(action.operation_id, action.principal_id, action.cost_units, EffectStatus.PENDING)

    def commit_if_current(self, action: ApprovedAction, effect: Callable[[], str]) -> EffectOutcome:
        """Lock authority through provider commit so revocation has a total order."""
        self._require_local_effect_runtime()
        now = int(time.time())
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT task_id,target,implementation_digest,object_prefix,max_action_cost,budget_reserved,policy_revision,authority_epoch,expires_at,revoked FROM vams_effect_authority WHERE principal_id=%s FOR UPDATE",
                    (action.principal_id,),
                )
                authority = cur.fetchone()
                cur.execute("SELECT action_digest,status,cost_units FROM vams_effect_operations WHERE operation_id=%s FOR UPDATE", (action.operation_id,))
                op = cur.fetchone()
                if not authority or not op:
                    raise EffectError("reservation or authority missing")
                task,target,digest,prefix,max_cost,reserved,revision,epoch,expiry,revoked = authority
                if op[0] != action.action_digest:
                    raise EffectError("operation action digest mismatch")
                if op[1] == EffectStatus.COMMITTED.value:
                    return EffectOutcome(action.operation_id, EffectStatus.COMMITTED)
                if op[1] not in (EffectStatus.PENDING.value, EffectStatus.INDETERMINATE.value):
                    raise EffectError("operation is not committable")
                in_scope = action.object_key == prefix.rstrip("/") or action.object_key.startswith(prefix.rstrip("/") + "/")
                if revoked or task != action.task_id or target != action.target or digest != action.implementation.digest or revision != action.policy_revision or epoch != action.authority_epoch or now >= min(expiry, action.expires_at) or not in_scope or action.cost_units > max_cost or op[2] != action.cost_units or op[2] > reserved:
                    raise EffectError("authority revoked, stale, or altered at provider boundary")
                receipt = effect()
                cur.execute("UPDATE vams_effect_authority SET budget_reserved=budget_reserved-%s,budget_spent=budget_spent+%s WHERE principal_id=%s", (op[2], op[2], action.principal_id))
                cur.execute("UPDATE vams_effect_operations SET status='committed',receipt=%s,updated_at=%s WHERE operation_id=%s", (receipt, now, action.operation_id))
                return EffectOutcome(action.operation_id, EffectStatus.COMMITTED, receipt)

    def revoke(self, principal_id: str, new_epoch: int, new_policy_revision: int) -> None:
        self._require_local_effect_runtime()
        if new_epoch < 0 or new_policy_revision < 0:
            raise EffectError("revocation epoch and policy revision must be nonnegative")
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE vams_effect_authority SET revoked=TRUE,authority_epoch=%s,policy_revision=%s WHERE principal_id=%s AND authority_epoch<%s AND policy_revision<=%s",
                    (new_epoch,new_policy_revision,principal_id,new_epoch,new_policy_revision),
                )
                if cur.rowcount != 1:
                    raise EffectError("revocation must advance an existing authority epoch")

    def mark_indeterminate(self, operation_id: str) -> None:
        self._require_local_effect_runtime()
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE vams_effect_operations SET status='indeterminate',updated_at=%s WHERE operation_id=%s AND status='pending'", (int(time.time()), operation_id))

    def record_observation(self, receipt: ObservationReceipt) -> None:
        self._require_local_effect_runtime()
        if receipt.schema_version != SCHEMA_VERSION or not _is_hash(receipt.object_hash) or not _is_hash(receipt.provider_record_hash):
            raise EffectError("invalid observation receipt")
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO vams_effect_observations(operation_id,object_hash,provider_record_hash,observed_at,source,schema_version) VALUES(%s,%s,%s,%s,%s,1) ON CONFLICT(operation_id) DO UPDATE SET object_hash=EXCLUDED.object_hash,provider_record_hash=EXCLUDED.provider_record_hash,observed_at=EXCLUDED.observed_at,source=EXCLUDED.source WHERE vams_effect_observations.object_hash=EXCLUDED.object_hash AND vams_effect_observations.provider_record_hash=EXCLUDED.provider_record_hash",
                    (receipt.operation_id, receipt.object_hash, receipt.provider_record_hash, receipt.observed_at, receipt.source),
                )
                if cur.rowcount != 1:
                    raise EffectError("conflicting provider observation")


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class HttpObjectProvider(LocalEffectRuntimeBoundary):
    def __init__(self, base_url: str, writer_key: bytes, observer_key: bytes, timeout_seconds: float = 3.0):
        self._bind_local_effect_runtime()
        try:
            parsed=urlsplit(base_url)
            port=parsed.port
        except ValueError as exc:
            raise EffectError("qualification provider URL is malformed") from exc
        if parsed.scheme!="http" or parsed.hostname!="127.0.0.1" or port is None or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
            raise EffectError("qualification provider must be a plain HTTP 127.0.0.1 URL with an explicit port")
        if len(writer_key) < 32 or len(observer_key) < 32 or hmac.compare_digest(writer_key, observer_key):
            raise EffectError("distinct writer and observer keys of at least 32 bytes are required")
        self.base_url=base_url.rstrip("/")
        self.writer_key=writer_key
        self.observer_key=observer_key
        self.timeout_seconds=timeout_seconds
        self.contract=ProviderEffectContract("local-object-provider-v1", True, True, True)
        self._opener=build_opener(_NoRedirectHandler())

    def _request(self, method: str, path: str, payload: Mapping[str,Any], *, observer: bool = False) -> dict[str,Any] | None:
        self._require_local_effect_runtime()
        body=json.dumps(payload,sort_keys=True,separators=(",",":")).encode()
        timestamp=str(int(time.time())); nonce=uuid.uuid4().hex
        message=b"\n".join((method.encode(),path.encode(),timestamp.encode(),nonce.encode(),hashlib.sha256(body).hexdigest().encode()))
        key=self.observer_key if observer else self.writer_key
        signature=hmac.new(key,message,hashlib.sha256).hexdigest()
        req=Request(self.base_url+path,data=body,method=method,headers={"Content-Type":"application/json","X-VAMS-Time":timestamp,"X-VAMS-Nonce":nonce,"X-VAMS-Signature":signature})
        try:
            with self._opener.open(req,timeout=self.timeout_seconds) as response:
                raw=response.read(MAX_OBJECT_BYTES+8192)
                return json.loads(raw)
        except HTTPError as exc:
            code=exc.code
            exc.close()
            raise EffectError(f"provider rejected request ({code})") from exc
        except (URLError,TimeoutError,ValueError) as exc:
            raise EffectError(f"provider outcome unavailable ({type(exc).__name__})") from exc

    def put(self, action: ApprovedAction, content: bytes) -> str:
        self._require_local_effect_runtime()
        if hashlib.sha256(content).hexdigest()!=action.content_hash:
            raise EffectError("content does not match approved hash")
        result=self._request("PUT","/v1/objects",{
            "operation_id":action.operation_id,"principal_id":action.principal_id,"task_id":action.task_id,
            "target":action.target,"implementation_digest":action.implementation.digest,"object_key":action.object_key,
            "content_hash":action.content_hash,"action_digest":action.action_digest,
            "authority_epoch":action.authority_epoch,"policy_revision":action.policy_revision,
            "expires_at":action.expires_at,"content_hex":content.hex(),
        })
        if result is None or not isinstance(result.get("receipt"),str):
            raise EffectError("provider returned malformed receipt")
        return result["receipt"]

    def lookup(self, operation_id: str) -> dict[str,Any] | None:
        self._require_local_effect_runtime()
        return self._request("POST","/v1/lookup",{"operation_id":operation_id})

    def observe(self, operation_id: str) -> dict[str,Any] | None:
        self._require_local_effect_runtime()
        return self._request("POST","/v1/observe",{"operation_id":operation_id},observer=True)


class EffectCoordinator:
    def __init__(self, repository: AuthorityRepository, provider: HttpObjectProvider):
        self.repository=repository
        self.provider=provider
        contract=provider.contract
        if not (contract.supports_idempotency and contract.supports_lookup and contract.atomic_object_and_ledger):
            raise EffectError("provider does not satisfy the effect contract")

    @classmethod
    def for_v2(cls, authority, provider):
        """Explicit local v2 composition; no existing route is upgraded."""
        from neuron.effect_authority_v2 import PostgresEffectAuthorityV2
        from neuron.effect_gate_v2 import ObjectEffectBoundaryV2, require_local
        require_local()
        if type(authority) is not PostgresEffectAuthorityV2 or type(provider) is not ObjectEffectBoundaryV2:
            raise EffectError("bound local v2 authority and provider required")
        instance = cls(authority.repository, provider)
        instance._authority_v2 = authority
        return instance

    def execute_v2(self, proposal, content):
        from neuron.effect_authority_v2 import execute_local_v2
        authority = getattr(self, "_authority_v2", None)
        if authority is None or authority.repository is not self.repository:
            raise EffectError("v2 authority was not explicitly composed")
        return execute_local_v2(authority, self.provider, proposal, content)

    def execute(self, action: ApprovedAction, content: bytes) -> EffectOutcome:
        if getattr(self, "_authority_v2", None) is not None:
            raise EffectError("v1 execution cannot use a v2 authority")
        if os.environ.get("VAMS_ENV") not in {"local","test","demo"}:
            raise EffectError("effect canary requires explicit local/test/demo mode")
        action.validate()
        if len(content)>MAX_OBJECT_BYTES or hashlib.sha256(content).hexdigest()!=action.content_hash:
            raise EffectError("content size or digest differs from approval")
        # A successful authenticated request for an absent operation proves the
        # observation route is reachable before new authority is consumed.
        self.provider.observe("00000000-0000-0000-0000-000000000000")
        self.repository.reserve(action,int(time.time()))
        try:
            outcome=self.repository.commit_if_current(action,lambda:self.provider.put(action,content))
        except Exception as exc:
            self.repository.mark_indeterminate(action.operation_id)
            record=self.provider.lookup(action.operation_id)
            if record is None:
                raise EffectError("effect outcome unknown; reservation retained") from exc
            if record.get("action_digest")!=action.action_digest or record.get("content_hash")!=action.content_hash:
                raise EffectError("provider ledger conflicts with approved action") from exc
            outcome=self.repository.commit_if_current(action,lambda:self.provider.put(action,content))
        observed=self.provider.observe(action.operation_id)
        if observed is None or observed.get("object_hash")!=action.content_hash:
            raise EffectError("independent object read-back missing or does not match")
        ledger=self.provider.lookup(action.operation_id)
        if ledger is None or ledger.get("action_digest")!=action.action_digest:
            raise EffectError("independent provider ledger read-back missing or mismatched")
        record_hash=hashlib.sha256(json.dumps(ledger,sort_keys=True,separators=(",",":")).encode()).hexdigest()
        receipt=ObservationReceipt(action.operation_id,observed["object_hash"],record_hash,int(time.time()),"separate-provider-observer-credential")
        self.repository.record_observation(receipt)
        return outcome
