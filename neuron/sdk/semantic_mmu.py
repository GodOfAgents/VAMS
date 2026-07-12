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
import os
import re
import secrets
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable
from enum import Enum

# Try relative import or fallback to absolute path import
try:
    from neuron.sdk.sira_engine import SiraEngine
except ImportError:
    try:
        from sdk.sira_engine import SiraEngine
    except ImportError:
        SiraEngine = None

logger = logging.getLogger("vams.semantic_mmu")

MEMORY_ROOT = Path(".data") / "memory"
SAFE_ADDRESS_PART = re.compile(r"^[A-Za-z0-9._-]{1,96}$")
MAX_PATCH_BYTES = 65_536


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
    value_score: float = 1.0       # V(m) consolidation scoring
    
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
        enable_access_log: bool = True,
        session_id: Optional[str] = None,
        review_authorizer: Optional[Callable[[str, str], bool]] = None,
    ):
        self.l1_capacity = l1_capacity
        self.l2_provider = l2_provider
        self.l3_provider = l3_provider
        self.enable_access_log = enable_access_log
        self.session_id = session_id or secrets.token_hex(16)
        self.review_authorizer = review_authorizer
        
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
            "evictions": 0,
            "hard_resets": 0,
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

    @staticmethod
    def _validate_address(address: str) -> List[str]:
        if not isinstance(address, str) or not address or len(address) > 256:
            raise ValueError("Memory address must be a non-empty string of at most 256 characters")
        if "\\" in address or address.startswith("/"):
            raise ValueError("Memory address must be a relative POSIX-style path")
        parts = address.split("/")
        if any(part in {"", ".", ".."} or not SAFE_ADDRESS_PART.fullmatch(part) for part in parts):
            raise ValueError("Memory address contains an unsafe path component")
        return parts

    @classmethod
    def _memory_path(cls, address: str) -> Path:
        parts = cls._validate_address(address)
        root = MEMORY_ROOT.resolve()
        path = root.joinpath(*parts[:-1], parts[-1] + ".json").resolve()
        if root not in path.parents:
            raise ValueError("Memory address escapes the HORMA root")
        return path
    
    def _log_access(self, address: str, operation: str, tier: MemoryTier):
        """Log memory access for ZK proof generation."""
        if not self.enable_access_log:
            return
        self._access_log.append(
            {
                "address_hash": hashlib.sha256(address.encode("utf-8")).hexdigest(),
                "operation": operation,
                "tier": tier.value,
                "session_id": self.session_id,
                "timestamp": time.time(),
            }
        )
        if len(self._access_log) > 10_000:
            del self._access_log[: len(self._access_log) - 10_000]

    def _write_to_horma_fs(self, page: MemoryPage):
        """Write page to the HORMA hierarchical filesystem (L3 Storage)."""
        path = self._memory_path(page.address)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('w', encoding="utf-8") as f:
                # Store serialized page metadata and content
                json.dump({
                    "address": page.address,
                    "content": page.content,
                    "content_hash": page.content_hash,
                    "tier": page.tier.value,
                    "provenance": page.provenance,
                    "value_score": page.value_score,
                    "access_count": page.access_count,
                    "last_accessed": page.last_accessed,
                    "created_at": page.created_at
                }, f, indent=2)
            logger.debug(f"HORMA FS write complete: {path}")
        except Exception as e:
            logger.error(f"Failed to write to HORMA FS: {e}")

    def evaluate_memory_value(self, content: Any) -> float:
        """
        V(m) Learned Consolidation Filter.
        Evaluates page value based on the 7 psychological factors:
        Utility, Alignment, Recency/History, etc.
        """
        # Multi-factor weights
        # V(m) = w_util * f_util + w_align * f_align + w_rec * f_rec
        
        # 1. Task Utility (does it contain successful workflow descriptors/status?)
        f_util = 0.5
        content_str = str(content).lower()
        if "success" in content_str or "complete" in content_str:
            f_util = 1.0
        elif "fail" in content_str or "error" in content_str:
            f_util = 0.2
            
        # 2. Value Alignment (does it violate safety/GCA parameters?)
        f_align = 1.0
        if "exploit" in content_str or "attack" in content_str or "malicious" in content_str:
            f_align = 0.0
            
        # 3. Usage History / Complexity
        f_size = min(1.0, len(content_str) / 5000.0)
        
        # 4. expected frequency / task relevance
        f_freq = 0.8
        
        # Weights: 40% Utility, 30% Alignment, 20% size/history, 10% freq
        v_m = 0.4 * f_util + 0.3 * f_align + 0.2 * f_size + 0.1 * f_freq
        return float(round(v_m, 3))

    def fold_completed_subtask(self, workflow_id: str, raw_trace_path: str) -> str:
        """
        HIPIF Information Folding.
        Folds raw trace steps into a compact, high-density summary block
        and stores it in the HORMA directory layout.
        """
        self._validate_address(f"workflows/{workflow_id}/folded_summary")
        trace_path = Path(raw_trace_path).resolve()
        memory_root = MEMORY_ROOT.resolve()
        if memory_root not in trace_path.parents:
            raise ValueError("HIPIF raw traces must be contained under .data/memory")
        if not trace_path.exists() or not trace_path.is_file():
            return "No raw trace found."
            
        try:
            with trace_path.open('r', encoding="utf-8") as f:
                raw_content = f.read()
                
            # Perform folding (mocking fast LLM translation logic using rule-based compression)
            lines = raw_content.split('\n')
            tx_hashes = [line.strip() for line in lines if "0x" in line or "tx" in line.lower()]
            errors = [line.strip() for line in lines if "error" in line.lower() or "exception" in line.lower()]
            success = any("success" in line.lower() or "done" in line.lower() for line in lines)
            
            folded_lines = [
                f"# Folded Subtask Summary: {workflow_id}",
                f"Status: {'SUCCESS' if success else 'COMPLETED_WITH_WARNINGS'}",
                f"Raw Step Count: {len(lines)}",
                "Transactions: " + (", ".join(tx_hashes[:3]) if tx_hashes else "None"),
                "Errors Captured: " + ("; ".join(errors[:3]) if errors else "None"),
                "Summary: Automatically compacted subtask boundary record via HIPIF."
            ]
            folded_summary = "\n".join(folded_lines)
            
            # Store folded summary in S-MMU under L3 HORMA directory layout
            address = f"workflows/{workflow_id}/folded_summary"
            self.store(address, folded_summary, tier=MemoryTier.L3_STORAGE)
            
            # Safely delete raw trace
            trace_path.unlink()
            logger.info(f"HIPIF: Folded raw trace of {workflow_id} and deleted original.")
            return folded_summary
        except Exception as e:
            logger.error(f"Failed to run HIPIF folding: {e}")
            return f"HIPIF folding failed: {e}"

    def apply_memory_patch(
        self,
        address: str,
        patch: Dict[str, Any],
        *,
        review_approved: bool = False,
        reviewed_by: Optional[str] = None,
    ) -> bool:
        """
        EvoMem Patch-Based Evolution.
        Appends a 4-tuple change patch to a jsonl file for auditability:
        {previous_state, new_state, rationale_for_change, supporting_evidence}
        """
        self._validate_address(address)
        if (
            not review_approved
            or not reviewed_by
            or not self._review_is_authorized("evomem_patch", reviewed_by)
        ):
            logger.warning(
                "EvoMem: Persistent mutation requires an authorized reviewer."
            )
            return False

        required_fields = {"previous_state", "new_state", "rationale_for_change", "supporting_evidence"}
        if not all(field in patch for field in required_fields):
            logger.warning("EvoMem: Patch lacks one or more of the 4 required fields.")
            return False
            
        reviewed_patch = {
            **patch,
            "reviewed_by": reviewed_by,
            "reviewed_at": int(time.time()),
            "session_id": self.session_id,
        }
        encoded_patch = json.dumps(reviewed_patch, sort_keys=True, default=str)
        if len(encoded_patch.encode("utf-8")) > MAX_PATCH_BYTES:
            logger.warning("EvoMem: Patch exceeds the 64 KiB persistence limit.")
            return False

        patch_dir = MEMORY_ROOT / "patches"
        patch_dir.mkdir(parents=True, exist_ok=True)
        # Safe filename from address
        safe_name = address.replace("/", "_").replace("\\", "_")
        patch_path = patch_dir / f"{safe_name}.jsonl"
        
        try:
            with patch_path.open('a', encoding="utf-8") as f:
                f.write(encoded_patch + "\n")
            logger.info(f"EvoMem: Appended memory patch for {address}.")
            return True
        except Exception as e:
            logger.error(f"Failed to apply EvoMem patch for {address}: {e}")
            return False
    
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
        self._validate_address(address)
        content_hash = self._hash_content(content)
        
        page = MemoryPage(
            address=address,
            content=content,
            content_hash=content_hash,
            tier=tier,
            provenance=provenance
        )
        
        # V(m) Consolidation Filter evaluation
        page.value_score = self.evaluate_memory_value(content)
        
        if tier == MemoryTier.L1_CACHE:
            self._store_l1(page)
        elif tier == MemoryTier.L2_RAM:
            self._l2_store[address] = page
        elif tier == MemoryTier.L3_STORAGE:
            self._l3_store[address] = page
            self._write_to_horma_fs(page)
        
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
        self._validate_address(address)

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
        
        # Try checking local HORMA FS if not in _l3_store dictionary
        if address not in self._l3_store:
            path = self._memory_path(address)
            if path.exists():
                try:
                    with path.open('r', encoding="utf-8") as f:
                        data = json.load(f)
                        page = MemoryPage(
                            address=data["address"],
                            content=data["content"],
                            content_hash=data["content_hash"],
                            tier=MemoryTier.L3_STORAGE,
                            provenance=data.get("provenance"),
                            value_score=data.get("value_score", 1.0),
                            access_count=data.get("access_count", 0),
                            last_accessed=data.get("last_accessed", time.time()),
                            created_at=data.get("created_at", time.time())
                        )
                        self._l3_store[address] = page
                except Exception as e:
                    logger.warning(f"Failed to read from HORMA FS for {address}: {e}")
        
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
        
        # Remove from HORMA FS as well
        path = self._memory_path(address)
        if path.exists():
            try:
                path.unlink()
            except Exception:
                pass
                
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
                provenance=page.provenance,
                value_score=page.value_score
            )
            self._l3_store[address] = page_copy
            self._write_to_horma_fs(page_copy)
            self._log_access(address, "flush_l3", MemoryTier.L3_STORAGE)
            logger.info(f"S-MMU flush: {address} → L3 (permanent)")
            return page_copy
        return None

    def checkpoint_interrupt_state(self, interrupt_id: str, escrow_record: Any, request_payload: Dict[str, Any]):
        """Stores a snapshot of the current interrupt's escrow state and request in L2_RAM (session-scoped)."""
        address = f"_irq_checkpoint/{interrupt_id}"
        checkpoint_data = {
            "nonce": escrow_record.nonce,
            "provider": escrow_record.provider,
            "escrow_id": escrow_record.escrow_id.hex() if hasattr(escrow_record.escrow_id, "hex") else str(escrow_record.escrow_id),
            "amount_wei": escrow_record.amount_wei,
            "expires_at": escrow_record.expires_at,
            "request_payload": request_payload
        }
        self.store(address, checkpoint_data, tier=MemoryTier.L2_RAM)
        logger.info(f"S-MMU checkpoint stored for interrupt {interrupt_id}")

    def restore_interrupt_state(self, interrupt_id: str) -> Optional[Dict[str, Any]]:
        """Fetches the checkpoint from L2 (or L3 HORMA FS if L2 was evicted)."""
        address = f"_irq_checkpoint/{interrupt_id}"
        page = self.fetch(address)
        if page:
            return page.content
        return None

    def hard_reset_session(
        self,
        *,
        purge_persistent: bool = False,
        review_approved: bool = False,
        reviewed_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Clear session memory and rotate its identity without leaking content."""
        if purge_persistent and (
            not review_approved
            or not reviewed_by
            or not self._review_is_authorized("persistent_purge", reviewed_by)
        ):
            raise PermissionError("Persistent L3 erasure requires an authorized reviewer")

        cleared = {
            "l1_pages": len(self._l1_cache),
            "l2_pages": len(self._l2_store),
            "access_events": len(self._access_log),
            "l3_pages": len(self._l3_store) if purge_persistent else 0,
        }
        old_session_hash = hashlib.sha256(self.session_id.encode("utf-8")).hexdigest()

        self._l1_cache.clear()
        self._l2_store.clear()
        self._access_log.clear()
        if purge_persistent:
            for address in list(self._l3_store):
                path = self._memory_path(address)
                if path.exists():
                    path.unlink()
            self._l3_store.clear()

        self.session_id = secrets.token_hex(16)
        self._stats["hard_resets"] += 1
        return {
            **cleared,
            "old_session_hash": old_session_hash,
            "persistent_purged": purge_persistent,
        }

    def _review_is_authorized(self, action: str, reviewed_by: str) -> bool:
        if self.review_authorizer is None:
            return False
        try:
            return bool(self.review_authorizer(action, reviewed_by))
        except Exception:
            return False


    
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
