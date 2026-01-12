"""
VAMS Neuron Configuration v0.5
==============================
Centralized configuration for the VAMS Neuron client.
"""

import os

# Version
VERSION = "v0.5.0-alpha"

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
# DISPLAY CONFIGURATION
# =============================================================================

BANNER = r"""
 __     ___    __  __ ____    _   _ _____ _   _ ____   ___  _   _ 
 \ \   / / \  |  \/  / ___|  | \ | | ____| | | |  _ \ / _ \| \ | |
  \ \ / / _ \ | |\/| \___ \  |  \| |  _| | | | | |_) | | | |  \| |
   \ V / ___ \| |  | |___) | | |\  | |___| |_| |  _ <| |_| | |\  |
    \_/_/   \_\_|  |_|____/  |_| \_|_____|\___/|_| \_\\___/|_| \_|
                          
        IMMORTAL AGENT  *  FULL 4-LAYER STACK  *  TEE READY
"""
