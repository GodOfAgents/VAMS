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
import secrets
import asyncio
import threading
import hashlib
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict

try:
    from fastapi import FastAPI, HTTPException, Depends
    from fastapi.responses import HTMLResponse
    from fastapi.security import HTTPBasic, HTTPBasicCredentials
    from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_500_INTERNAL_SERVER_ERROR
    from pydantic import BaseModel
    import uvicorn
    from ecdsa import VerifyingKey, SECP256k1, BadSignatureError
except ImportError:
    print("❌ MISSING DEPENDENCIES")
    print("Please run: pip install -r requirements.txt")
    print("Or: pip install fastapi uvicorn pydantic ecdsa")
    import sys
    sys.exit(1)


from neuron.runtime_safety import current_environment, is_live_environment


# --- CONFIGURATION ---
VERSION = "v0.2.0-alpha"
NODE_TIMEOUT = 120  # Seconds before node is considered offline
MAX_NODES = 5000
CLEANUP_INTERVAL = 3600 # 1 hour
AUTH_REPLAY_WINDOW_SECONDS = 300
LIVE_BIND_HOST = "127.0.0.1"
LOCAL_BIND_HOST = "0.0.0.0"
CLIENT_CERT_VERIFIED_HEADERS = (
    "X-VAMS-Client-Cert-Verified",
    "X-Forwarded-Tls-Client-Cert-Verified",
    "X-SSL-Client-Verify",
)
CLIENT_CERT_FINGERPRINT_HEADERS = (
    "X-VAMS-Client-Cert-Fingerprint",
    "X-Forwarded-Tls-Client-Cert-Fingerprint",
    "X-SSL-Client-Fingerprint",
)
CLIENT_CERT_VERIFIED_VALUES = {"1", "true", "success", "verified"}


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

    # CHC Phase 7: Add agent profile & cognitive properties
    region: str = "us-east-1"
    cost_per_hour: float = 0.15
    credit_score: int = 750
    passports: str = "ERC-8004 Phala TEE"
    skills: List[str] = field(default_factory=list)
    cognitive_profile: Dict[str, float] = field(default_factory=dict)

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
    
    def to_dict(self) -> dict:
        return {
            **asdict(self),
            "is_online": self.is_online,
            "uptime": self.uptime,
            "last_seen_formatted": datetime.fromtimestamp(self.last_seen).strftime("%H:%M:%S")
        }


from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup tasks
    admin_password = os.getenv("GATEWAY_ADMIN_PASSWORD")
    if not admin_password:
        raise RuntimeError("CRITICAL: GATEWAY_ADMIN_PASSWORD is not set in the environment.")
    if admin_password == "vams2026":
        raise RuntimeError("CRITICAL: GATEWAY_ADMIN_PASSWORD is set to the default insecure value 'vams2026'. Please change it.")
    if is_live_environment() and not os.getenv("GATEWAY_ADMIN_DID"):
        raise RuntimeError(
            f"CRITICAL: GATEWAY_ADMIN_DID is required when VAMS_ENV={current_environment()}."
        )
    if is_live_environment() and not os.getenv("GATEWAY_HEARTBEAT_CERT_FINGERPRINTS"):
        raise RuntimeError(
            f"CRITICAL: GATEWAY_HEARTBEAT_CERT_FINGERPRINTS is required when VAMS_ENV={current_environment()}."
        )
        
    asyncio.create_task(cleanup_offline_nodes())
    yield

# --- APPLICATION ---
app = FastAPI(
    title="VAMS Gateway",
    version=VERSION,
    description="Central gateway for VAMS Neuron nodes",
    lifespan=lifespan
)

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

# Configure CORS
allowed_origins_str = os.getenv("GATEWAY_ALLOWED_ORIGINS", "")
if allowed_origins_str:
    allowed_origins = [origin.strip() for origin in allowed_origins_str.split(",") if origin.strip()]
else:
    allowed_origins = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173"
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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

# In-memory node registry
nodes: Dict[str, NodeInfo] = {}
used_did_signatures: Dict[str, float] = {}

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

# --- ECONOMIC LAYER (Phase 4) ---
try:
    from neuron.economics.keeper import EconomicsKeeper
    from neuron.economics.reward_engine import RewardEngine
    from neuron.economics.regional import RegionalEconomics
    
    econ_engine = RewardEngine(regional_economics=RegionalEconomics())
    keeper = EconomicsKeeper(reward_engine=econ_engine)
    keeper.start()
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
    from neuron.runtime_safety import require_not_live_mock
    mock_mode_flag = os.getenv("VAMS_MOCK_MODE", "true").lower() == "true"
    require_not_live_mock("Gateway DA audit log", mock_mode_flag)
    da_audit_log = PerformanceAuditLog(mock_mode=mock_mode_flag)
    DA_AUDIT_AVAILABLE = True
except ImportError:
    DA_AUDIT_AVAILABLE = False
    da_audit_log = None
    print("\u26a0\ufe0f DA Audit Layer not available — Phase 0 endpoints disabled")

security = HTTPBasic(auto_error=False)

def verify_did_signature(did: str, signature_hex: str, timestamp_str: str, method: str, path: str) -> bool:
    try:
        ts = float(timestamp_str)
        now = time.time()
        if abs(now - ts) > AUTH_REPLAY_WINDOW_SECONDS:
            return False

        # Store only a digest of the credential tuple; raw signatures remain out of memory logs/state.
        replay_key = hashlib.sha256(
            f"{did}:{signature_hex}:{timestamp_str}:{method}:{path}".encode("utf-8")
        ).hexdigest()
        expired_keys = [
            key for key, seen_at in used_did_signatures.items()
            if now - seen_at > AUTH_REPLAY_WINDOW_SECONDS
        ]
        for key in expired_keys:
            del used_did_signatures[key]
        if replay_key in used_did_signatures:
            return False

        pubkey_hex = did
        if did.startswith("did:key:"):
            pubkey_hex = did[len("did:key:"):]

        authorized_did = os.getenv("GATEWAY_ADMIN_DID")
        if not authorized_did:
            return False

        auth_pubkey = authorized_did[len("did:key:"):] if authorized_did.startswith("did:key:") else authorized_did
        if pubkey_hex.lower() != auth_pubkey.lower():
            return False

        message = f"VAMS_ADMIN_AUTH:{method}:{path}:{timestamp_str}"
        vk = VerifyingKey.from_string(
            bytes.fromhex(pubkey_hex),
            curve=SECP256k1
        )
        verified = vk.verify(
            bytes.fromhex(signature_hex),
            message.encode()
        )
        if verified:
            used_did_signatures[replay_key] = now
        return verified
    except Exception:
        return False

from fastapi import Request

def get_current_username(request: Request, credentials: Optional[HTTPBasicCredentials] = Depends(security)):
    # Check headers for DID Auth first
    did = request.headers.get("X-VAMS-DID")
    signature = request.headers.get("X-VAMS-Signature")
    timestamp = request.headers.get("X-VAMS-Timestamp")

    if did and signature and timestamp:
        if verify_did_signature(did, signature, timestamp, request.method, request.url.path):
            return did
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Invalid DID signature or timestamp expired",
            headers={"WWW-Authenticate": "Basic"},
        )

    if is_live_environment():
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="DID authentication is required for live gateway control-plane routes.",
        )

    # Fallback to Basic Auth
    if credentials:
        admin_user = os.getenv("GATEWAY_ADMIN_USER", "admin")
        admin_password = os.getenv("GATEWAY_ADMIN_PASSWORD")
        if not admin_password:
            raise HTTPException(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Server configuration error: Admin password not configured"
            )
        correct_username = secrets.compare_digest(credentials.username, admin_user)
        correct_password = secrets.compare_digest(credentials.password, admin_password)
        if correct_username and correct_password:
            return credentials.username
            
    raise HTTPException(
        status_code=HTTP_401_UNAUTHORIZED,
        detail="Not authenticated. Provide DID headers or Basic Auth.",
        headers={"WWW-Authenticate": "Basic"},
    )


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
    if not is_live_environment():
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
async def dashboard(username: str = Depends(get_current_username)):
    """Simple HTML dashboard showing connected nodes."""
    online_nodes = [n for n in nodes.values() if n.is_online]
    offline_nodes = [n for n in nodes.values() if not n.is_online]
    
    rows = ""
    for node in sorted(online_nodes, key=lambda n: n.last_seen, reverse=True):
        rows += f"""
        <tr>
            <td><span class="status online">●</span> {node.node_id}</td>
            <td>{node.last_block:,}</td>
            <td>{node.network}</td>
            <td>{node.heartbeat_count}</td>
            <td>{node.uptime}</td>
            <td>{node.last_seen_formatted}</td>
        </tr>
        """
    
    for node in offline_nodes:
        rows += f"""
        <tr class="offline">
            <td><span class="status">●</span> {node.node_id}</td>
            <td>{node.last_block:,}</td>
            <td>{node.network}</td>
            <td>{node.heartbeat_count}</td>
            <td>{node.uptime}</td>
            <td>{node.last_seen_formatted}</td>
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
            
            if pub_key_hex:
                vk = VerifyingKey.from_string(
                    bytes.fromhex(pub_key_hex),
                    curve=SECP256k1
                )
                vk.verify(
                    bytes.fromhex(heartbeat.signature),
                    heartbeat.payload.encode()
                )
        except BadSignatureError:
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

            # CHC Phase 7: Extract fields from payload or use defaults
            region = payload.get("region", "us-east-1")
            cost_per_hour = payload.get("cost_per_hour", 0.15)
            credit_score = payload.get("credit_score", 750)
            passports = payload.get("passports", "ERC-8004 Phala TEE")
            skills = payload.get("skills", ["token-swap", "arbitrage-analysis"])
            cognitive_profile = payload.get("cognitive_profile", {
                "K": 0.85, "RW": 0.90, "M": 0.95, "R": 0.80, "WM": 0.75, "MS": 0.85, "MR": 0.90, "V": 0.40, "A": 0.30, "S": 0.95
            })

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
        node.network = "mocha-4"  # From Celestia

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
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Heartbeat from {node_id}: Block #{block_height}")
        
        return {
            "status": "ok",
            "node_id": node_id,
            "heartbeat_count": node.heartbeat_count
        }
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid payload JSON")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/nodes")
async def list_nodes():
    """List all registered nodes."""
    return {
        "total": len(nodes),
        "online": len([n for n in nodes.values() if n.is_online]),
        "nodes": [n.to_dict() for n in nodes.values()]
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": VERSION, "composer_available": COMPOSER_AVAILABLE}


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
async def compose_resources(request: ComposeRequest, username: str = Depends(get_current_username)):
    """Submit a blueprint to provision resources."""
    if not COMPOSER_AVAILABLE:
        raise HTTPException(status_code=503, detail="Resource Composer not available")

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
                "status": "provisioned",
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
            # Wait, ComposeRequest might not have required_service_blocks. Let's check ComposeRequest to be safe.
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
            "status": "provisioned",
            "instance": instance.to_dict(),
            "base_hourly_cost": round(base_hourly_cost, 6),
            "premium_rate_bps": premium_rate_bps,
            "premium_hourly_cost": round(premium_hourly_cost, 6),
            "total_hourly_cost": round(total_hourly_cost, 6),
        }

    except (ComposerError, KeyError) as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.delete("/compose/{instance_id}")
async def deprovision_resources(instance_id: str, username: str = Depends(get_current_username)):
    """Deprovision an active composed instance."""
    if not COMPOSER_AVAILABLE:
        raise HTTPException(status_code=503, detail="Resource Composer not available")

    success = composer.deprovision(instance_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Instance {instance_id} not found")
    return {"status": "deprovisioned", "instance_id": instance_id}


@app.get("/compose/instances")
async def list_composed_instances(username: str = Depends(get_current_username)):
    """List all active composed instances."""
    if not COMPOSER_AVAILABLE:
        raise HTTPException(status_code=503, detail="Resource Composer not available")

    instances = composer.list_active_instances()
    return {
        "total": len(instances),
        "instances": [i.to_dict() for i in instances],
        "stats": composer.get_stats(),
    }


@app.get("/compose/blueprints")
async def list_available_blueprints():
    """List pre-defined blueprints (no auth required)."""
    if not COMPOSER_AVAILABLE:
        raise HTTPException(status_code=503, detail="Resource Composer not available")

    return {"blueprints": list_blueprints()}


@app.get("/services/blocks")
async def list_service_blocks(category: Optional[str] = None):
    """List available service blocks from the registry."""
    if not COMPOSER_AVAILABLE:
        raise HTTPException(status_code=503, detail="Resource Composer not available")
    return {"blocks": service_client.list_blocks(category=category)}


@app.get("/services/macros")
async def list_macro_blocks():
    """List pre-defined macro composite blocks."""
    if not COMPOSER_AVAILABLE:
        raise HTTPException(status_code=503, detail="Resource Composer not available")
    return {"macros": list_macros()}


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
async def da_status():
    """Get live connectivity status for all DA layer adapters."""
    if not DA_AUDIT_AVAILABLE:
        raise HTTPException(status_code=503, detail="DA Audit Layer not available")
    
    status = await da_audit_log.get_adapter_status()
    return {
        "version": VERSION,
        "da_layer": "Phase 0 Foundation",
        "adapters": status,
    }

@app.get("/da/anchors")
async def da_anchors(
    protocol: Optional[str] = None,
    limit: int = 50,
):
    """Query anchored performance audit records."""
    if not DA_AUDIT_AVAILABLE:
        raise HTTPException(status_code=503, detail="DA Audit Layer not available")
    
    history = da_audit_log.get_audit_history(limit=limit)
    
    # Optional filter by protocol
    if protocol:
        history = [h for h in history if h.get("protocol") == protocol]
    
    return {
        "total": len(history),
        "protocol_filter": protocol,
        "anchors": history,
    }


def main():
    """Run the gateway server."""
    bind_host = LIVE_BIND_HOST if is_live_environment() else LOCAL_BIND_HOST
    print()
    print("⚡ VAMS Gateway Server")
    print(f"   Version: {VERSION}")
    print(f"   Dashboard: http://localhost:8000")
    print(f"   API Docs: http://localhost:8000/docs")
    print(f"   Bind Host: {bind_host}")
    print()

    uvicorn.run(app, host=bind_host, port=8000)


if __name__ == "__main__":
    main()
