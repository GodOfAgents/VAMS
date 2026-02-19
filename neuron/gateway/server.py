from fastapi import FastAPI, HTTPException, Request, Depends, status
import logging
from typing import Dict, List, Optional
import time
import uvicorn
from contextlib import asynccontextmanager

from gateway.models import (
    RegisterRequest, HeartbeatRequest, Task, TaskResult, GenericResponse, AgentStatus
)
from gateway.rate_limiter import RateLimiter

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("GatewayServer")

# Global State (In-Memory for MVP)
AGENTS: Dict[str, Dict] = {}
TASKS: Dict[str, Task] = {}
PENDING_TASKS: Dict[str, List[str]] = {} # node_id -> [task_ids]

# Rate Limiter
limiter = RateLimiter(default_limit=100, window_sec=60)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 VAMS Gateway Server Starting...")
    yield
    logger.info("🛑 VAMS Gateway Server Stopping...")

app = FastAPI(title="VAMS Gateway", version="1.0.0", lifespan=lifespan)

# Middleware for Rate Limiting
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host
    if not limiter.is_allowed(client_ip):
        return await call_next(request) # For now, just log warning in limiter, don't block fully for easy testing
        # In prod: return JSONResponse(status_code=429, content={"detail": "Rate Limit Exceeded"})
    return await call_next(request)

@app.get("/")
def home():
    return {"status": "online", "system": "VAMS Gateway", "agents_active": len(AGENTS)}

@app.post("/agents/register", response_model=GenericResponse)
def register_agent(req: RegisterRequest):
    if req.node_id in AGENTS:
        # Update existing
        AGENTS[req.node_id].update({
           "last_seen": time.time(),
           "ip": "unknown",
           "status": AgentStatus.ACTIVE
        })
        return GenericResponse(success=True, message="Agent updated", data={"agent_id": req.node_id})
    
    AGENTS[req.node_id] = {
        "public_key": req.public_key,
        "stake": req.stake_amount,
        "capabilities": req.capabilities,
        "last_seen": time.time(),
        "status": AgentStatus.ACTIVE,
        "tasks_completed": 0
    }
    PENDING_TASKS[req.node_id] = []
    logger.info(f"✅ New Agent Registered: {req.node_id} (Stake: {req.stake_amount})")
    
    return GenericResponse(success=True, message="Agent registered", data={"agent_id": req.node_id})

@app.post("/heartbeat", response_model=GenericResponse)
def heartbeat(req: HeartbeatRequest):
    # Verify signature (Stub)
    # In real impl: verify_signature(req.payload, req.signature, stored_public_key)
    
    # Payload format: "timestamp|status|node_id" (naive)
    try:
        parts = req.payload.split("|")
        if len(parts) < 3:
             return GenericResponse(success=False, message="Invalid payload format")
             
        ts, status, node_id = parts[0], parts[1], parts[2]
        
        if node_id not in AGENTS:
            return GenericResponse(success=False, message="Agent not registered")
            
        AGENTS[node_id]["last_seen"] = time.time()
        AGENTS[node_id]["status"] = status
        
        return GenericResponse(success=True, message="Heartbeat ack")
        
    except Exception as e:
        logger.error(f"Heartbeat error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/tasks/pending")
def get_pending_tasks(node_id: str):
    if node_id not in PENDING_TASKS:
        return {"tasks": []}
        
    task_ids = PENDING_TASKS[node_id]
    tasks = [TASKS[tid] for tid in task_ids if tid in TASKS]
    return {"tasks": tasks}

@app.post("/tasks/{task_id}/result", response_model=GenericResponse)
def submit_result(task_id: str, res: TaskResult):
    if task_id not in TASKS:
        raise HTTPException(status_code=404, detail="Task not found")
        
    # Process result (update DB, smart contract, etc)
    logger.info(f"📩 Result received for {task_id}")
    
    # Cleanup
    if task_id in TASKS:
        del TASKS[task_id]
        
    # Update agent stats
    # (Assuming we knew who sent it - would need auth)
    
    return GenericResponse(success=True, message="Result accepted")

def start_server(host="0.0.0.0", port=8000):
    uvicorn.run(app, host=host, port=port)

if __name__ == "__main__":
    start_server()
