"""
VAMS Macro Service Blocks
============================
Pre-defined composite service packages that bundle multiple
individual service blocks into turnkey infrastructure solutions.

Each macro block is a dictionary:
    - name: Macro block identifier
    - description: What the macro provides
    - blocks: List of constituent service block names
    - category: Top-level category

Architecture Reference:
    - ICN Gap #6: Service Blocks
    - VAMS Phase 3, Sprint 8
"""

from __future__ import annotations

from typing import Dict, List


# ═══════════════════════════════════════════════════════════════
# Macro Block Definitions
# ═══════════════════════════════════════════════════════════════

MACRO_BLOCKS: Dict[str, Dict] = {
    "AI_AGENT_STARTER_PACK": {
        "name": "AI_AGENT_STARTER_PACK",
        "description": (
            "Complete AI agent infrastructure: Llama inference engine, "
            "vector database for RAG, TEE privacy wrapper, Celestia DA "
            "audit trail, and x402 micropayment integration."
        ),
        "blocks": [
            "llama_inference",
            "vector_db",
            "tee_wrapper",
            "celestia_audit",
            "x402_payments",
        ],
        "category": "AI",
    },
    "DEFI_ARBITRAGE_SUITE": {
        "name": "DEFI_ARBITRAGE_SUITE",
        "description": (
            "High-frequency DeFi arbitrage stack: ultra-low-latency compute, "
            "MEV protection module, and multi-chain bridge relay."
        ),
        "blocks": [
            "high_speed_compute",
            "mev_protection",
            "multi_chain_bridge",
        ],
        "category": "DEFI",
    },
    "DATA_PIPELINE_STANDARD": {
        "name": "DATA_PIPELINE_STANDARD",
        "description": (
            "Standard data pipeline: large NVMe storage cluster, "
            "CPU compute for ETL processing, and high-bandwidth networking."
        ),
        "blocks": [
            "storage_cluster_block",
            "cpu_compute_block",
        ],
        "category": "DATA",
    },
    "CONFIDENTIAL_AI_SUITE": {
        "name": "CONFIDENTIAL_AI_SUITE",
        "description": (
            "Privacy-first AI stack: Llama inference in a TEE enclave, "
            "encrypted vector store, and auditable DA trail."
        ),
        "blocks": [
            "llama_inference",
            "tee_wrapper",
            "vector_db",
            "celestia_audit",
        ],
        "category": "AI",
    },
}


# ═══════════════════════════════════════════════════════════════
# Lookup Functions
# ═══════════════════════════════════════════════════════════════

def get_macro(name: str) -> Dict:
    """
    Look up a macro service block by name.

    Returns:
        Dict with macro metadata and constituent block names

    Raises:
        KeyError: If macro not found
    """
    macro = MACRO_BLOCKS.get(name)
    if macro is None:
        raise KeyError(
            f"Unknown macro block '{name}'. "
            f"Available: {list(MACRO_BLOCKS.keys())}"
        )
    return macro


def list_macros() -> List[Dict]:
    """List all macro blocks with summaries."""
    return [
        {
            "name": m["name"],
            "category": m["category"],
            "block_count": len(m["blocks"]),
            "blocks": m["blocks"],
            "description": m["description"][:100] + "..." if len(m["description"]) > 100 else m["description"],
        }
        for m in MACRO_BLOCKS.values()
    ]
