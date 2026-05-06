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

    async def _run() -> str:
        with SetWorkflowID(wf_id):
            return await vams_data_pipeline()

    result = asyncio.run(_run())
    log_fn(f"[WORKFLOW] Complete: {result}")
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
