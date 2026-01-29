"""
VAMS Neuron - Workflow Engine (Layer 3: Logic)
===============================================
DBOS-style workflow checkpoints for crash-proof execution.

Features:
- Automatic checkpointing at each step
- Crash recovery from last checkpoint
- Exactly-once execution semantics
- Local SQLite persistence
"""

import time
import json
import sqlite3
import functools
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable
from enum import Enum
from datetime import datetime


class WorkflowStatus(Enum):
    """Status of a workflow execution."""
    PENDING = "pending"
    RUNNING = "running"
    CHECKPOINTED = "checkpointed"
    COMPLETED = "completed"
    FAILED = "failed"
    RECOVERED = "recovered"


@dataclass
class Checkpoint:
    """A workflow checkpoint."""
    workflow_id: str
    step_name: str
    step_index: int
    data: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "step_name": self.step_name,
            "step_index": self.step_index,
            "data": self.data,
            "timestamp": self.timestamp
        }


@dataclass
class WorkflowResult:
    """Result of a workflow execution."""
    workflow_id: str
    status: WorkflowStatus
    steps_completed: int
    total_steps: int
    recovered: bool = False
    recovery_step: Optional[str] = None
    result: Any = None
    error: Optional[str] = None


class CheckpointStore:
    """SQLite-based checkpoint storage."""
    
    def __init__(self, db_path: str = "workflow_checkpoints.db"):
        self.db_path = db_path
        self._init_db()
        # Phase D: Decentralized Storage
        try:
            from storage import ArweaveStorage, KwilStorage
            self.arweave = ArweaveStorage()
            self.kwil = KwilStorage()
            self.decentralized_enabled = True
        except ImportError:
            self.decentralized_enabled = False
    
    def _init_db(self):
        """Initialize the checkpoint database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS checkpoints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workflow_id TEXT NOT NULL,
                step_name TEXT NOT NULL,
                step_index INTEGER NOT NULL,
                data TEXT NOT NULL,
                timestamp REAL NOT NULL,
                arweave_tx TEXT,
                UNIQUE(workflow_id, step_name)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS workflow_state (
                workflow_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                current_step INTEGER DEFAULT 0,
                total_steps INTEGER DEFAULT 0,
                started_at REAL,
                completed_at REAL,
                error TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def save_checkpoint(self, checkpoint: Checkpoint):
        """Save a checkpoint."""
        # 1. Store in decentralized storage (if enabled)
        arweave_tx = None
        if self.decentralized_enabled:
            # We don't block on Arweave upload (it's slow or simulated)
            # ideally we'd queue this, but for PoC we do it or skip
            try:
                # Store permanent memory of this checkpoint
                arweave_tx = self.arweave.store_memory(
                    agent_id="self", # TODO: Get actual ID
                    data=checkpoint.to_dict(),
                    tags={"Type": "Checkpoint", "Workflow": checkpoint.workflow_id}
                )
            except Exception:
                pass

        # 2. Store locally (SQLite)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO checkpoints 
            (workflow_id, step_name, step_index, data, timestamp, arweave_tx)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            checkpoint.workflow_id,
            checkpoint.step_name,
            checkpoint.step_index,
            json.dumps(checkpoint.data),
            checkpoint.timestamp,
            arweave_tx
        ))
        
        conn.commit()
        conn.close()
    
    def get_last_checkpoint(self, workflow_id: str) -> Optional[Checkpoint]:
        """Get the last checkpoint for a workflow."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT workflow_id, step_name, step_index, data, timestamp
            FROM checkpoints
            WHERE workflow_id = ?
            ORDER BY step_index DESC
            LIMIT 1
        ''', (workflow_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return Checkpoint(
                workflow_id=row[0],
                step_name=row[1],
                step_index=row[2],
                data=json.loads(row[3]),
                timestamp=row[4]
            )
        return None
    
    def clear_checkpoints(self, workflow_id: str):
        """Clear all checkpoints for a workflow."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM checkpoints WHERE workflow_id = ?', (workflow_id,))
        cursor.execute('DELETE FROM workflow_state WHERE workflow_id = ?', (workflow_id,))
        conn.commit()
        conn.close()


def checkpoint(step_name: str):
    """Decorator to mark a workflow step with automatic checkpointing."""
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            # Execute the step
            result = func(self, *args, **kwargs)
            
            # Save checkpoint
            if hasattr(self, '_checkpoint_store') and hasattr(self, '_workflow_id'):
                cp = Checkpoint(
                    workflow_id=self._workflow_id,
                    step_name=step_name,
                    step_index=getattr(self, '_current_step', 0),
                    data={"result": result, "args": str(args)}
                )
                self._checkpoint_store.save_checkpoint(cp)
            
            return result
        
        wrapper._checkpoint_step = step_name
        return wrapper
    return decorator


class VamsWorkflow:
    """
    Base class for VAMS workflows with automatic checkpointing.
    
    Example usage:
        class MyWorkflow(VamsWorkflow):
            @checkpoint("gather")
            def step_gather(self):
                return fetch_data()
            
            @checkpoint("process")
            def step_process(self, data):
                return process(data)
    """
    
    def __init__(self, workflow_id: Optional[str] = None):
        self._workflow_id = workflow_id or f"wf_{int(time.time() * 1000)}"
        self._checkpoint_store = CheckpointStore()
        self._current_step = 0
        self._steps: List[str] = []
        self._recovered = False
        self._recovery_step: Optional[str] = None
    
    def _get_steps(self) -> List[str]:
        """Get all checkpoint-decorated methods in order."""
        steps = []
        for name in dir(self):
            if name.startswith('step_'):
                method = getattr(self, name)
                if hasattr(method, '_checkpoint_step'):
                    steps.append(name)
        return sorted(steps)
    
    def recover(self) -> bool:
        """Attempt to recover from last checkpoint."""
        last_cp = self._checkpoint_store.get_last_checkpoint(self._workflow_id)
        if last_cp:
            self._current_step = last_cp.step_index + 1
            self._recovered = True
            self._recovery_step = last_cp.step_name
            return True
        return False


class DemoWorkflow(VamsWorkflow):
    """
    Demo workflow showing DBOS-style crash-proof execution.
    
    Simulates a multi-step agent task with checkpoints.
    """
    
    def __init__(self, workflow_id: Optional[str] = None, simulate_crash: bool = True):
        super().__init__(workflow_id)
        self.simulate_crash = simulate_crash
        self.crash_at_step = 2  # Crash after step 2
        self._results: Dict[str, Any] = {}
    
    @checkpoint("gather_data")
    def step_1_gather(self) -> Dict[str, Any]:
        """Step 1: Gather data from sources."""
        time.sleep(0.5)  # Simulate work
        return {
            "source": "celestia",
            "block": 9628712,
            "timestamp": time.time()
        }
    
    @checkpoint("run_inference")
    def step_2_inference(self, data: Dict) -> Dict[str, Any]:
        """Step 2: Run AI inference on data."""
        time.sleep(0.5)  # Simulate inference
        return {
            "prediction": "bullish",
            "confidence": 0.87,
            "model": "bittensor-sn1"
        }
    
    @checkpoint("execute_action")
    def step_3_execute(self, inference: Dict) -> Dict[str, Any]:
        """Step 3: Execute action based on inference."""
        time.sleep(0.3)  # Simulate execution
        return {
            "action": "log_prediction",
            "status": "success",
            "tx_hash": "0x" + "a" * 64
        }
    
    @checkpoint("report_result")
    def step_4_report(self, action: Dict) -> str:
        """Step 4: Report final result."""
        time.sleep(0.2)
        return f"Workflow complete: {action['status']}"
    
    def run(self, log_fn: Callable = print) -> WorkflowResult:
        """Execute the workflow with checkpointing."""
        steps = [
            ("Gather Data", self.step_1_gather),
            ("Run Inference", self.step_2_inference),
            ("Execute Action", self.step_3_execute),
            ("Report Result", self.step_4_report)
        ]
        
        total_steps = len(steps)
        start_step = 0
        prev_result = None
        
        # Check for recovery
        if self.recover():
            start_step = self._current_step
            log_fn(f"  [RECOVERY] Resuming from step {start_step + 1}: {self._recovery_step}")
            # Load previous result from checkpoint
            last_cp = self._checkpoint_store.get_last_checkpoint(self._workflow_id)
            if last_cp and last_cp.data:
                prev_result = last_cp.data.get("result")
        
        try:
            for i, (name, step_fn) in enumerate(steps):
                if i < start_step:
                    continue
                
                self._current_step = i
                step_num = f"[{i+1}/{total_steps}]"
                
                # Execute step
                log_fn(f"  {step_num} {name}......")
                
                if prev_result is not None:
                    result = step_fn(prev_result)
                else:
                    result = step_fn()
                
                prev_result = result
                log_fn(f"  {step_num} {name}...... [CHECKPOINT]")
                
                # Simulate crash after step 2 (first run only)
                if self.simulate_crash and i == self.crash_at_step - 1 and not self._recovered:
                    log_fn(f"  -- Simulated crash! --")
                    return WorkflowResult(
                        workflow_id=self._workflow_id,
                        status=WorkflowStatus.FAILED,
                        steps_completed=i + 1,
                        total_steps=total_steps,
                        error="Simulated crash for demo"
                    )
            
            # Workflow completed
            self._checkpoint_store.clear_checkpoints(self._workflow_id)
            log_fn(f"  [COMPLETE] Workflow finished successfully!")
            
            return WorkflowResult(
                workflow_id=self._workflow_id,
                status=WorkflowStatus.COMPLETED,
                steps_completed=total_steps,
                total_steps=total_steps,
                recovered=self._recovered,
                recovery_step=self._recovery_step,
                result=prev_result
            )
            
        except Exception as e:
            return WorkflowResult(
                workflow_id=self._workflow_id,
                status=WorkflowStatus.FAILED,
                steps_completed=self._current_step,
                total_steps=total_steps,
                error=str(e)
            )


class LogicLayerMonitor:
    """
    Monitors Layer 3 Logic providers:
    - Kwil (Relational DB)
    - WeaveDB (Permanent Logs)
    - Glacier (Vector DB)
    
    Note: These are decentralized services that typically require SDK integration.
    We check their main sites for reachability.
    """
    
    def __init__(self):
        import requests
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "VAMS-Neuron/0.4",
            "Accept": "text/html,application/json"
        })
        self.timeout = 15
        
        self.providers = {
            "kwil": {
                "endpoint": "https://kwil.com",
                "description": "Relational Backbone - Permissionless SQL"
            },
            "weavedb": {
                "endpoint": "https://weavedb.dev",
                "description": "Permanent Logs - NoSQL on Arweave"
            },
            "glacier": {
                "endpoint": "https://www.glacier.io",
                "description": "Long-Term Memory - Vector DB"
            }
        }
    
    def check_all(self) -> Dict[str, Dict[str, Any]]:
        """Check status of all Logic layer providers."""
        results = {}
        
        for name, config in self.providers.items():
            start = time.time()
            try:
                response = self.session.get(
                    config["endpoint"],
                    timeout=self.timeout,
                    allow_redirects=True
                )
                latency = (time.time() - start) * 1000
                
                # Consider 2xx and 3xx as healthy
                if response.status_code < 400:
                    results[name] = {
                        "status": "healthy",
                        "latency_ms": latency,
                        "description": config["description"]
                    }
                else:
                    results[name] = {
                        "status": "degraded",
                        "latency_ms": latency,
                        "description": config["description"],
                        "error": f"Status {response.status_code}"
                    }
            except Exception as e:
                latency = (time.time() - start) * 1000
                results[name] = {
                    "status": "offline",
                    "latency_ms": latency,
                    "error": str(e)[:50],
                    "description": config["description"]
                }
        
        return results


def run_demo_workflow(log_fn: Callable = print) -> WorkflowResult:
    """Run the demo workflow with crash simulation."""
    workflow_id = f"demo_{int(time.time())}"
    
    log_fn(f"\n[WORKFLOW] Starting: DataPipeline (ID: {workflow_id})")
    log_fn("")
    
    # First run - will crash
    wf1 = DemoWorkflow(workflow_id=workflow_id, simulate_crash=True)
    result1 = wf1.run(log_fn)
    
    if result1.status == WorkflowStatus.FAILED and "Simulated crash" in (result1.error or ""):
        log_fn("")
        log_fn("[WORKFLOW] Restarting after crash...")
        log_fn("")
        
        # Second run - will recover
        wf2 = DemoWorkflow(workflow_id=workflow_id, simulate_crash=False)
        result2 = wf2.run(log_fn)
        return result2
    
    return result1
