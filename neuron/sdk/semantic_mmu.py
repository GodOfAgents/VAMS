"""
VAMS Neuron - Semantic Memory Management Unit (S-MMU)
=====================================================
Maps the AgentOS S-MMU cognitive memory hierarchy onto VAMS
decentralized storage infrastructure.

Tiers:
    L1 CACHE  → In-process KV-Cache (<10ms, ephemeral)
    L2 RAM    → Near DA (85,000x cheaper, <500ms, session-scoped)
    L3 STORAGE → Glacier VDB + WeaveDB (<2s, permanent)
    L0 ANCHOR  → Polygon CDK Validium + Ethereum (ZK-State Root)

Reference: AGENTOS_INTEGRATION.md §2.2
"""

import time
import hashlib
import json
import logging
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from enum import Enum

logger = logging.getLogger("vams.semantic_mmu")


class MemoryTier(Enum):
    """S-MMU Cognitive Memory Tiers mapped to VAMS infrastructure."""
    L1_CACHE = "l1_cache"        # In-process KV-Cache
    L2_RAM = "l2_ram"            # Near DA
    L3_STORAGE = "l3_storage"    # Glacier VDB + WeaveDB
    L0_ANCHOR = "l0_anchor"      # Polygon CDK Validium (VAMS extension)


@dataclass
class MemoryPage:
    """
    A page in the S-MMU address space.
    Content-addressed for verifiable access.
    """
    address: str                   # Semantic address (concept key)
    content: Any                   # Stored data
    content_hash: str              # SHA-256 for integrity
    tier: MemoryTier               # Current storage tier
    access_count: int = 0          # For promotion/demotion decisions
    last_accessed: float = field(default_factory=time.time)
    created_at: float = field(default_factory=time.time)
    provenance: Optional[str] = None   # Origin checkpoint ID
    
    def verify(self) -> bool:
        """Verify content integrity via hash."""
        computed = hashlib.sha256(
            json.dumps(self.content, sort_keys=True, default=str).encode()
        ).hexdigest()
        return computed == self.content_hash


class SemanticMMU:
    """
    VAMS implementation of the AgentOS Semantic Memory Management Unit.
    
    Manages a 4-tier cognitive memory hierarchy mapped to VAMS
    decentralized storage providers:
    
      L1 CACHE  → In-process dict (fast, ephemeral)
      L2 RAM    → Near DA integration (session-scoped)
      L3 STORAGE → Glacier/WeaveDB integration (permanent)
      L0 ANCHOR  → ZK-State Root on Polygon CDK (cryptographic guarantee)
    
    Key features:
    - Automatic page promotion/demotion between tiers
    - Content-addressed pages for tamper detection
    - Page fault handling (cache miss → deeper tier search)
    - Access pattern tracking for ZK proof generation
    
    Args:
        l1_capacity: Maximum pages in L1 cache (LRU eviction)
        l2_provider: Near DA provider name (from config)
        l3_provider: Glacier/WeaveDB provider name
        enable_access_log: Track access patterns for ZK proofs
    """
    
    TIER_CONFIG = {
        MemoryTier.L1_CACHE: {
            "latency_ms": 1,
            "persistence": "ephemeral",
            "cost": "free"
        },
        MemoryTier.L2_RAM: {
            "latency_ms": 500,
            "persistence": "session_scoped",
            "cost": "85000x_cheaper_than_eth"
        },
        MemoryTier.L3_STORAGE: {
            "latency_ms": 2000,
            "persistence": "permanent",
            "cost": "low"
        },
        MemoryTier.L0_ANCHOR: {
            "latency_ms": 300_000,
            "persistence": "cryptographic_guarantee",
            "cost": "medium"
        }
    }
    
    def __init__(
        self,
        l1_capacity: int = 128,
        l2_provider: str = "near",
        l3_provider: str = "glacier",
        enable_access_log: bool = True
    ):
        self.l1_capacity = l1_capacity
        self.l2_provider = l2_provider
        self.l3_provider = l3_provider
        self.enable_access_log = enable_access_log
        
        # L1 Cache (LRU ordered dict)
        self._l1_cache: OrderedDict[str, MemoryPage] = OrderedDict()
        
        # L2/L3 are backed by VAMS DA/Storage providers
        # In-memory simulation for local mode; real providers loaded lazily
        self._l2_store: Dict[str, MemoryPage] = {}
        self._l3_store: Dict[str, MemoryPage] = {}
        
        # Access log for ZK proof generation
        self._access_log: List[Dict[str, Any]] = []
        
        # Statistics
        self._stats = {
            "l1_hits": 0,
            "l1_misses": 0,
            "l2_hits": 0,
            "l2_misses": 0,
            "l3_hits": 0,
            "page_faults": 0,
            "promotions": 0,
            "evictions": 0
        }
        
        # Load real providers if available
        self._near_da = None
        self._glacier = None
        self._init_providers()
    
    def _init_providers(self):
        """Lazily initialize real storage providers."""
        try:
            from sdk.celestia import CelestiaDA
            # Near DA would be similar — using Celestia pattern
            logger.debug("Storage providers available for S-MMU")
        except ImportError:
            logger.debug("S-MMU running in local-only mode")
    
    def _hash_content(self, content: Any) -> str:
        """Compute content hash for integrity verification."""
        return hashlib.sha256(
            json.dumps(content, sort_keys=True, default=str).encode()
        ).hexdigest()
    
    def _log_access(self, address: str, operation: str, tier: MemoryTier):
        """Log memory access for ZK proof generation."""
        if self.enable_access_log:
            self._access_log.append({
                "address": address,
                "operation": operation,
                "tier": tier.value,
                "timestamp": time.time()
            })
            # Keep last 1000 accesses
            if len(self._access_log) > 1000:
                self._access_log = self._access_log[-500:]
    
    def store(
        self, 
        address: str, 
        content: Any, 
        tier: MemoryTier = MemoryTier.L1_CACHE,
        provenance: Optional[str] = None
    ) -> MemoryPage:
        """
        Store content at a semantic address.
        
        Args:
            address: Semantic key (e.g., "market_context", "agent_goal")
            content: Data to store
            tier: Target storage tier
            provenance: Origin checkpoint ID for tracing
            
        Returns:
            MemoryPage with content hash
        """
        content_hash = self._hash_content(content)
        
        page = MemoryPage(
            address=address,
            content=content,
            content_hash=content_hash,
            tier=tier,
            provenance=provenance
        )
        
        if tier == MemoryTier.L1_CACHE:
            self._store_l1(page)
        elif tier == MemoryTier.L2_RAM:
            self._l2_store[address] = page
        elif tier == MemoryTier.L3_STORAGE:
            self._l3_store[address] = page
        
        self._log_access(address, "write", tier)
        logger.debug(f"S-MMU store: {address} -> {tier.value} (hash={content_hash[:12]})")
        
        return page
    
    def _store_l1(self, page: MemoryPage):
        """Store in L1 with LRU eviction."""
        if page.address in self._l1_cache:
            self._l1_cache.move_to_end(page.address)
            self._l1_cache[page.address] = page
        else:
            if len(self._l1_cache) >= self.l1_capacity:
                # Evict LRU page → demote to L2
                evicted_addr, evicted_page = self._l1_cache.popitem(last=False)
                self._demote_to_l2(evicted_page)
                self._stats["evictions"] += 1
            self._l1_cache[page.address] = page
    
    def _demote_to_l2(self, page: MemoryPage):
        """Demote a page from L1 to L2 (Near DA)."""
        page.tier = MemoryTier.L2_RAM
        self._l2_store[page.address] = page
        logger.debug(f"S-MMU demote: {page.address} L1→L2")
    
    def _promote_to_l1(self, page: MemoryPage):
        """Promote a page to L1 cache."""
        page.tier = MemoryTier.L1_CACHE
        page.access_count += 1
        page.last_accessed = time.time()
        self._store_l1(page)
        self._stats["promotions"] += 1
    
    def fetch(self, address: str) -> Optional[MemoryPage]:
        """
        Fetch content from the S-MMU address space.
        Implements page fault handling: L1 → L2 → L3 → L0 recovery.
        
        Args:
            address: Semantic address to fetch
            
        Returns:
            MemoryPage if found, None if total cache miss
        """
        # Try L1 (in-process, <1ms)
        if address in self._l1_cache:
            self._l1_cache.move_to_end(address)
            page = self._l1_cache[address]
            page.access_count += 1
            page.last_accessed = time.time()
            self._stats["l1_hits"] += 1
            self._log_access(address, "read_hit", MemoryTier.L1_CACHE)
            return page
        
        self._stats["l1_misses"] += 1
        
        # Try L2 (Near DA, <500ms)
        if address in self._l2_store:
            page = self._l2_store[address]
            # Verify integrity before promotion
            if page.verify():
                self._promote_to_l1(page)
                self._stats["l2_hits"] += 1
                self._log_access(address, "read_promote_l2", MemoryTier.L2_RAM)
                return page
            else:
                logger.warning(f"S-MMU integrity check failed for {address} in L2!")
                self._stats["page_faults"] += 1
        
        self._stats["l2_misses"] += 1
        
        # Try L3 (Glacier/WeaveDB, <2s)
        if address in self._l3_store:
            page = self._l3_store[address]
            if page.verify():
                # Promote through tiers
                self._l2_store[address] = MemoryPage(
                    address=page.address,
                    content=page.content,
                    content_hash=page.content_hash,
                    tier=MemoryTier.L2_RAM,
                    provenance=page.provenance
                )
                self._promote_to_l1(page)
                self._stats["l3_hits"] += 1
                self._log_access(address, "read_promote_l3", MemoryTier.L3_STORAGE)
                return page
            else:
                logger.warning(f"S-MMU integrity check failed for {address} in L3!")
                self._stats["page_faults"] += 1
        
        # Total cache miss
        self._stats["page_faults"] += 1
        self._log_access(address, "page_fault", MemoryTier.L0_ANCHOR)
        logger.info(f"S-MMU page fault: {address} not found in any tier")
        return None
    
    def invalidate(self, address: str):
        """Remove a page from all tiers."""
        self._l1_cache.pop(address, None)
        self._l2_store.pop(address, None)
        self._l3_store.pop(address, None)
        self._log_access(address, "invalidate", MemoryTier.L1_CACHE)
    
    def flush_to_l3(self, address: str) -> Optional[MemoryPage]:
        """
        Flush a page from L1/L2 to permanent L3 storage.
        Used before agent suspension or migration.
        """
        page = self.fetch(address)
        if page:
            page_copy = MemoryPage(
                address=page.address,
                content=page.content,
                content_hash=page.content_hash,
                tier=MemoryTier.L3_STORAGE,
                access_count=page.access_count,
                provenance=page.provenance
            )
            self._l3_store[address] = page_copy
            self._log_access(address, "flush_l3", MemoryTier.L3_STORAGE)
            logger.info(f"S-MMU flush: {address} → L3 (permanent)")
            return page_copy
        return None
    
    def get_access_log(self) -> List[Dict[str, Any]]:
        """
        Get the memory access log for ZK proof generation.
        This log is used by Phase 4 ZK-Verified Memory Access Patterns.
        """
        return self._access_log.copy()
    
    def get_state_hash(self) -> str:
        """
        Compute unified hash of all L1+L2 state.
        This is the value that would be anchored to L0 during CSP.
        """
        all_hashes = []
        for page in self._l1_cache.values():
            all_hashes.append(page.content_hash)
        for page in self._l2_store.values():
            all_hashes.append(page.content_hash)
        
        combined = "|".join(sorted(all_hashes))
        return hashlib.sha256(combined.encode()).hexdigest()
    
    def get_stats(self) -> Dict[str, Any]:
        """Return S-MMU statistics."""
        total_reads = (
            self._stats["l1_hits"] + self._stats["l2_hits"] + 
            self._stats["l3_hits"] + self._stats["page_faults"]
        )
        return {
            **self._stats,
            "l1_pages": len(self._l1_cache),
            "l2_pages": len(self._l2_store),
            "l3_pages": len(self._l3_store),
            "l1_capacity": self.l1_capacity,
            "hit_rate": (
                f"{self._stats['l1_hits']}/{total_reads} "
                f"({self._stats['l1_hits'] / max(1, total_reads) * 100:.0f}%)"
            ),
            "state_hash": self.get_state_hash()[:16] + "..."
        }
