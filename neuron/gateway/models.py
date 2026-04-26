from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from enum import Enum
import time

class AgentStatus(str, Enum):
    ACTIVE = "active"
    OFFLINE = "offline"
    BUSY = "busy"
    SLASHED = "slashed"

class RegisterRequest(BaseModel):
    node_id: str = Field(..., description="Unique identifier for the agent node (bytes32 hex)", pattern=r"^0x[a-fA-F0-9]{64}$")
    public_key: str = Field(..., description="Agent's public signing key")
    stake_amount: float = Field(0.0, description="Amount of VAMS staked")
    capabilities: Dict[str, Any] = Field(default_factory=dict, description="Compute/Storage capabilities")
    version: str = Field("1.0.0", description="Neuron version")

class HeartbeatRequest(BaseModel):
    payload: str = Field(..., description="Signed content: timestamp, status")
    signature: str = Field(..., description="Cryptographic signature of payload")

class Task(BaseModel):
    task_id: str
    type: str
    payload: Dict[str, Any]
    reward: float
    created_at: float = Field(default_factory=time.time)
    expires_at: float

class TaskResult(BaseModel):
    task_id: str
    result: Dict[str, Any]
    signature: str
    timestamp: float = Field(default_factory=time.time)

class GenericResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
