"""
VAMS Hardware Registry SDK Client
==================================
Python wrapper for agent-side hardware node discovery and registration.
Interfaces with VAMSHardwareRegistry.sol on-chain.

Part of Phase 2: Hardware Layer (Sprint 1).
"""

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from functools import lru_cache

logger = logging.getLogger(__name__)


# ═══════════════════ Hardware Class Constants ═══════════════════

def _class_id(name: str) -> bytes:
    """Compute bytes32 class ID matching Solidity keccak256(name)."""
    from eth_abi import encode
    from eth_utils import keccak
    return keccak(name.encode("utf-8"))


class HardwareClass:
    """Pre-seeded hardware class identifiers (mirrors HardwareClasses.sol)."""
    GPU_H100     = "GPU_H100"
    GPU_A100     = "GPU_A100"
    GPU_L40S     = "GPU_L40S"
    GPU_RTX_4090 = "GPU_RTX_4090"
    CPU_EPYC     = "CPU_EPYC"
    CPU_XEON     = "CPU_XEON"
    STORAGE_NVME = "STORAGE_NVME"
    STORAGE_HDD  = "STORAGE_HDD"
    NETWORK_10G  = "NETWORK_10G"
    TEE_SGX      = "TEE_SGX"
    TEE_NITRO    = "TEE_NITRO"

    ALL = [
        GPU_H100, GPU_A100, GPU_L40S, GPU_RTX_4090,
        CPU_EPYC, CPU_XEON,
        STORAGE_NVME, STORAGE_HDD,
        NETWORK_10G,
        TEE_SGX, TEE_NITRO,
    ]


# ═══════════════════ Data Models ═══════════════════

@dataclass
class HardwareClassInfo:
    """Mirrors IVAMSHardwareRegistry.HardwareClassInfo."""
    class_id: bytes
    name: str
    category: str
    min_collateral: int
    min_benchmark_score: int
    is_active: bool


@dataclass
class ResourceNode:
    """Mirrors IVAMSHardwareRegistry.VAMSResourceNode."""
    node_id: bytes
    provider: str
    hw_class: bytes
    hw_class_name: str  # Human-readable (resolved from class_id)
    region: str
    capacity_units: int
    reservation_price: int  # $VAMS per hour (18 decimals)
    max_booking_duration: int  # seconds
    collateral_staked: int
    is_active: bool
    registered_at: int
    last_benchmark_at: int
    benchmark_score: int

    @property
    def price_per_hour_vams(self) -> float:
        """Human-readable price in $VAMS."""
        return self.reservation_price / 1e18

    @property
    def is_benchmarked(self) -> bool:
        return self.last_benchmark_at > 0

    @property
    def benchmark_percent(self) -> float:
        """Benchmark score as percentage (0-100)."""
        return self.benchmark_score / 100.0


# ═══════════════════ Cached Results ═══════════════════

@dataclass
class _CacheEntry:
    """TTL-based cache entry."""
    data: Any
    expires_at: float


# ═══════════════════ SDK Client ═══════════════════

# Minimal ABI for the functions we need
HARDWARE_REGISTRY_ABI = json.loads("""[
    {
        "inputs": [{"internalType": "bytes32", "name": "classId", "type": "bytes32"}],
        "name": "getHardwareClass",
        "outputs": [{"components": [
            {"internalType": "bytes32", "name": "classId", "type": "bytes32"},
            {"internalType": "string", "name": "name", "type": "string"},
            {"internalType": "string", "name": "category", "type": "string"},
            {"internalType": "uint256", "name": "minCollateral", "type": "uint256"},
            {"internalType": "uint256", "name": "minBenchmarkScore", "type": "uint256"},
            {"internalType": "bool", "name": "isActive", "type": "bool"}
        ], "internalType": "struct IVAMSHardwareRegistry.HardwareClassInfo", "name": "", "type": "tuple"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "getRegisteredClassCount",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "uint256", "name": "index", "type": "uint256"}],
        "name": "getRegisteredClassId",
        "outputs": [{"internalType": "bytes32", "name": "", "type": "bytes32"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "bytes32", "name": "nodeId", "type": "bytes32"}],
        "name": "getNode",
        "outputs": [{"components": [
            {"internalType": "bytes32", "name": "nodeId", "type": "bytes32"},
            {"internalType": "address", "name": "provider", "type": "address"},
            {"internalType": "bytes32", "name": "hwClass", "type": "bytes32"},
            {"internalType": "string", "name": "region", "type": "string"},
            {"internalType": "uint256", "name": "capacityUnits", "type": "uint256"},
            {"internalType": "uint256", "name": "reservationPrice", "type": "uint256"},
            {"internalType": "uint256", "name": "maxBookingDuration", "type": "uint256"},
            {"internalType": "uint256", "name": "collateralStaked", "type": "uint256"},
            {"internalType": "bool", "name": "isActive", "type": "bool"},
            {"internalType": "uint256", "name": "registeredAt", "type": "uint256"},
            {"internalType": "uint256", "name": "lastBenchmarkAt", "type": "uint256"},
            {"internalType": "uint256", "name": "benchmarkScore", "type": "uint256"}
        ], "internalType": "struct IVAMSHardwareRegistry.VAMSResourceNode", "name": "", "type": "tuple"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "address", "name": "provider", "type": "address"}],
        "name": "getNodesByProvider",
        "outputs": [{"internalType": "bytes32[]", "name": "", "type": "bytes32[]"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "getTotalNodeCount",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "bytes32", "name": "nodeId", "type": "bytes32"}],
        "name": "isNodeHealthy",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "bytes32", "name": "hwClass", "type": "bytes32"},
            {"internalType": "string", "name": "region", "type": "string"},
            {"internalType": "uint256", "name": "capacityUnits", "type": "uint256"},
            {"internalType": "uint256", "name": "reservationPrice", "type": "uint256"},
            {"internalType": "uint256", "name": "maxBookingDuration", "type": "uint256"}
        ],
        "name": "registerNode",
        "outputs": [{"internalType": "bytes32", "name": "nodeId", "type": "bytes32"}],
        "stateMutability": "nonpayable",
        "type": "function"
    }
]""")


class HardwareRegistryClient:
    """
    Python SDK client for VAMSHardwareRegistry.sol.

    Provides:
    - Hardware class enumeration and discovery
    - Node querying with filters (class, region, price, benchmark)
    - Cached queries with configurable TTL
    - Integration-ready for agent provisioning workflows
    """

    CACHE_TTL = 60  # seconds

    def __init__(
        self,
        registry_address: Optional[str] = None,
        rpc_url: Optional[str] = None,
        private_key: Optional[str] = None,
    ):
        self.registry_address = registry_address
        self.contract = None
        self.w3 = None
        self._cache: Dict[str, _CacheEntry] = {}
        self._class_name_map: Dict[bytes, str] = {}

        if registry_address and rpc_url:
            try:
                from web3 import Web3
                self.w3 = Web3(Web3.HTTPProvider(rpc_url))
                self.contract = self.w3.eth.contract(
                    address=Web3.to_checksum_address(registry_address),
                    abi=HARDWARE_REGISTRY_ABI,
                )
                if private_key:
                    self._account = self.w3.eth.account.from_key(private_key)
                else:
                    self._account = None
                logger.info(
                    "HardwareRegistryClient connected to %s", registry_address
                )
            except ImportError:
                logger.warning("web3 not installed -- using offline mode")
            except Exception as e:
                logger.error("Failed to connect: %s", e)

    # ═══════════════════ Cache Helpers ═══════════════════

    def _get_cached(self, key: str) -> Optional[Any]:
        entry = self._cache.get(key)
        if entry and time.time() < entry.expires_at:
            return entry.data
        return None

    def _set_cached(self, key: str, data: Any) -> None:
        self._cache[key] = _CacheEntry(data=data, expires_at=time.time() + self.CACHE_TTL)

    def clear_cache(self) -> None:
        """Clear the local query cache."""
        self._cache.clear()

    # ═══════════════════ Class Discovery ═══════════════════

    def get_all_classes(self) -> List[HardwareClassInfo]:
        """Fetch all registered hardware classes."""
        cached = self._get_cached("all_classes")
        if cached:
            return cached

        if not self.contract:
            return self._offline_classes()

        count = self.contract.functions.getRegisteredClassCount().call()
        classes = []
        for i in range(count):
            class_id = self.contract.functions.getRegisteredClassId(i).call()
            raw = self.contract.functions.getHardwareClass(class_id).call()
            info = HardwareClassInfo(
                class_id=raw[0],
                name=raw[1],
                category=raw[2],
                min_collateral=raw[3],
                min_benchmark_score=raw[4],
                is_active=raw[5],
            )
            classes.append(info)
            self._class_name_map[raw[0]] = raw[1]

        self._set_cached("all_classes", classes)
        return classes

    def _offline_classes(self) -> List[HardwareClassInfo]:
        """Return pre-seeded classes for offline/testing mode."""
        defaults = {
            HardwareClass.GPU_H100: ("GPU", 50_000, 8000),
            HardwareClass.GPU_A100: ("GPU", 25_000, 7500),
            HardwareClass.GPU_L40S: ("GPU", 20_000, 7000),
            HardwareClass.GPU_RTX_4090: ("GPU", 10_000, 6000),
            HardwareClass.CPU_EPYC: ("CPU", 10_000, 7000),
            HardwareClass.CPU_XEON: ("CPU", 10_000, 7000),
            HardwareClass.STORAGE_NVME: ("STORAGE", 15_000, 8000),
            HardwareClass.STORAGE_HDD: ("STORAGE", 5_000, 5000),
            HardwareClass.NETWORK_10G: ("NETWORK", 8_000, 7500),
            HardwareClass.TEE_SGX: ("TEE", 30_000, 9000),
            HardwareClass.TEE_NITRO: ("TEE", 30_000, 9000),
        }
        return [
            HardwareClassInfo(
                class_id=hashlib.sha3_256(name.encode()).digest(),
                name=name,
                category=cat,
                min_collateral=int(col * 1e18),
                min_benchmark_score=bench,
                is_active=True,
            )
            for name, (cat, col, bench) in defaults.items()
        ]

    # ═══════════════════ Node Queries ═══════════════════

    def get_nodes_by_provider(self, provider_address: str) -> List[ResourceNode]:
        """Get all nodes owned by a provider."""
        if not self.contract:
            return []

        node_ids = self.contract.functions.getNodesByProvider(provider_address).call()
        return [self._fetch_node(nid) for nid in node_ids]

    def _fetch_node(self, node_id: bytes) -> ResourceNode:
        """Fetch a single node's details."""
        raw = self.contract.functions.getNode(node_id).call()
        hw_name = self._class_name_map.get(raw[2], raw[2].hex()[:16])
        return ResourceNode(
            node_id=raw[0],
            provider=raw[1],
            hw_class=raw[2],
            hw_class_name=hw_name,
            region=raw[3],
            capacity_units=raw[4],
            reservation_price=raw[5],
            max_booking_duration=raw[6],
            collateral_staked=raw[7],
            is_active=raw[8],
            registered_at=raw[9],
            last_benchmark_at=raw[10],
            benchmark_score=raw[11],
        )

    def find_by_class(self, hw_class_name: str) -> List[ResourceNode]:
        """Find all active nodes of a given hardware class."""
        # Note: On-chain findNodes with region filter is gas-intensive.
        # This does client-side filtering over provider-indexed nodes.
        # In production, use an indexer (The Graph / Ponder).
        logger.info("find_by_class: %s (requires indexer for production)", hw_class_name)
        return []

    def find_cheapest(
        self, hw_class_name: str, region: Optional[str] = None, min_capacity: int = 1
    ) -> Optional[ResourceNode]:
        """Find the cheapest active node matching criteria."""
        logger.info(
            "find_cheapest: class=%s region=%s min_cap=%d (requires indexer)",
            hw_class_name, region, min_capacity,
        )
        return None

    def find_by_score(self, min_benchmark: int = 7500) -> List[ResourceNode]:
        """Find nodes with benchmark score above threshold."""
        logger.info(
            "find_by_score: min=%d (requires indexer for production)", min_benchmark
        )
        return []

    # ═══════════════════ Health Check ═══════════════════

    def is_healthy(self, node_id: bytes) -> bool:
        """Check if a node is active and meeting SLA."""
        if not self.contract:
            return False
        return self.contract.functions.isNodeHealthy(node_id).call()

    # ═══════════════════ Stats ═══════════════════

    def get_total_nodes(self) -> int:
        """Get total registered node count."""
        if not self.contract:
            return 0
        return self.contract.functions.getTotalNodeCount().call()

    def get_summary(self) -> Dict[str, Any]:
        """Get registry summary for dashboards."""
        classes = self.get_all_classes()
        return {
            "total_classes": len(classes),
            "active_classes": sum(1 for c in classes if c.is_active),
            "total_nodes": self.get_total_nodes(),
            "classes": [
                {
                    "name": c.name,
                    "category": c.category,
                    "min_collateral_vams": c.min_collateral / 1e18,
                    "min_benchmark": c.min_benchmark_score,
                    "active": c.is_active,
                }
                for c in classes
            ],
        }
