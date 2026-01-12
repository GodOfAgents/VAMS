#!/usr/bin/env python3
"""
VAMS Gateway Server v0.1.0
==========================
Simple FastAPI server to receive and display neuron heartbeats.

This is OPTIONAL - neurons work in standalone mode without it.
The gateway provides a central view of all running nodes.
"""

import time
import json
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse
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
VERSION = "v0.1.0-alpha"
NODE_TIMEOUT = 120  # Seconds before node is considered offline


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


@app.get("/", response_class=HTMLResponse)
async def dashboard():
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
        
        # TODO: Verify signature with node's public key
        # For MVP, we accept all heartbeats
        
        # Update or create node entry
        if node_id not in nodes:
            nodes[node_id] = NodeInfo(node_id=node_id)
        
        node = nodes[node_id]
        node.last_block = block_height
        node.last_seen = time.time()
        node.heartbeat_count += 1
        node.network = "mocha-4"  # From Celestia
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Heartbeat from {node_id}: Block #{block_height}")
        
        return {
            "status": "ok",
            "node_id": node_id,
            "heartbeat_count": node.heartbeat_count
        }
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid payload JSON")
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
    return {"status": "healthy", "version": VERSION}


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
