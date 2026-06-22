"""
VAMS Neuron - Workflow Engine (Layer 3: Logic)
==============================================
Real DBOS durable execution — replaces the hand-rolled SQLite checkpoint
engine with the official DBOS Python SDK.

Architecture
------------
Workflows call Steps. Steps are where all I/O and non-determinism lives.

  @DBOS.step()   — executes exactly once; retried on transient failure
  @DBOS.workflow() — deterministic orchestration; resumes from the last
                     completed step after any crash or restart

Guarantees (provided by DBOS, not by us):
  1. Workflows always run to completion.
  2. Steps are never re-executed after they complete (exactly-once).
  3. All state is stored in Postgres — process restarts are transparent.

Layer 3 providers (health check only — no workflow dependency):
  Kwil · WeaveDB · Glacier
"""

import time
import logging
import asyncio
from typing import Dict, Any, Callable

from dbos import DBOS, SetWorkflowID

logger = logging.getLogger("vams.workflows")

try:
    from sdk.semantic_mmu import SemanticMMU, MemoryTier
    from intelligence.world_model import ProPlayWorldModel
except ImportError:
    try:
        from neuron.sdk.semantic_mmu import SemanticMMU, MemoryTier
        from neuron.intelligence.world_model import ProPlayWorldModel
    except ImportError:
        SemanticMMU = None
        MemoryTier = None
        ProPlayWorldModel = None


# ═══════════════════════════════════════════════════════════════════════════════
# STEPS — non-deterministic / side-effectful operations
# Every external call (chain RPC, inference API, contract write) must be a step.
# DBOS records the return value after first success; on replay it skips the I/O
# and returns the recorded value directly.
# ═══════════════════════════════════════════════════════════════════════════════

@DBOS.step()
async def step_gather_data() -> Dict[str, Any]:
    """
    Step 1: Fetch latest block data from Celestia DA layer.
    Replace the sleep + mock dict with a real CelestiaDA().get_latest_block() call.
    """
    await asyncio.sleep(0)  # yield — replace with: from sdk.celestia import CelestiaDA
    logger.debug("step_gather_data executing")
    return {
        "source": "celestia",
        "block": 9_628_712,
        "timestamp": time.time(),
    }


@DBOS.step()
async def step_run_inference(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Step 2: Run AI inference via Bittensor subnet 1.
    Replace with: from sdk.bittensor_subnet import BittensorSubnet
    """
    await asyncio.sleep(0)
    logger.debug("step_run_inference executing for block %s", data.get("block"))
    return {
        "prediction": "bullish",
        "confidence": 0.87,
        "model": "bittensor-sn1",
    }


@DBOS.step()
async def step_execute_action(inference: Dict[str, Any]) -> Dict[str, Any]:
    """
    Step 3: Execute on-chain action based on inference result.
    Replace with: actual contract call via web3 / bridge_executor.
    """
    await asyncio.sleep(0)
    logger.debug("step_execute_action: prediction=%s", inference.get("prediction"))
    return {
        "action": "log_prediction",
        "status": "success",
        "tx_hash": "0x" + "a" * 64,
    }


@DBOS.step()
async def step_report_result(action: Dict[str, Any]) -> str:
    """
    Step 4: Emit final telemetry / result string.
    Replace with: WeaveDB log, Arweave anchor, or gateway POST.
    """
    await asyncio.sleep(0)
    result = f"Workflow complete: {action['status']}"
    logger.info("step_report_result: %s", result)
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# WORKFLOW — deterministic orchestration only
# No I/O, no time.time(), no random, no global mutation allowed here.
# All non-determinism must live inside @DBOS.step() functions.
# ═══════════════════════════════════════════════════════════════════════════════

@DBOS.workflow()
async def vams_data_pipeline() -> str:
    """
    VAMS four-step data pipeline with real DBOS durability.

    If the process crashes between any two steps, DBOS will resume from
    the last completed step on restart — no data is re-fetched or re-sent.
    """
    data      = await step_gather_data()
    inference = await step_run_inference(data)
    action    = await step_execute_action(inference)
    result    = await step_report_result(action)
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def run_demo_workflow(log_fn: Callable[[str], None] = print) -> str:
    """
    Launch the VAMS data pipeline workflow and block until complete.

    Uses SetWorkflowID for idempotency: calling run_demo_workflow() twice
    with the same workflow ID executes the pipeline exactly once, regardless
    of crashes or retries.

    Args:
        log_fn: Optional callable for progress messages (default: print).
                Kept for backward-compatibility with neuron.py callers.

    Returns:
        The result string from the final pipeline step.
    """
    wf_id = f"vams-pipeline-{int(time.time())}"
    log_fn(f"[WORKFLOW] Starting: DataPipeline (ID: {wf_id})")
    log_fn("[WORKFLOW] DBOS durability active — crash-safe execution")

    # 1. ProPlay Guidance integration
    if ProPlayWorldModel is not None:
        try:
            import os
            os.makedirs(".data/memory", exist_ok=True)
            model = ProPlayWorldModel(filepath=".data/memory/workflow_procedures.json")
            
            # Setup some default workflow nodes if empty
            model.add_procedure("initiate", "Initiate pipeline")
            model.add_procedure("gather_data", "Fetch DA blocks")
            model.add_procedure("run_inference", "Query Bittensor subnet")
            model.add_procedure("execute_action", "Settle bridge transaction")
            
            guidance = model.get_soft_guidance("DeFi cross-chain data pipeline execution")
            log_fn(f"[COGNITIVE] ProPlay Soft Guidance: {guidance}")
        except Exception as e:
            log_fn(f"[COGNITIVE] ProPlay failed to load/guide: {e}")
    else:
        log_fn("[COGNITIVE] ProPlayWorldModel not imported")

    async def _run() -> str:
        with SetWorkflowID(wf_id):
            return await vams_data_pipeline()

    result = asyncio.run(_run())
    log_fn(f"[WORKFLOW] Complete: {result}")

    # 2. S-MMU HORMA & HIPIF integration
    if SemanticMMU is not None and MemoryTier is not None:
        try:
            mmu = SemanticMMU()
            import os
            
            # Write a raw trace log simulating step execution
            trace_path = f".data/memory/raw_trace_{wf_id}.log"
            os.makedirs(os.path.dirname(trace_path), exist_ok=True)
            with open(trace_path, "w") as f:
                f.write(
                    f"Workflow: {wf_id}\n"
                    "Step 1: step_gather_data resolved block 9628712 on Celestia\n"
                    "Step 2: step_run_inference output bullish prediction\n"
                    "Step 3: step_execute_action completed bridge tx 0xabcdef0123456789\n"
                    "Status: success completed"
                )
            
            log_fn(f"[COGNITIVE] S-MMU: Raw trace logged to {trace_path}")
            
            # Run HIPIF information folding at subtask boundary
            folded = mmu.fold_completed_subtask(wf_id, trace_path)
            log_fn("[COGNITIVE] S-MMU: HIPIF folding complete, raw trace cleaned up.")
            log_fn(f"[COGNITIVE] S-MMU: Folded block stored in L3 HORMA:\n{folded}")
            
            # Evaluate memory value V(m) for the final result
            v_m = mmu.evaluate_memory_value(result)
            log_fn(f"[COGNITIVE] S-MMU: V(m) expected utility score for workflow result: {v_m}")
            
            # Log EvoMem Patch tracking state change
            patch_success = mmu.apply_memory_patch(
                f"workflows/data_pipeline/{wf_id}",
                {
                    "previous_state": "idle",
                    "new_state": result,
                    "rationale_for_change": "vams demo pipeline execution completed successfully",
                    "supporting_evidence": "block_height=9628712 tx_hash=0xabcdef0123456789"
                }
            )
            if patch_success:
                log_fn("[COGNITIVE] S-MMU: EvoMem append-only state patch recorded.")
            
            # Promote to L3 / local filesystem
            mmu.store(f"workflows/data_pipeline/{wf_id}/result", {"status": result, "v_m": v_m}, tier=MemoryTier.L3_STORAGE)
            log_fn(f"[COGNITIVE] S-MMU: Page workflows/data_pipeline/{wf_id}/result anchored to L3 HORMA FS.")
            
            # Update ProPlay transition trajectory with high reward
            if ProPlayWorldModel is not None:
                model.record_transition("initiate", "gather_data", reward=1.0, task_description="DeFi cross-chain data pipeline execution")
                model.record_transition("gather_data", "run_inference", reward=1.0, task_description="DeFi cross-chain data pipeline execution")
                model.record_transition("run_inference", "execute_action", reward=1.0, task_description="DeFi cross-chain data pipeline execution")
                model.record_transition("execute_action", "complete", reward=1.0, task_description="DeFi cross-chain data pipeline execution")
                model.save_graph()
                log_fn("[COGNITIVE] ProPlay: Recorded successful workflow procedures to transition graph.")
        except Exception as e:
            log_fn(f"[COGNITIVE] S-MMU/ProPlay logging failed: {e}")
    else:
        log_fn("[COGNITIVE] SemanticMMU not imported")

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# LOGIC LAYER HEALTH MONITOR (unchanged — no DBOS dependency)
# ═══════════════════════════════════════════════════════════════════════════════

class LogicLayerMonitor:
    """
    Checks reachability of Layer 3 logic providers:
      Kwil (Relational DB) · WeaveDB (Permanent Logs) · Glacier (Vector DB)

    These are decentralised services accessed via HTTP; this class performs
    a simple GET to verify the endpoint is up. It has no DBOS dependency.
    """

    def __init__(self):
        import requests
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "VAMS-Neuron/0.5",
            "Accept": "text/html,application/json",
        })
        self.timeout = 15
        self.providers = {
            "kwil": {
                "endpoint": "https://kwil.com",
                "description": "Relational Backbone - Permissionless SQL",
            },
            "weavedb": {
                "endpoint": "https://weavedb.dev",
                "description": "Permanent Logs - NoSQL on Arweave",
            },
            "glacier": {
                "endpoint": "https://www.glacier.io",
                "description": "Long-Term Memory - Vector DB",
            },
        }

    def check_all(self) -> Dict[str, Dict[str, Any]]:
        """Check reachability of all Layer 3 providers."""
        results: Dict[str, Dict[str, Any]] = {}
        for name, cfg in self.providers.items():
            start = time.time()
            try:
                resp = self.session.get(cfg["endpoint"], timeout=self.timeout, allow_redirects=True)
                latency = (time.time() - start) * 1000
                status = "healthy" if resp.status_code < 400 else "degraded"
                results[name] = {
                    "status": status,
                    "latency_ms": latency,
                    "description": cfg["description"],
                }
                if status == "degraded":
                    results[name]["error"] = f"HTTP {resp.status_code}"
            except Exception as exc:
                latency = (time.time() - start) * 1000
                results[name] = {
                    "status": "offline",
                    "latency_ms": latency,
                    "description": cfg["description"],
                    "error": str(exc)[:60],
                }
        return results
