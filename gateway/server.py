"""
VAMS Gateway Server v1.0.0-icn
==============================
FastAPI server for neuron heartbeats, resource composition,
performance auditing, and economics.

Endpoints:
  - /heartbeat               — Neuron heartbeat submission
  - /nodes                   — List connected nodes
  - /compose/*               — Resource Composition Engine (Phase 3)
  - /services/*              — Service Block Registry (Phase 3)
  - /da/*                    — DA Performance Audit (Phase 0)
  - /economics/*             — Economics & Rewards (Phase 4)
"""

import time
import json
import os
import asyncio
import threading
import logging
from datetime import datetime
from html import escape as escape_html
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict

try:
    from fastapi import FastAPI, HTTPException, Query
    from fastapi.responses import HTMLResponse
    from pydantic import BaseModel
    import uvicorn
    from neuron.secp256k1 import verify_message
except ImportError:
    print("❌ MISSING DEPENDENCIES")
    print("Please run: pip install -r requirements.txt")
    print("Or: pip install fastapi uvicorn pydantic cryptography")
    import sys
    sys.exit(1)


from neuron.runtime_safety import (
    LiveModeSafetyError,
    RuntimePolicy,
    load_runtime_policy,
)
from gateway.replay_store import build_gateway_replay_store
from gateway.request_auth import (
    ConfiguredAdminDIDResolver,
    GatewayRequestAuthenticator,
    KeyStatus,
    SystemClock,
    configured_gateway_audience,
)
from gateway.route_policy import validate_route_policy
from gateway.route_security import (
    GatewayRouteSecurityMiddleware,
    TRUSTED_INGRESS_VALUE,
)


logger = logging.getLogger("vams.gateway")


# --- CONFIGURATION ---
VERSION = "v0.2.0-alpha"
NODE_TIMEOUT = 120  # Seconds before node is considered offline
MAX_NODES = 5000
CLEANUP_INTERVAL = 3600 # 1 hour
LIVE_BIND_HOST = "127.0.0.1"
LOCAL_BIND_HOST = "127.0.0.1"
CLIENT_CERT_VERIFIED_HEADERS = (
    "X-VAMS-Client-Cert-Verified",
)
CLIENT_CERT_FINGERPRINT_HEADERS = (
    "X-VAMS-Client-Cert-Fingerprint",
)
CLIENT_CERT_VERIFIED_VALUES = {"1", "true", "success", "verified"}
DEFAULT_LOCAL_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
]


# --- DATA MODELS ---
class HeartbeatRequest(BaseModel):
    payload: str
    signature: str


@dataclass
class NodeInfo:
    node_id: str
    public_key: str = ""
    last_block: int = 0
    network: str = ""
    last_seen: float = 0
    heartbeat_count: int = 0
    first_seen: float = field(default_factory=time.time)

    # CHC Phase 7: agent profile & cognitive properties. Every one of these is
    # SELF-DECLARED by the node's signed heartbeat and verified by nothing here
    # (F15). Defaults are neutral: no invented region, price, score, attestation,
    # skill or cognitive profile is ever shown for a node that did not declare one.
    region: str = "unknown"
    cost_per_hour: float = 0.0
    credit_score: int = 0
    passports: str = ""
    skills: List[str] = field(default_factory=list)
    cognitive_profile: Dict[str, float] = field(default_factory=dict)
    # Not a dataclass field (no annotation). A valid heartbeat signature
    # authenticates who sent these values, not that they are true.
    _SELF_DECLARED_FIELDS = ("region", "cost_per_hour", "credit_score", "passports",
                             "skills", "cognitive_profile")

    @property
    def is_online(self) -> bool:
        return (time.time() - self.last_seen) < NODE_TIMEOUT
    
    @property
    def uptime(self) -> str:
        seconds = time.time() - self.first_seen
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            return f"{int(seconds // 60)}m"
        else:
            return f"{int(seconds // 3600)}h {int((seconds % 3600) // 60)}m"
    
    @property
    def last_seen_formatted(self) -> str:
        return datetime.fromtimestamp(self.last_seen).strftime("%H:%M:%S")

    def to_dict(self) -> dict:
        return {
            **asdict(self),
            # F15: reachability and declared profile are not execution evidence.
            "verification": "unverified-self-declared",
            "self_declared_fields": list(self._SELF_DECLARED_FIELDS),
            "is_online": self.is_online,
            "uptime": self.uptime,
            "last_seen_formatted": self.last_seen_formatted
        }


from contextlib import asynccontextmanager

cleanup_task: Optional[asyncio.Task] = None
active_runtime_policy: Optional[RuntimePolicy] = None
auth_replay_store = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global active_runtime_policy, auth_replay_store, cleanup_task, da_audit_log

    # Runtime policy is the first startup boundary. No owned task or thread may
    # start before this immutable configuration has passed validation.
    policy = load_runtime_policy()
    validate_route_policy(app)
    resolve_allowed_origins(policy=policy)
    admin_password = os.getenv("GATEWAY_ADMIN_PASSWORD")
    if not admin_password:
        raise RuntimeError("CRITICAL: GATEWAY_ADMIN_PASSWORD is not set in the environment.")
    # Reject the removed legacy password rather than treating it as a credential.
    if admin_password == "vams2026":  # nosec B105
        raise RuntimeError("CRITICAL: GATEWAY_ADMIN_PASSWORD is set to the default insecure value 'vams2026'. Please change it.")
    if policy.is_live and not os.getenv("GATEWAY_ADMIN_DID"):
        raise RuntimeError(
            f"CRITICAL: GATEWAY_ADMIN_DID is required when VAMS_ENV={policy.mode.value}."
        )
    if policy.is_live and not os.getenv("GATEWAY_HEARTBEAT_CERT_FINGERPRINTS"):
        raise RuntimeError(
            "CRITICAL: GATEWAY_HEARTBEAT_CERT_FINGERPRINTS is required when "
            f"VAMS_ENV={policy.mode.value}."
        )

    audience = configured_gateway_audience()
    key_resolver = ConfiguredAdminDIDResolver()
    configured_did = os.getenv("GATEWAY_ADMIN_DID", "")
    if policy.is_live and key_resolver.resolve(configured_did).status is not KeyStatus.AVAILABLE:
        raise RuntimeError(
            "CRITICAL: GATEWAY_ADMIN_DID is invalid for live M2 authentication."
        )

    # Only demo startup may opt in to the local Composer/catalogue simulation.
    # Other Gateway functionality remains available with this path disabled.
    _bind_resource_composer(policy)

    # M2.2 storage is initialized before any owned background activity. Live
    # modes require an explicit durable database; no process-local fallback is
    # possible through this factory.
    candidate_auth_replay_store = build_gateway_replay_store(policy)
    candidate_gateway_authenticator = GatewayRequestAuthenticator(
        expected_audience=audience,
        clock=SystemClock(),
        key_resolver=key_resolver,
        replay_store=candidate_auth_replay_store,
    )

    candidate_audit_log = None
    if DA_AUDIT_AVAILABLE:
        candidate_audit_log = PerformanceAuditLog(
            mock_mode=policy.gateway_mock_enabled
        )

    logger.info(
        "gateway runtime mode=%s classification=%s evidence=%s gateway_mock=%s "
        "live_ingress=%s",
        policy.mode.value,
        policy.runtime_classification,
        policy.evidence_classification,
        policy.gateway_mock_enabled,
        TRUSTED_INGRESS_VALUE.decode("ascii") if policy.is_live else "direct-non-live",
    )

    app.state.runtime_policy = policy
    app.state.auth_replay_store = candidate_auth_replay_store
    app.state.gateway_authenticator = candidate_gateway_authenticator
    active_runtime_policy = policy
    auth_replay_store = candidate_auth_replay_store
    da_audit_log = candidate_audit_log
    keeper_started = False
    try:
        if ECONOMICS_AVAILABLE and keeper is not None:
            keeper.start()
            keeper_started = True
        cleanup_task = asyncio.create_task(cleanup_offline_nodes())
        yield
    finally:
        if cleanup_task is not None:
            cleanup_task.cancel()
            try:
                await cleanup_task
            except asyncio.CancelledError:
                pass
            cleanup_task = None
        if keeper_started and keeper is not None:
            keeper.stop()
        da_audit_log = None
        auth_replay_store = None
        active_runtime_policy = None
        if hasattr(app.state, "runtime_policy"):
            del app.state.runtime_policy
        if hasattr(app.state, "auth_replay_store"):
            del app.state.auth_replay_store
        if hasattr(app.state, "gateway_authenticator"):
            del app.state.gateway_authenticator

# --- APPLICATION ---
app = FastAPI(
    title="VAMS Gateway",
    version=VERSION,
    description="Central gateway for VAMS Neuron nodes",
    lifespan=lifespan
)

# VDSO is an isolated, fail-closed shadow/canary router. Importing it may stop
# startup when an unsafe live configuration requests canary or authoritative
# mode; this is intentional and must not be converted into an optional mock.
from gateway.vdso import router as vdso_router

app.include_router(vdso_router)

# --- MIDDLEWARES ---
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.requests import Request

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limit: int = 100, window_sec: int = 60):
        super().__init__(app)
        self.limit = limit
        self.window_sec = window_sec
        self.buckets = {}
        self.lock = threading.Lock()

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        
        with self.lock:
            if client_ip not in self.buckets:
                self.buckets[client_ip] = {"tokens": float(self.limit), "last_refill": now}
            
            bucket = self.buckets[client_ip]
            elapsed = now - bucket["last_refill"]
            refill_amount = elapsed * (self.limit / self.window_sec)
            bucket["tokens"] = min(float(self.limit), bucket["tokens"] + refill_amount)
            bucket["last_refill"] = now
            
            if len(self.buckets) > 1000:
                keys_to_remove = [k for k, v in self.buckets.items() if now - v["last_refill"] > self.window_sec * 2]
                for k in keys_to_remove:
                    del self.buckets[k]

            if bucket["tokens"] >= 1.0:
                bucket["tokens"] -= 1.0
                allowed = True
            else:
                allowed = False

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Rate limit exceeded."}
            )

        return await call_next(request)


class RuntimeClassificationMiddleware(BaseHTTPMiddleware):
    """Attach the sanitized runtime/evidence classification to every response."""

    async def dispatch(self, request: Request, call_next):
        policy = _request_runtime_policy(request)
        response = await call_next(request)
        response.headers["X-VAMS-Runtime-Mode"] = policy.mode.value
        response.headers["X-VAMS-Runtime-Classification"] = (
            policy.runtime_classification
        )
        response.headers["X-VAMS-Evidence-Classification"] = (
            policy.evidence_classification
        )
        return response


class RequestSizeLimitMiddleware:
    def __init__(self, app, max_bytes: int = 1_048_576):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        content_lengths = [
            value
            for key, value in scope.get("headers", [])
            if key.lower() == b"content-length"
        ]
        transfer_encodings = [
            value
            for key, value in scope.get("headers", [])
            if key.lower() == b"transfer-encoding"
        ]
        if transfer_encodings:
            await self._reject(
                scope, receive, send, 400, "unsupported_transfer_encoding"
            )
            return
        if len(content_lengths) > 1:
            await self._reject(
                scope, receive, send, 400, "ambiguous_content_length"
            )
            return
        if content_lengths:
            try:
                content_length = int(content_lengths[0].decode("ascii"))
                if content_length < 0:
                    raise ValueError
            except (UnicodeDecodeError, ValueError):
                await self._reject(
                    scope, receive, send, 400, "malformed_content_length"
                )
                return
            if content_length > self.max_bytes:
                await self._reject(scope, receive, send, 413, "body_too_large")
                return

        buffered_messages = []
        received_bytes = 0
        while True:
            message = await receive()
            buffered_messages.append(message)
            if message["type"] == "http.disconnect":
                break
            if message["type"] != "http.request":
                continue
            received_bytes += len(message.get("body", b""))
            if received_bytes > self.max_bytes:
                await self._reject(scope, receive, send, 413, "body_too_large")
                return
            if not message.get("more_body", False):
                break

        if content_lengths and received_bytes != content_length:
            await self._reject(
                scope, receive, send, 400, "content_length_mismatch"
            )
            return

        message_index = 0

        async def replay_receive():
            nonlocal message_index
            if message_index < len(buffered_messages):
                message = buffered_messages[message_index]
                message_index += 1
                return message
            return {"type": "http.request", "body": b"", "more_body": False}

        await self.app(scope, replay_receive, send)

    @staticmethod
    async def _reject(scope, receive, send, status_code: int, code: str):
        response = JSONResponse(
            status_code=status_code,
            content={"detail": f"gateway_request_denied:{code}"},
        )
        await response(scope, receive, send)

# Configure CORS
def _parse_allowed_origins(raw_origins: str) -> List[str]:
    if raw_origins:
        return [origin.strip() for origin in raw_origins.split(",") if origin.strip()]
    return list(DEFAULT_LOCAL_ALLOWED_ORIGINS)


def resolve_allowed_origins(
    raw_origins: Optional[str] = None,
    *,
    policy: Optional[RuntimePolicy] = None,
) -> List[str]:
    effective_policy = policy or load_runtime_policy()
    allowed_origins_str = (
        os.getenv("GATEWAY_ALLOWED_ORIGINS", "")
        if raw_origins is None
        else raw_origins
    )
    if effective_policy.is_live and not allowed_origins_str:
        raise RuntimeError(
            "GATEWAY_ALLOWED_ORIGINS is required when "
            f"VAMS_ENV={effective_policy.mode.value}."
        )
    allowed_origins = _parse_allowed_origins(allowed_origins_str)

    if effective_policy.is_live and any("*" in origin for origin in allowed_origins):
        raise RuntimeError(
            "Wildcard CORS origins are not allowed when "
            f"VAMS_ENV={effective_policy.mode.value}."
        )
    return allowed_origins


allowed_origins = _parse_allowed_origins(os.getenv("GATEWAY_ALLOWED_ORIGINS", ""))

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-VAMS-Auth-Version",
        "X-VAMS-Auth-Algorithm",
        "X-VAMS-Auth-Audience",
        "X-VAMS-Auth-Signer",
        "X-VAMS-Auth-Nonce",
        "X-VAMS-Auth-Issued-At",
        "X-VAMS-Auth-Expires-At",
        "X-VAMS-Auth-Signature",
    ],
)

# Configure Rate Limiting
rate_limit_env = os.getenv("GATEWAY_RATE_LIMIT", "100")
try:
    if "/" in rate_limit_env:
        limit_str, window_str = rate_limit_env.split("/")
        limit_val = int(limit_str)
        window_val = int(window_str)
    else:
        limit_val = int(rate_limit_env)
        window_val = 60
except ValueError:
    limit_val = 100
    window_val = 60

app.add_middleware(
    RateLimitMiddleware,
    limit=limit_val,
    window_sec=window_val
)
app.add_middleware(GatewayRouteSecurityMiddleware)
app.add_middleware(RequestSizeLimitMiddleware, max_bytes=1_048_576)
app.add_middleware(RuntimeClassificationMiddleware)

# In-memory node registry
nodes: Dict[str, NodeInfo] = {}

# --- RESOURCE COMPOSER (Phase 3) ---
try:
    from neuron.composer.composer import VAMSResourceComposer, ComposerError
    from neuron.composer.blueprints import list_blueprints, get_blueprint
    from neuron.composer.models import InstanceBlueprint, ComputeSpec, GPUType, MemorySpec, StorageSpec, StorageType, NetworkSpec
    from neuron.services.registry_client import ServiceBlockClient
    from neuron.services.macro_blocks import list_macros
    composer = VAMSResourceComposer()
    service_client = ServiceBlockClient()
    COMPOSER_AVAILABLE = True
except ImportError:
    COMPOSER_AVAILABLE = False
    composer = None
    print("\u26a0\ufe0f Resource Composer not available — Phase 3 endpoints disabled")


def _bind_resource_composer(policy: RuntimePolicy) -> None:
    global composer, service_client
    if COMPOSER_AVAILABLE:
        service_client = ServiceBlockClient(simulation=policy.is_demo, policy=policy)
        composer = VAMSResourceComposer(
            service_client=service_client, simulation=policy.is_demo, policy=policy,
        )


def _require_composer_simulation() -> None:
    if not COMPOSER_AVAILABLE:
        raise HTTPException(status_code=503, detail="Resource Composer not available")
    try:
        composer.assert_simulation_available()
    except LiveModeSafetyError:
        raise HTTPException(status_code=503, detail="Authenticated Composer execution unavailable")

# --- ECONOMIC LAYER (Phase 4) ---
try:
    from neuron.economics.keeper import EconomicsKeeper
    from neuron.economics.reward_engine import RewardEngine
    from neuron.economics.regional import RegionalEconomics
    
    econ_engine = RewardEngine(regional_economics=RegionalEconomics())
    keeper = EconomicsKeeper(reward_engine=econ_engine)
    ECONOMICS_AVAILABLE = True
except ImportError:
    ECONOMICS_AVAILABLE = False
    keeper = None
    econ_engine = None
    print("\u26a0\ufe0f Economics Layer not available — Phase 4 endpoints disabled")

# --- DA PERFORMANCE AUDIT (Phase 0 Foundation) ---
try:
    from neuron.da.performance_audit import PerformanceAuditLog
    from neuron.da.models import DAProtocol
    DA_AUDIT_AVAILABLE = True
    da_audit_log = None
except ImportError:
    DA_AUDIT_AVAILABLE = False
    da_audit_log = None
    print("\u26a0\ufe0f DA Audit Layer not available — Phase 0 endpoints disabled")

def _request_runtime_policy(request: Request) -> RuntimePolicy:
    state = getattr(getattr(request, "app", None), "state", None)
    policy = getattr(state, "runtime_policy", None)
    return policy if isinstance(policy, RuntimePolicy) else load_runtime_policy()

def _normalize_cert_fingerprint(value: str) -> str:
    return value.replace(":", "").replace(" ", "").strip().lower()


def _configured_heartbeat_fingerprints() -> set[str]:
    raw = os.getenv("GATEWAY_HEARTBEAT_CERT_FINGERPRINTS", "")
    return {
        _normalize_cert_fingerprint(item)
        for item in raw.split(",")
        if item.strip()
    }


def verify_heartbeat_client_certificate(request: Request) -> Optional[str]:
    """Require proxy-verified mTLS client identity for live heartbeat telemetry."""
    if not _request_runtime_policy(request).is_live:
        return None

    verified = any(
        request.headers.get(header, "").strip().lower() in CLIENT_CERT_VERIFIED_VALUES
        for header in CLIENT_CERT_VERIFIED_HEADERS
    )
    if not verified:
        raise HTTPException(
            status_code=401,
            detail="mTLS client certificate verification is required for live heartbeats.",
        )

    fingerprint = ""
    for header in CLIENT_CERT_FINGERPRINT_HEADERS:
        value = request.headers.get(header)
        if value:
            fingerprint = _normalize_cert_fingerprint(value)
            break
    if not fingerprint:
        raise HTTPException(
            status_code=401,
            detail="mTLS client certificate fingerprint is required for live heartbeats.",
        )

    allowed = _configured_heartbeat_fingerprints()
    if fingerprint not in allowed:
        raise HTTPException(
            status_code=403,
            detail="mTLS client certificate fingerprint is not authorized.",
        )
    return fingerprint


async def cleanup_offline_nodes():
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL)
        current_time = time.time()
        # Remove nodes offline for > 1 hour
        offline_keys = [k for k, v in nodes.items() if (current_time - v.last_seen) > 3600]
        for k in offline_keys:
            del nodes[k]

# Lifespan handles startup events.

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Simple HTML dashboard showing connected nodes."""
    online_nodes = [n for n in nodes.values() if n.is_online]
    offline_nodes = [n for n in nodes.values() if not n.is_online]
    
    rows = ""
    for node in sorted(online_nodes, key=lambda n: n.last_seen, reverse=True):
        rows += f"""
        <tr>
            <td><span class="status online">●</span> {escape_html(str(node.node_id))}</td>
            <td>{node.last_block:,}</td>
            <td>{escape_html(str(node.network))}</td>
            <td>{node.heartbeat_count}</td>
            <td>{escape_html(str(node.uptime))}</td>
            <td>{escape_html(str(node.last_seen_formatted))}</td>
        </tr>
        """
    
    for node in offline_nodes:
        rows += f"""
        <tr class="offline">
            <td><span class="status">●</span> {escape_html(str(node.node_id))}</td>
            <td>{node.last_block:,}</td>
            <td>{escape_html(str(node.network))}</td>
            <td>{node.heartbeat_count}</td>
            <td>{escape_html(str(node.uptime))}</td>
            <td>{escape_html(str(node.last_seen_formatted))}</td>
        </tr>
        """
    
    if not rows:
        rows = '<tr><td colspan="6" style="text-align:center;color:#666;">No nodes connected yet</td></tr>'
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>VAMS Gateway</title>
        <meta http-equiv="refresh" content="5">
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{ 
                font-family: 'Segoe UI', system-ui, sans-serif;
                background: linear-gradient(135deg, #0a0a0a 0%, #1a1a2e 100%);
                color: #e0e0e0;
                min-height: 100vh;
                padding: 40px;
            }}
            .container {{ max-width: 1200px; margin: 0 auto; }}
            h1 {{ 
                font-size: 2.5rem;
                background: linear-gradient(90deg, #00d4ff, #7c3aed);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                margin-bottom: 10px;
            }}
            .subtitle {{ color: #888; margin-bottom: 30px; }}
            .stats {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 20px;
                margin-bottom: 40px;
            }}
            .stat-card {{
                background: rgba(255,255,255,0.05);
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 12px;
                padding: 20px;
            }}
            .stat-value {{ font-size: 2rem; font-weight: bold; color: #00d4ff; }}
            .stat-label {{ color: #888; margin-top: 5px; }}
            table {{
                width: 100%;
                border-collapse: collapse;
                background: rgba(255,255,255,0.03);
                border-radius: 12px;
                overflow: hidden;
            }}
            th, td {{ padding: 15px 20px; text-align: left; }}
            th {{ 
                background: rgba(124,58,237,0.2);
                color: #7c3aed;
                font-weight: 600;
            }}
            tr:nth-child(even) {{ background: rgba(255,255,255,0.02); }}
            tr:hover {{ background: rgba(0,212,255,0.1); }}
            tr.offline {{ opacity: 0.5; }}
            .status {{ font-size: 0.8rem; }}
            .status.online {{ color: #00ff88; }}
            .footer {{
                margin-top: 40px;
                text-align: center;
                color: #555;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>⚡ VAMS Gateway</h1>
            <p class="subtitle">L1 Monitor Network • Celestia Mocha Testnet</p>
            
            <div class="stats">
                <div class="stat-card">
                    <div class="stat-value">{len(online_nodes)}</div>
                    <div class="stat-label">Online Nodes</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{len(nodes)}</div>
                    <div class="stat-label">Total Registered</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{sum(n.heartbeat_count for n in nodes.values()):,}</div>
                    <div class="stat-label">Total Heartbeats</div>
                </div>
            </div>
            
            <table>
                <thead>
                    <tr>
                        <th>Node ID</th>
                        <th>Last Block</th>
                        <th>Network</th>
                        <th>Heartbeats</th>
                        <th>Uptime</th>
                        <th>Last Seen</th>
                    </tr>
                </thead>
                <tbody>
                    {rows}
                </tbody>
            </table>
            
            <p class="footer">VAMS Gateway {VERSION} • Auto-refreshes every 5s</p>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


@app.post("/heartbeat")
async def receive_heartbeat(heartbeat: HeartbeatRequest, http_request: Request):
    """Receive a signed heartbeat from a neuron."""
    try:
        verify_heartbeat_client_certificate(http_request)

        # Parse the payload
        payload = json.loads(heartbeat.payload)
        node_id = payload.get("node_id", "unknown")
        block_height = payload.get("block_height", 0)
        
        # Verify signature with node's public key
        try:
            pub_key_hex = ""
            if node_id in nodes and nodes[node_id].public_key:
                pub_key_hex = nodes[node_id].public_key
            elif "public_key" in payload:
                pub_key_hex = payload["public_key"]
            else:
                raise HTTPException(
                    status_code=403,
                    detail="First heartbeat must include public_key in payload"
                )
            
            if not isinstance(pub_key_hex, str) or not pub_key_hex:
                raise ValueError("signature verification failed")
            if not verify_message(
                bytes.fromhex(pub_key_hex),
                heartbeat.payload.encode(),
                bytes.fromhex(heartbeat.signature),
            ):
                raise ValueError("signature verification failed")
        except (TypeError, ValueError):
            raise HTTPException(status_code=403, detail="Invalid heartbeat signature")
        
        # Update or create node entry
        if node_id not in nodes:
            if len(nodes) >= MAX_NODES:
                # Evict oldest offline node if full
                offline_nodes = [n for n in nodes.values() if not n.is_online]
                if offline_nodes:
                    oldest = min(offline_nodes, key=lambda n: n.last_seen)
                    del nodes[oldest.node_id]
                else:
                    raise HTTPException(status_code=429, detail="Max capacity reached")

            # CHC Phase 7: self-declared fields; neutral defaults (F15).
            region = payload.get("region", "unknown")
            cost_per_hour = payload.get("cost_per_hour", 0.0)
            credit_score = payload.get("credit_score", 0)
            passports = payload.get("passports", "")
            skills = payload.get("skills", [])
            cognitive_profile = payload.get("cognitive_profile", {})

            nodes[node_id] = NodeInfo(
                node_id=node_id,
                region=region,
                cost_per_hour=cost_per_hour,
                credit_score=credit_score,
                passports=passports,
                skills=skills,
                cognitive_profile=cognitive_profile
            )
        
        node = nodes[node_id]
        node.last_block = block_height
        node.last_seen = time.time()
        node.heartbeat_count += 1
        # Network is not assumed (previously hardcoded "mocha-4") and not copied
        # from the payload, which would add an unreviewed captured field (T33).

        # Update fields if in payload
        if "region" in payload:
            node.region = payload["region"]
        if "cost_per_hour" in payload:
            node.cost_per_hour = payload["cost_per_hour"]
        if "credit_score" in payload:
            node.credit_score = payload["credit_score"]
        if "passports" in payload:
            node.passports = payload["passports"]
        if "skills" in payload:
            node.skills = payload["skills"]
        if "cognitive_profile" in payload:
            node.cognitive_profile = payload["cognitive_profile"]
        
        # Store public key on first heartbeat
        if not node.public_key and "public_key" in payload:
            node.public_key = payload["public_key"]
        
        logger.info("gateway heartbeat accepted")
        
        return {
            "status": "ok",
            "node_id": node_id,
            "heartbeat_count": node.heartbeat_count
        }
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid payload JSON")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Heartbeat processing failed")


@app.get("/nodes")
async def list_nodes():
    """List all registered nodes."""
    return {
        "total": len(nodes),
        "online": len([n for n in nodes.values() if n.is_online]),
        "nodes": [n.to_dict() for n in nodes.values()]
    }


@app.get("/health")
async def health_check(request: Request):
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": VERSION,
        "composer_available": COMPOSER_AVAILABLE,
        "runtime": _request_runtime_policy(request).sanitized_summary(),
    }


# ═══════════════════════════════════════════════════════════════
# RESOURCE COMPOSITION ENDPOINTS (Phase 3)
# ═══════════════════════════════════════════════════════════════

class ComposeRequest(BaseModel):
    """Request body for blueprint-based provisioning."""
    blueprint_name: Optional[str] = None  # Use pre-defined blueprint
    service_block_name: Optional[str] = None # Use registered service block
    macro_block_name: Optional[str] = None # Use composite macro block
    # OR custom blueprint fields:
    name: Optional[str] = None
    gpu_type: Optional[str] = None
    gpu_count: int = 0
    vcpu: int = 4
    ram_gb: int = 16
    storage_gb: int = 100
    region: Optional[str] = None
    max_cost_per_hour: float = 0.0
    elastic: bool = False
    min_replicas: int = 1
    max_replicas: int = 1
    required_service_blocks: List[str] = []


@app.post("/compose")
async def compose_resources(request: ComposeRequest):
    """Submit a blueprint for explicit demo simulation; no provider execution."""
    _require_composer_simulation()

    try:
        from neuron.economics.gas_premium import GasAbstractionPremiumCalculator
        calculator = GasAbstractionPremiumCalculator()

        if request.blueprint_name:
            instance = composer.provision_blueprint(request.blueprint_name)
        elif request.service_block_name:
            instance = composer.provision_service_block(request.service_block_name)
        elif request.macro_block_name:
            instances = composer.provision_macro_block(request.macro_block_name)
            
            total_base = sum(i.allocation.total_hourly_cost for i in instances)
            total_premium = 0.0
            for i in instances:
                req_b = getattr(i.blueprint, "required_service_blocks", [])
                total_premium += calculator.calculate_premium_cost(i.allocation.total_hourly_cost, req_b)
            total_hourly = total_base + total_premium
            
            return {
                "status": "simulated",
                "simulation": True,
                "evidence_classification": "non-authoritative",
                "instances": [i.to_dict() for i in instances],
                "base_hourly_cost": round(total_base, 6),
                "premium_rate_bps": 0,
                "premium_hourly_cost": round(total_premium, 6),
                "total_hourly_cost": round(total_hourly, 6),
            }
        elif request.name:
            bp = InstanceBlueprint(
                name=request.name,
                compute=ComputeSpec(
                    gpu_type=GPUType(request.gpu_type) if request.gpu_type else GPUType.ANY,
                    gpu_count=request.gpu_count,
                    vcpu=request.vcpu,
                ),
                memory=MemorySpec(ram_gb=request.ram_gb),
                storage=StorageSpec(capacity_gb=request.storage_gb),
                networking=NetworkSpec(region=request.region or ""),
                max_cost_per_hour=request.max_cost_per_hour,
                elastic=request.elastic,
                min_replicas=request.min_replicas,
                max_replicas=request.max_replicas,
                required_service_blocks=request.required_service_blocks if hasattr(request, 'required_service_blocks') else []
            )
            instance = composer.provision(bp)
        else:
            raise HTTPException(status_code=400, detail="Provide blueprint_name or custom blueprint fields")

        bp = instance.blueprint
        required_blocks = getattr(bp, "required_service_blocks", [])
        premium_rate = calculator.calculate_premium_rate(required_blocks)
        premium_rate_bps = int(premium_rate * 10000)
        
        base_hourly_cost = instance.allocation.total_hourly_cost
        premium_hourly_cost = calculator.calculate_premium_cost(base_hourly_cost, required_blocks)
        total_hourly_cost = calculator.calculate_total_cost(base_hourly_cost, required_blocks)

        return {
            "status": "simulated",
            "simulation": True,
            "evidence_classification": "non-authoritative",
            "instance": instance.to_dict(),
            "base_hourly_cost": round(base_hourly_cost, 6),
            "premium_rate_bps": premium_rate_bps,
            "premium_hourly_cost": round(premium_hourly_cost, 6),
            "total_hourly_cost": round(total_hourly_cost, 6),
        }

    except LiveModeSafetyError:
        raise HTTPException(status_code=503, detail="Authenticated Composer execution unavailable")
    except (ComposerError, KeyError) as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.delete("/compose/{instance_id}")
async def deprovision_resources(instance_id: str):
    """Remove a local simulation only; no provider release or settlement."""
    if not COMPOSER_AVAILABLE:
        raise HTTPException(status_code=503, detail="Resource Composer not available")

    try:
        success = composer.deprovision(instance_id)
    except LiveModeSafetyError:
        raise HTTPException(status_code=503, detail="Authenticated provider deprovisioning unavailable")
    if not success:
        raise HTTPException(status_code=404, detail=f"Instance {instance_id} not found")
    return {"status": "simulation_removed", "instance_id": instance_id,
            "simulation": True, "evidence_classification": "non-authoritative"}


@app.get("/compose/instances")
async def list_composed_instances():
    """Inspect local records, including simulations after runtime drift."""
    if not COMPOSER_AVAILABLE:
        raise HTTPException(status_code=503, detail="Resource Composer not available")

    instances = composer.list_instances()
    return {
        "total": len(instances),
        "instances": [i.to_dict() for i in instances],
        "stats": composer.get_stats(),
        "evidence_classification": "non-authoritative",
    }


@app.get("/compose/blueprints")
async def list_available_blueprints():
    """List pre-defined blueprints (no auth required)."""
    if not COMPOSER_AVAILABLE:
        raise HTTPException(status_code=503, detail="Resource Composer not available")

    return {"blueprints": list_blueprints(), "catalogue_kind": "static-planning-templates",
            "registry_verified": False, "evidence_classification": "non-authoritative"}


@app.get("/services/blocks")
async def list_service_blocks(category: Optional[str] = None):
    """List explicit demo declarations; no authenticated registry read."""
    _require_composer_simulation()
    return {"blocks": service_client.list_blocks(category=category), "simulation": True,
            "registry_verified": False, "evidence_classification": "non-authoritative"}


@app.get("/services/macros")
async def list_macro_blocks():
    """List pre-defined macro composite blocks."""
    _require_composer_simulation()
    return {"macros": service_client.list_macros(), "simulation": True,
            "registry_verified": False, "evidence_classification": "non-authoritative"}


# ═══════════════════════════════════════════════════════════════
# ECONOMICS ENDPOINTS (Phase 4)
# ═══════════════════════════════════════════════════════════════

@app.get("/economics/status")
async def get_economics_status():
    """Get the current running status of the Economics Keeper."""
    if not ECONOMICS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Economics Layer not available")
    return keeper.get_status()

@app.get("/economics/epochs")
async def list_epochs():
    """List all completed reward epochs."""
    if not ECONOMICS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Economics Layer not available")
    
    summaries = keeper.get_all_summaries()
    return {
        "total_epochs": len(summaries),
        "epochs": summaries
    }

@app.get("/economics/epochs/{epoch_id}")
async def get_epoch(epoch_id: int):
    """Get details for a specific reward epoch."""
    if not ECONOMICS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Economics Layer not available")
    
    summary = keeper.get_epoch_summary(epoch_id)
    if not summary:
        raise HTTPException(status_code=404, detail=f"Epoch {epoch_id} not found")
        
    return summary

@app.get("/economics/estimate-apr")
async def estimate_apr(
    region_id: str = "us-east-1",
    capacity_contribution: int = 10,
    staked_amount: float = 0.0,
    epoch_emission_budget: float = 383000.0,
    total_region_capacity: int = 100
):
    """Estimate APR and weekly rewards for a provider."""
    if not ECONOMICS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Economics Layer not available")
    
    return econ_engine.estimate_provider_apr(
        region_id=region_id,
        capacity_contribution=capacity_contribution,
        staked_amount=staked_amount,
        epoch_emission_budget=epoch_emission_budget,
        total_region_capacity=total_region_capacity
    )


# ============================================================
#            DA PERFORMANCE AUDIT ENDPOINTS (Phase 0)
# ============================================================

@app.get("/da/status")
async def da_status(request: Request):
    """Get live connectivity status for all DA layer adapters."""
    if not DA_AUDIT_AVAILABLE or da_audit_log is None:
        raise HTTPException(status_code=503, detail="DA Audit Layer not available")
    
    status = await da_audit_log.get_adapter_status()
    return {
        "version": VERSION,
        "da_layer": "Phase 0 Foundation",
        "runtime": _request_runtime_policy(request).sanitized_summary(),
        "adapters": status,
    }

@app.get("/da/anchors")
async def da_anchors(
    request: Request,
    protocol: Optional[str] = None,
    limit: int = Query(default=50, ge=1),
):
    """Query anchored performance audit records."""
    if not DA_AUDIT_AVAILABLE or da_audit_log is None:
        raise HTTPException(status_code=503, detail="DA Audit Layer not available")
    
    history = da_audit_log.get_audit_history(limit=limit)
    
    # Optional filter by protocol
    if protocol:
        history = [h for h in history if h.get("protocol") == protocol]
    
    return {
        "total": len(history),
        "protocol_filter": protocol,
        "runtime": _request_runtime_policy(request).sanitized_summary(),
        "anchors": history,
    }


def main():
    """Run the gateway server."""
    policy = load_runtime_policy()
    bind_host = LIVE_BIND_HOST if policy.is_live else LOCAL_BIND_HOST
    print()
    print("⚡ VAMS Gateway Server")
    print(f"   Version: {VERSION}")
    print(f"   Dashboard: http://localhost:8000")
    print(f"   API Docs: http://localhost:8000/docs")
    print(f"   Bind Host: {bind_host}")
    print(f"   Runtime: {policy.mode.value} ({policy.runtime_classification})")
    print(f"   Evidence: {policy.evidence_classification}")
    print()

    uvicorn.run(app, host=bind_host, port=8000)


if __name__ == "__main__":
    main()
