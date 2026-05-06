"""
VAMS Neuron Configuration v1.0 (Amoy Ready)
===========================================
Centralized configuration for the VAMS Neuron client.
Updated 2026-02-07 - Bound to Polygon Amoy Testnet.
"""

import os

# Version
VERSION = "v1.3.0-oms"

# VAMS Gateway (Optional - for connected mode)
VAMS_GATEWAY = os.getenv("VAMS_GATEWAY", "http://localhost:8000")

# Heartbeat Configuration
HEARTBEAT_INTERVAL = int(os.getenv("HEARTBEAT_INTERVAL", "30"))  # seconds

# Storage Configuration
DATABASE_PATH = os.getenv("VAMS_DB_PATH", "neuron_data.db")
IDENTITY_PATH = os.getenv("VAMS_IDENTITY_PATH", "node_identity.pem")
WORKFLOW_DB_PATH = os.getenv("VAMS_WORKFLOW_DB", "workflow_checkpoints.db")

# Network Configuration
REQUEST_TIMEOUT = 10  # seconds
MAX_RETRY_ATTEMPTS = 3
RETRY_BACKOFF = 2
MOCK_MODE = os.getenv("VAMS_MOCK_MODE", "true").lower() == "true"

# =============================================================================
# LAYER 0: POLYGON AMOY (ECONOMIC LAYER)
# =============================================================================
# The immutable ledger that binds us.

AMOY_CONFIG = {
    "rpc": os.getenv("POLYGON_AMOY_RPC_URL", "https://rpc-amoy.polygon.technology/"),
    "chain_id": 80002,
    "contracts": {
        "token": os.getenv("VAMS_CONTRACT_TOKEN", "0x62a705eD1cAbBBafFCd99e9b2497024031329fd4"),
        "registry": os.getenv("VAMS_CONTRACT_REGISTRY", "0x7e290350448cDC8A22e4cF4Ad377B1E595CDd347"),
        "staking": os.getenv("VAMS_CONTRACT_STAKING", "0x0e6aE5B11b9a73A5671B5F8551c0cF3EB82186C2"),
        "vesting": os.getenv("VAMS_CONTRACT_VESTING", "0x92d20dd7A48268Fef76bA14A4a9b6620d0179209"),
        "timelock": os.getenv("VAMS_CONTRACT_TIMELOCK", "0xabCC69eff15753B547E02AB56FC0aa62765fb768")
    }
}

# =============================================================================
# LAYER 1: DATA AVAILABILITY PROVIDERS
# =============================================================================

DEFAULT_PROVIDER = os.getenv("VAMS_PROVIDER", "celestia")
ENABLE_FAILOVER = os.getenv("VAMS_FAILOVER", "true").lower() == "true"

DA_PROVIDERS = {
    "celestia": {
        "rpc": os.getenv("CELESTIA_RPC", "https://rpc-mocha.pops.one"),
        "network": "mocha-4",
        "description": "Default DA - Data Availability Sampling"
    },
    "eigenda": {
        "rpc": os.getenv("EIGENDA_RPC", "https://holesky.drpc.org"),
        "network": "holesky",
        "description": "High-value enterprise - Ethereum security"
    },
    "near": {
        "rpc": os.getenv("NEAR_RPC", "https://rpc.testnet.near.org"),
        "network": "testnet",
        "description": "High-frequency - Fast finality"
    },
    "avail": {
        "rpc": os.getenv("AVAIL_RPC", "https://avail-turing.api.onfinality.io/public"),
        "network": "turing",
        "description": "ZK/Validium - KZG commitments"
    },
    "iagon": {
        "rpc": os.getenv("IAGON_RPC", "https://api.iagon.com"),
        "network": "cardano-mainnet",
        "description": "Cardano-Native eUTXO Storage"
    }
}

PROVIDER_CONFIG = DA_PROVIDERS

# =============================================================================
# LAYER 2: COMPUTE PROVIDERS
# =============================================================================

COMPUTE_PROVIDERS = {
    "io.net": {
        "endpoint": os.getenv("IONET_API", "https://io.net"),
        "description": "GPU Clusters (H100/A100) for AI inference"
    },
    "akash": {
        "endpoint": os.getenv("AKASH_API", "https://rest.cosmos.directory/akash"),
        "description": "Supercloud (Kubernetes/Docker) for persistent workloads"
    },
    "render": {
        "endpoint": os.getenv("RENDER_API", "https://renderfoundation.com"),
        "description": "Visual AI / GPU Rendering for 3D assets"
    },
    "bittensor": {
        "endpoint": os.getenv("BITTENSOR_API", "https://bittensor.org"),
        "description": "Intelligence-as-a-Service (AI Subnets)"
    },
    "phala_cp": {
        "endpoint": os.getenv("PHALA_CP_API", "https://phala.network"),
        "description": "AI Coprocessor in TEE (Confidential Compute)"
    }
}

# =============================================================================
# LAYER 3: LOGIC PROVIDERS
# =============================================================================

LOGIC_PROVIDERS = {
    "kwil": {
        "endpoint": os.getenv("KWIL_API", "https://kwil.com"),
        "description": "Relational Backbone - Permissionless SQL"
    },
    "weavedb": {
        "endpoint": os.getenv("WEAVEDB_API", "https://weavedb.dev"),
        "description": "Permanent Logs - NoSQL on Arweave"
    },
    "glacier": {
        "endpoint": os.getenv("GLACIER_API", "https://www.glacier.io"),
        "description": "Long-Term Memory - Vector DB"
    }
}

# =============================================================================
# LAYER 4: TRUST PROVIDERS
# =============================================================================

TRUST_PROVIDERS = {
    "phala": {
        "endpoint": os.getenv("PHALA_API", "https://phala.network"),
        "technology": "Intel SGX",
        "description": "Phat Contracts - Private Compute"
    },
    "marlin": {
        "endpoint": os.getenv("MARLIN_API", "https://www.marlin.org"),
        "technology": "AWS Nitro",
        "description": "Oyster - TEE Coprocessors"
    },
    "automata": {
        "endpoint": os.getenv("AUTOMATA_API", "https://1rpc.io/ata"),
        "technology": "Multi-Prover",
        "description": "1RPC - Privacy Relay"
    }
}

# =============================================================================
# LAYER 5: EXECUTION CHAINS (CLR Routing Targets)
# =============================================================================
# These are NOT host domains — VAMS agents are not deployed here.
# The CLR routes signed transactions to these chains when specific
# constraints (formal verification, compliance privacy) are required.

EXECUTION_CHAINS = {
    "cardano": {
        "rpc": os.getenv("CARDANO_RPC", "https://cardano-mainnet.blockfrost.io/api/v0"),
        "chain_type": "eUTXO",
        "consensus": "Ouroboros Praos",
        "finality_ms": 720_000,  # ~12 min (36 slots)
        "formally_verified": True,
        "privacy": "public",
        "bridge": "Rosen Bridge",
        "description": "Formally verified settlement - eUTXO deterministic execution"
    },
    "midnight": {
        "rpc": os.getenv("MIDNIGHT_RPC", "https://midnight.network/api/v0"),
        "chain_type": "Cardano Sidechain",
        "consensus": "Ouroboros (epoch-optimized)",
        "finality_ms": 60_000,   # ~1 min
        "formally_verified": True,
        "privacy": "ZK-SD",      # Zero-Knowledge with Selective Disclosure
        "bridge": "Hyperlane (ZK-ISM)",
        "description": "Compliance-grade privacy - ZK with selective disclosure"
    }
}

# =============================================================================
# CHAIN ORACLE CONFIGURATION
# =============================================================================
# TTL for cached chain metrics (seconds). Set higher to reduce RPC calls.

ORACLE_CACHE_TTL = int(os.getenv("ORACLE_CACHE_TTL", "30"))

# Per-chain RPC endpoints (used by chain_oracle.py)
CHAIN_RPC = {
    "ethereum": os.getenv("ETHEREUM_RPC", "https://ethereum-rpc.publicnode.com"),
    "avalanche": os.getenv("AVALANCHE_RPC", "https://api.avax.network/ext/bc/C/rpc"),
    "solana": os.getenv("SOLANA_RPC", "https://api.mainnet-beta.solana.com"),
    "polygon": os.getenv("POLYGON_RPC", "https://polygon-rpc.com"),
    "arbitrum": os.getenv("ARBITRUM_RPC", "https://arb1.arbitrum.io/rpc"),
    "base": os.getenv("BASE_RPC", "https://mainnet.base.org"),
    "phala": os.getenv("PHALA_RPC", "https://phala.api.onfinality.io/public"),
    "oasis": os.getenv("OASIS_RPC", "https://emerald.oasis.io"),
    "cardano": os.getenv("CARDANO_RPC", "https://cardano-mainnet.blockfrost.io/api/v0"),
    "midnight": os.getenv("MIDNIGHT_RPC", "https://midnight.network/api/v0"),
}

# =============================================================================
# CLR ROUTER CONFIGURATION
# =============================================================================
# Default safety thresholds for the "Hard Filter" stage
CLR_MIN_SECURITY_SCORE = float(os.getenv("CLR_MIN_SECURITY", "0.5"))
CLR_MAX_LATENCY_MS = int(os.getenv("CLR_MAX_LATENCY", "60000")) # 1 min default cap

# Entropy-Greedy Tuning (Soft Filter)
CLR_WEIGHT_LATENCY = float(os.getenv("CLR_WEIGHT_LATENCY", "2.0"))
CLR_WEIGHT_COST = float(os.getenv("CLR_WEIGHT_COST", "1.0"))


# =============================================================================
# x402 PAYMENT PROTOCOL CONFIGURATION
# =============================================================================
PAYMENT_CHANNEL_DURATION = int(os.getenv("PAYMENT_CHANNEL_DURATION", "24")) # Hours
PAYMENT_MIN_DEPOSIT = float(os.getenv("PAYMENT_MIN_DEPOSIT", "100.0")) # VAMS
PAYMENT_DEFAULT_FEE = float(os.getenv("PAYMENT_DEFAULT_FEE", "1.0")) # 1 VAMS per service call

# =============================================================================
# CIRCUIT BREAKER CONFIGURATION (RESILIENCE)
# =============================================================================
BREAKER_PRICE_FLOOR = float(os.getenv("BREAKER_PRICE_FLOOR", "0.50")) # USD
BREAKER_MAX_EXPOSURE = float(os.getenv("BREAKER_MAX_EXPOSURE", "1000.0")) # VAMS
BREAKER_MAX_CONSECUTIVE_FAILURES = int(os.getenv("BREAKER_MAX_FAILURES", "5"))
BREAKER_ORACLE_TIMEOUT_MS = int(os.getenv("BREAKER_ORACLE_TIMEOUT", "60000"))
BREAKER_COOLDOWN_SEC = int(os.getenv("BREAKER_COOLDOWN", "300")) # 5 min auto-reset

# =============================================================================
# AGENTOS COGNITIVE RUNTIME CONFIGURATION
# =============================================================================
# Maps AgentOS preprint concepts onto VAMS infrastructure.
# See docs/team/AGENTOS_INTEGRATION.md for full specification.

# Semantic Checkpoint Manager (CID-based boundary detection)
CID_EPSILON = float(os.getenv("VAMS_CID_EPSILON", "0.15"))           # dD/dt threshold
CID_MIN_INTERVAL = int(os.getenv("VAMS_CID_MIN_INTERVAL", "3"))      # Min steps between checkpoints
CID_MAX_INTERVAL = int(os.getenv("VAMS_CID_MAX_INTERVAL", "50"))     # Max steps (safety fallback)
ENABLE_SEMANTIC_CHECKPOINTS = os.getenv("VAMS_SEMANTIC_CHECKPOINTS", "true").lower() == "true"

# S-MMU Memory Hierarchy
SMMU_L1_CAPACITY = int(os.getenv("VAMS_SMMU_L1_CAPACITY", "128"))    # L1 cache page limit
SMMU_L2_PROVIDER = os.getenv("VAMS_SMMU_L2_PROVIDER", "near")        # Near DA for L2
SMMU_L3_PROVIDER = os.getenv("VAMS_SMMU_L3_PROVIDER", "glacier")     # Glacier for L3
ENABLE_ACCESS_LOG = os.getenv("VAMS_SMMU_ACCESS_LOG", "true").lower() == "true"

# Interrupt Vector Table (x402 Interrupt Handler)
IVT_TIMEOUT_MS = int(os.getenv("VAMS_IVT_TIMEOUT", "30000"))         # HTLC timelock
IVT_MAX_RETRIES = int(os.getenv("VAMS_IVT_MAX_RETRIES", "2"))        # Provider failover attempts
IVT_MOCK_MODE = os.getenv("VAMS_IVT_MOCK", "true").lower() == "true" # Mock x402 payments

# Cognitive Drift Detection & Sync Pulses  
DRIFT_THETA = float(os.getenv("VAMS_DRIFT_THETA", "0.3"))            # CSP trigger threshold
DRIFT_GAMMA = float(os.getenv("VAMS_DRIFT_GAMMA", "1.5"))            # Oracle reputation exponent
DRIFT_MAX_ORACLE_INFLUENCE = float(os.getenv("VAMS_DRIFT_MAX_INFLUENCE", "0.15"))  # 15% cap
DRIFT_MIN_ORACLE_PARTICIPANTS = int(os.getenv("VAMS_DRIFT_MIN_ORACLES", "3"))
DRIFT_REPUTATION_DECAY = float(os.getenv("VAMS_DRIFT_REP_DECAY", "0.05"))  # 5% per epoch

# =============================================================================
# CLR v3.1 ENHANCED ROUTING CONFIGURATION
# =============================================================================
# Architecture Section 14, 16, 20.4.3, 20.5

# Routing Thresholds
CLR_SECURITY_THRESHOLD = int(os.getenv("VAMS_CLR_SECURITY_THRESHOLD", "10000"))   # USD
CLR_VELOCITY_THRESHOLD = int(os.getenv("VAMS_CLR_VELOCITY_THRESHOLD", "1000"))    # ms

# Bridge Executor (Section 16, 20.5)
BRIDGE_PRIMARY_TIMEOUT_MS = int(os.getenv("VAMS_BRIDGE_PRIMARY_TIMEOUT", "30000"))
BRIDGE_SECONDARY_TIMEOUT_MS = int(os.getenv("VAMS_BRIDGE_SECONDARY_TIMEOUT", "60000"))

# MEV Protection (Section 20.4.3)
MEV_BATCH_WINDOW_MS = int(os.getenv("VAMS_MEV_BATCH_WINDOW", "500"))              # Batch auction window

# =============================================================================
# POLYGON OPEN MONEY STACK (OMS) CONFIGURATION
# =============================================================================
# Architecture v0.6.0 - Institutional Identity & Stablecoin Payments

OMS_IDENTITY_API = os.getenv("OMS_IDENTITY_API", "https://api.oms.polygon.technology/v1/identity")
OMS_API_KEY = os.getenv("OMS_API_KEY", "")
SEQUENCE_PROJECT_KEY = os.getenv("SEQUENCE_PROJECT_KEY", "")

# Enterprise RPC (Section 2.1)
VAMS_ENTERPRISE_RPC = os.getenv("VAMS_ENTERPRISE_RPC", AMOY_CONFIG["rpc"])
VAMS_RPC_FAILOVER_TIMEOUT = int(os.getenv("VAMS_RPC_FAILOVER_TIMEOUT", "5000")) # ms

# Stablecoin Payouts (Section 2.3)
STABLECOIN_CONFIG = {
    "USDC": os.getenv("VAMS_USDC_ADDRESS", "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"), # Polygon USDC
    "USDT": os.getenv("VAMS_USDT_ADDRESS", "0xc2132D05D31c914a87C6611C10748AEb04B58e8F")  # Polygon USDT
}

# =============================================================================

BANNER = r"""
 __     ___    __  __ ____    _   _ _____ _   _ ____   ___  _   _ 
 \ \   / / \  |  \/  / ___|  | \ | | ____| | | |  _ \ / _ \| \ | |
  \ \ / / _ \ | |\/| \___ \  |  \| |  _| | | | | |_) | | | |  \| |
   \ V / ___ \| |  | |___) | | |\  | |___| |_| |  _ <| |_| | |\  |
    \_/_/   \_\_|  |_|____/  |_| \_|_____|\___/|_| \_\\___/|_| \_|
                          
        IMMORTAL AGENT  *  AMOY LIVE  *  SURVIVAL NATIVE
"""
