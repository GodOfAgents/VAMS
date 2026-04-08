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
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict

try:
    from fastapi import FastAPI, HTTPException, Depends
    from fastapi.responses import HTMLResponse
    from fastapi.security import HTTPBasic, HTTPBasicCredentials
    from starlette.status import HTTP_401_UNAUTHORIZED
    from pydantic import BaseModel
    import uvicorn
except ImportError:
    print("❌ MISSING DEPENDENCIES")
    print("Please run: pip install -r requirements.txt")
    print("Or: pip install fastapi uvicorn pydantic")
    import sys
    sys.exit(1)

try:
    from ecdsa import VerifyingKey, SECP256k1, BadSignatureError
    ECDSA_AVAILABLE = True
except ImportError:
    ECDSA_AVAILABLE = False
    print("⚠️ ECDSA not available - signature verification disabled")


# --- CONFIGURATION ---
VERSION = "v0.2.0-alpha"
NODE_TIMEOUT = 120  # Seconds before node is considered offline
MAX_NODES = 5000
CLEANUP_INTERVAL = 3600 # 1 hour


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


# --- APPLICATION ---
app = FastAPI(
    title="VAMS Gateway",
    version=VERSION,
    description="Central gateway for VAMS Neuron nodes"
)

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
    da_audit_log = PerformanceAuditLog(mock_mode=True)
    DA_AUDIT_AVAILABLE = True
except ImportError:
    DA_AUDIT_AVAILABLE = False
    da_audit_log = None
    print("\u26a0\ufe0f DA Audit Layer not available — Phase 0 endpoints disabled")

import os
import secrets
import asyncio

security = HTTPBasic()

def get_current_username(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = secrets.compare_digest(credentials.username, os.getenv("GATEWAY_ADMIN_USER", "admin"))
    correct_password = secrets.compare_digest(credentials.password, os.getenv("GATEWAY_ADMIN_PASSWORD", "vams2026"))
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

async def cleanup_offline_nodes():
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL)
        current_time = time.time()
        # Remove nodes offline for > 1 hour
        offline_keys = [k for k, v in nodes.items() if (current_time - v.last_seen) > 3600]
        for k in offline_keys:
            del nodes[k]

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(cleanup_offline_nodes())

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
async def receive_heartbeat(request: HeartbeatRequest):
    """Receive a signed heartbeat from a neuron."""
    try:
        # Parse the payload
        payload = json.loads(request.payload)
        node_id = payload.get("node_id", "unknown")
        block_height = payload.get("block_height", 0)
        
        # Verify signature with node's public key
        if ECDSA_AVAILABLE:
            try:
                # The node's public key should be registered on first heartbeat
                if node_id in nodes and nodes[node_id].public_key:
                    vk = VerifyingKey.from_string(
                        bytes.fromhex(nodes[node_id].public_key),
                        curve=SECP256k1
                    )
                    vk.verify(
                        bytes.fromhex(request.signature),
                        request.payload.encode()
                    )
                elif "public_key" not in payload:
                    raise HTTPException(
                        status_code=403,
                        detail="First heartbeat must include public_key in payload"
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
            nodes[node_id] = NodeInfo(node_id=node_id)
        
        node = nodes[node_id]
        node.last_block = block_height
        node.last_seen = time.time()
        node.heartbeat_count += 1
        node.network = "mocha-4"  # From Celestia
        
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


@app.post("/compose")
async def compose_resources(request: ComposeRequest, username: str = Depends(get_current_username)):
    """Submit a blueprint to provision resources."""
    if not COMPOSER_AVAILABLE:
        raise HTTPException(status_code=503, detail="Resource Composer not available")

    try:
        if request.blueprint_name:
            instance = composer.provision_blueprint(request.blueprint_name)
        elif request.service_block_name:
            instance = composer.provision_service_block(request.service_block_name)
        elif request.macro_block_name:
            instances = composer.provision_macro_block(request.macro_block_name)
            return {"status": "provisioned", "instances": [i.to_dict() for i in instances]}
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
            )
            instance = composer.provision(bp)
        else:
            raise HTTPException(status_code=400, detail="Provide blueprint_name or custom blueprint fields")

        return {"status": "provisioned", "instance": instance.to_dict()}

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
    print()
    print("⚡ VAMS Gateway Server")
    print(f"   Version: {VERSION}")
    print(f"   Dashboard: http://localhost:8000")
    print(f"   API Docs: http://localhost:8000/docs")
    print()
    
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
