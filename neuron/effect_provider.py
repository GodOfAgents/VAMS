"""Independent loopback provider for the controlled object-write canary.

The SQLite object table and idempotency ledger commit in one transaction. This
small service is a real local provider, not evidence of PostgreSQL qualification
or a staging-capable storage adapter."""
from __future__ import annotations
import hashlib, hmac, json, os, re, sqlite3, time, uuid
from pathlib import Path
from contextlib import contextmanager
from typing import Any
from wsgiref.simple_server import WSGIServer, WSGIRequestHandler, make_server

from neuron.effect_runtime import LocalEffectRuntimeBoundary, local_effect_policy
from neuron.runtime_safety import LiveModeSafetyError

MAX_BODY=2_200_000
MAX_SKEW=30
_HASH=re.compile(r"^[0-9a-f]{64}$")

class ProviderError(RuntimeError): pass

def _local_provider_policy():
    return local_effect_policy()


class ObjectProvider(LocalEffectRuntimeBoundary):
    def __init__(self, database: str, writer_key: bytes, observer_key: bytes, target_id: str, implementation_digest: str):
        # Bind before key validation, filesystem permissions or database access.
        self._bind_local_effect_runtime()
        if len(writer_key)<32 or len(observer_key)<32 or hmac.compare_digest(writer_key,observer_key): raise ProviderError("writer and observer keys must be distinct 32-byte secrets")
        if not target_id or not _HASH.fullmatch(implementation_digest): raise ProviderError("provider target and implementation pin are required")
        self.database=database; self.writer_key=writer_key; self.observer_key=observer_key; self.target_id=target_id; self.implementation_digest=implementation_digest
        db_path=Path(database)
        db_path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        if db_path.parent.stat().st_mode & 0o077:
            raise ProviderError("provider database directory must be private to its owner")
        previous_umask=os.umask(0o077)
        try:
            self._initialize_database()
        finally:
            os.umask(previous_umask)
        try: os.chmod(database,0o600)
        except OSError as exc: raise ProviderError("provider database permissions could not be restricted") from exc

    def _require_local_provider(self):
        self._require_local_effect_runtime()

    def _initialize_database(self):
        self._require_local_provider()
        with self._connection() as db:
            db.executescript("""CREATE TABLE IF NOT EXISTS provider_objects(principal_id TEXT NOT NULL, object_key TEXT NOT NULL, content BLOB NOT NULL, content_hash TEXT NOT NULL, operation_id TEXT NOT NULL UNIQUE, action_digest TEXT NOT NULL, created_at INTEGER NOT NULL, PRIMARY KEY(principal_id,object_key)); CREATE TABLE IF NOT EXISTS provider_nonces(key_id TEXT NOT NULL, nonce TEXT NOT NULL, used_at INTEGER NOT NULL, PRIMARY KEY(key_id,nonce)); CREATE TABLE IF NOT EXISTS provider_schema(singleton INTEGER PRIMARY KEY CHECK(singleton=1),version INTEGER NOT NULL); INSERT INTO provider_schema VALUES(1,1) ON CONFLICT(singleton) DO NOTHING;""")
            row=db.execute("SELECT version FROM provider_schema WHERE singleton=1").fetchone()
            if not row or row[0]!=1: raise ProviderError("unsupported provider database schema")

    def _connect(self):
        self._require_local_provider()
        db=sqlite3.connect(self.database,timeout=5,isolation_level=None)
        db.execute("PRAGMA foreign_keys=ON"); db.execute("PRAGMA busy_timeout=5000")
        return db

    @contextmanager
    def _connection(self):
        self._require_local_provider()
        db=self._connect()
        try:
            yield db
        finally:
            db.close()

    @staticmethod
    def _message(method: str,path: str,timestamp: str,nonce: str,body: bytes) -> bytes:
        return bytes([10]).join((method.encode(),path.encode(),timestamp.encode(),nonce.encode(),hashlib.sha256(body).hexdigest().encode()))

    def _authenticate(self, environ: dict[str,Any], method: str,path: str,body: bytes, *, observer: bool) -> tuple[str,str]:
        self._require_local_provider()
        timestamp=environ.get("HTTP_X_VAMS_TIME",""); nonce=environ.get("HTTP_X_VAMS_NONCE",""); signature=environ.get("HTTP_X_VAMS_SIGNATURE","")
        try: issued=int(timestamp)
        except ValueError as exc: raise ProviderError("invalid request timestamp") from exc
        if abs(int(time.time())-issued)>MAX_SKEW: raise ProviderError("request timestamp outside replay window")
        if not re.fullmatch(r"[0-9a-f]{32}",nonce): raise ProviderError("invalid request nonce")
        key_id="observer" if observer else "writer"; key=self.observer_key if observer else self.writer_key
        expected=hmac.new(key,self._message(method,path,timestamp,nonce,body),hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected,signature): raise ProviderError("request authentication failed")
        return key_id,nonce

    def put(self, payload: dict[str,Any]) -> dict[str,Any]:
        self._require_local_provider()
        required={"operation_id","principal_id","task_id","target","implementation_digest","object_key","content_hash","action_digest","authority_epoch","policy_revision","expires_at","content_hex"}
        if set(payload)!=required: raise ProviderError("unexpected provider request fields")
        try: operation=str(uuid.UUID(payload["operation_id"]))
        except (ValueError,TypeError) as exc: raise ProviderError("invalid operation identifier") from exc
        principal=payload["principal_id"]; key=payload["object_key"]; raw=payload["content_hex"]
        if not isinstance(principal,str) or not re.fullmatch(r"[A-Za-z0-9._-]{1,128}",principal): raise ProviderError("invalid principal scope")
        if not isinstance(key,str) or len(key)>512 or not key.startswith(principal+"/") or any(part in ("",".","..") for part in key.split("/")) or "\\" in key: raise ProviderError("object key escapes principal scope")
        if payload["target"]!=self.target_id or payload["implementation_digest"]!=self.implementation_digest: raise ProviderError("provider target or pinned implementation mismatch")
        if not _HASH.fullmatch(payload["content_hash"]) or not _HASH.fullmatch(payload["action_digest"]): raise ProviderError("invalid action or content digest")
        try: content=bytes.fromhex(raw)
        except (ValueError,TypeError) as exc: raise ProviderError("invalid content encoding") from exc
        if len(content)>1_048_576 or hashlib.sha256(content).hexdigest()!=payload["content_hash"]: raise ProviderError("content length or digest mismatch")
        db=self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            old=db.execute("SELECT action_digest,content_hash FROM provider_objects WHERE operation_id=?",(operation,)).fetchone()
            if old:
                if old!=(payload["action_digest"],payload["content_hash"]): raise ProviderError("operation ID reused with changed action")
                db.commit(); return self._receipt(operation,payload["action_digest"],payload["content_hash"])
            # This check occurs inside the provider's write transaction, at the
            # actual effect boundary rather than only before network dispatch.
            expiry=payload["expires_at"]
            if isinstance(expiry,bool) or not isinstance(expiry,int) or int(time.time())>=expiry:
                raise ProviderError("authority expired at provider commit boundary")
            if any(isinstance(payload[k],bool) or not isinstance(payload[k],int) or payload[k]<0 for k in ("authority_epoch","policy_revision")):
                raise ProviderError("invalid authority epoch or policy revision")
            conflict=db.execute("SELECT operation_id FROM provider_objects WHERE principal_id=? AND object_key=?",(principal,key)).fetchone()
            if conflict: raise ProviderError("immutable object key already exists")
            db.execute("INSERT INTO provider_objects VALUES(?,?,?,?,?,?,?)",(principal,key,content,payload["content_hash"],operation,payload["action_digest"],int(time.time())))
            db.commit()
            return self._receipt(operation,payload["action_digest"],payload["content_hash"])
        except Exception:
            db.rollback(); raise
        finally: db.close()

    @staticmethod
    def _receipt(operation: str,action_digest: str,content_hash: str) -> dict[str,str]:
        data={"operation_id":operation,"action_digest":action_digest,"content_hash":content_hash}
        data["receipt"]=hashlib.sha256(b"VAMS:PROVIDER-RECEIPT:v1\0"+json.dumps(data,sort_keys=True,separators=(",",":")).encode()).hexdigest()
        return data

    def lookup(self, operation_id: str) -> dict[str,Any] | None:
        self._require_local_provider()
        try: operation=str(uuid.UUID(operation_id))
        except (ValueError,TypeError): return None
        with self._connection() as db:
            row=db.execute("SELECT action_digest,content_hash,created_at FROM provider_objects WHERE operation_id=?",(operation,)).fetchone()
        if row is None:return None
        data=self._receipt(operation,row[0],row[1]); data["created_at"]=row[2]; return data

    def observe(self, operation_id: str) -> dict[str,Any] | None:
        self._require_local_provider()
        try: operation=str(uuid.UUID(operation_id))
        except (ValueError,TypeError): return None
        with self._connection() as db:
            row=db.execute("SELECT principal_id,object_key,content,content_hash,action_digest,created_at FROM provider_objects WHERE operation_id=?",(operation,)).fetchone()
        if row is None:return None
        content=row[2]
        return {"operation_id":operation,"principal_id":row[0],"object_key":row[1],"object_hash":hashlib.sha256(content).hexdigest(),"content_hash":row[3],"action_digest":row[4],"created_at":row[5]}

    def app(self,environ,start_response):
        try:
            self._require_local_provider()
            path=environ.get("PATH_INFO",""); method=environ.get("REQUEST_METHOD","GET")
            try:length=int(environ.get("CONTENT_LENGTH") or 0)
            except ValueError: raise ProviderError("invalid body length")
            if not 0<=length<=MAX_BODY: raise ProviderError("request body exceeds limit")
            body=environ["wsgi.input"].read(length)
            observer=path=="/v1/observe"
            if (method,path) not in (("PUT","/v1/objects"),("POST","/v1/lookup"),("POST","/v1/observe")): raise ProviderError("route not found")
            key_id,nonce=self._authenticate(environ,method,path,body,observer=observer)
            payload=json.loads(body or b"{}")
            if not isinstance(payload,dict): raise ProviderError("JSON object required")
            with self._connection() as db:
                db.execute("BEGIN IMMEDIATE")
                db.execute("DELETE FROM provider_nonces WHERE used_at<?",(int(time.time())-MAX_SKEW,))
                try: db.execute("INSERT INTO provider_nonces VALUES(?,?,?)",(key_id,nonce,int(time.time())))
                except sqlite3.IntegrityError as exc: raise ProviderError("request replay rejected") from exc
                db.commit()
            if path=="/v1/objects":result=self.put(payload); status=200
            elif path=="/v1/lookup":result=self.lookup(payload.get("operation_id")); status=200
            else: result=self.observe(payload.get("operation_id")); status=200
            response=json.dumps(result,separators=(",",":")).encode(); start_response(f"{status} OK",[("Content-Type","application/json"),("Content-Length",str(len(response))),("Cache-Control","no-store")]); return [response]
        except LiveModeSafetyError:
            response=b'{"error":"local provider unavailable in current runtime"}'
            start_response("403 Error",[("Content-Type","application/json"),("Content-Length",str(len(response))),("Cache-Control","no-store")])
            return [response]
        except (ProviderError,sqlite3.Error,json.JSONDecodeError) as exc:
            code=409 if "already" in str(exc) or "reuse" in str(exc) or "replay" in str(exc) else 400
            response=json.dumps({"error":str(exc)[:200]},separators=(",",":")).encode(); start_response(f"{code} Error",[("Content-Type","application/json"),("Content-Length",str(len(response))),("Cache-Control","no-store")]); return [response]
        except Exception:
            response=b"{\"error\":\"provider internal error\"}"; start_response("500 Error",[("Content-Type","application/json"),("Content-Length",str(len(response))),("Cache-Control","no-store")]); return [response]

class QuietHandler(WSGIRequestHandler):
    def log_message(self,*args): pass

def from_environment() -> ObjectProvider:
    _local_provider_policy()
    def key(name):
        raw=os.environ.get(name,"")
        try:value=bytes.fromhex(raw)
        except ValueError as exc: raise ProviderError(f"{name} must be hex") from exc
        if len(value)<32: raise ProviderError(f"{name} must contain at least 32 bytes")
        return value
    return ObjectProvider(os.environ["VAMS_EFFECT_PROVIDER_DB"],key("VAMS_EFFECT_WRITER_KEY"),key("VAMS_EFFECT_OBSERVER_KEY"),os.environ["VAMS_EFFECT_TARGET_ID"],os.environ["VAMS_EFFECT_IMPLEMENTATION_DIGEST"])

def main():
    _local_provider_policy()
    os.umask(0o077)
    service=from_environment()
    service._require_local_provider()
    server=make_server("127.0.0.1",int(os.environ.get("VAMS_EFFECT_PROVIDER_PORT","8765")),service.app,handler_class=QuietHandler)
    server.serve_forever()
if __name__=="__main__":main()
