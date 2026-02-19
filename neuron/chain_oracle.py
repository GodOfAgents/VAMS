"""
VAMS Neuron - Chain Oracle Layer
=================================
Live-data oracle that fetches real-time metrics from all 10 CLR execution
chains. Sits between the agent and the CLR to provide current gas prices,
block times, congestion estimates, and finality data.

Chains covered (matching CLR simulation):
  Account-model L1s:  Ethereum, Avalanche, Solana
  L2 Rollups:         Polygon, Arbitrum, Base
  Privacy chains:     Phala (TEE), Oasis (ZK)
  eUTXO ecosystem:    Cardano, Midnight

Usage:
    from neuron.chain_oracle import OracleManager
    oracle = OracleManager()
    metrics = oracle.get_all_metrics()           # dict[str, ChainMetrics]
    eth = oracle.get_metrics("ethereum")         # single chain
    oracle.refresh()                             # force refresh all

Standalone:
    python -m neuron.chain_oracle                # prints live metrics table
"""

import os
import time
import threading
import requests
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, List
from enum import Enum


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class ChainMetrics:
    """Point-in-time metrics snapshot for a single execution chain."""
    chain: str
    gas_price_gwei: float          # Gas price in Gwei (or equivalent unit)
    block_time_ms: int             # Observed block time (ms)
    last_block: int                # Latest block height
    congestion_pct: float          # Estimated congestion 0-100%
    finality_ms: int               # Time to economic irreversibility (ms)
    timestamp: float               # When this snapshot was taken
    stale: bool = False            # True if fetched from cache after RPC failure
    error: Optional[str] = None    # Error message if fetch failed

    @property
    def age_seconds(self) -> float:
        return time.time() - self.timestamp

    def to_dict(self) -> dict:
        return {
            "chain": self.chain,
            "gas_price_gwei": round(self.gas_price_gwei, 4),
            "block_time_ms": self.block_time_ms,
            "last_block": self.last_block,
            "congestion_pct": round(self.congestion_pct, 1),
            "finality_ms": self.finality_ms,
            "age_s": round(self.age_seconds, 1),
            "stale": self.stale,
        }


class OracleStatus(Enum):
    LIVE = "live"
    STALE = "stale"
    OFFLINE = "offline"


# =============================================================================
# ABSTRACT BASE
# =============================================================================

class ChainOracle(ABC):
    """Abstract base class for chain-specific oracles."""

    name: str = "base"
    chain_type: str = "unknown"

    def __init__(self, rpc_url: str, timeout: int = 10):
        self.rpc_url = rpc_url
        self.timeout = timeout

    @abstractmethod
    def fetch_metrics(self) -> ChainMetrics:
        """Fetch live metrics from this chain's RPC."""
        ...

    def _rpc_post(self, payload: dict) -> dict:
        """Send a JSON-RPC POST request."""
        resp = requests.post(
            self.rpc_url,
            json=payload,
            timeout=self.timeout,
            headers={"Content-Type": "application/json"},
        )
        resp.raise_for_status()
        return resp.json()

    def _rpc_get(self, path: str = "", params: dict = None) -> dict:
        """Send a GET request (for REST APIs like Blockfrost)."""
        url = f"{self.rpc_url}{path}"
        resp = requests.get(url, params=params, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def _eth_gas_and_block(self) -> ChainMetrics:
        """Standard EVM pattern: eth_gasPrice + eth_blockNumber."""
        # Batch both calls
        batch = [
            {"jsonrpc": "2.0", "id": 1, "method": "eth_gasPrice", "params": []},
            {"jsonrpc": "2.0", "id": 2, "method": "eth_blockNumber", "params": []},
        ]
        try:
            resp = requests.post(
                self.rpc_url,
                json=batch,
                timeout=self.timeout,
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            results = resp.json()

            gas_wei = int(results[0]["result"], 16)
            gas_gwei = gas_wei / 1e9
            block_num = int(results[1]["result"], 16)

            return ChainMetrics(
                chain=self.name,
                gas_price_gwei=gas_gwei,
                block_time_ms=self._default_block_time_ms(),
                last_block=block_num,
                congestion_pct=self._estimate_congestion(gas_gwei),
                finality_ms=self._default_finality_ms(),
                timestamp=time.time(),
            )
        except Exception as e:
            return ChainMetrics(
                chain=self.name,
                gas_price_gwei=0.0,
                block_time_ms=self._default_block_time_ms(),
                last_block=0,
                congestion_pct=0.0,
                finality_ms=self._default_finality_ms(),
                timestamp=time.time(),
                stale=True,
                error=str(e),
            )

    def _default_block_time_ms(self) -> int:
        return 12_000  # Override per chain

    def _default_finality_ms(self) -> int:
        return 780_000  # Override per chain

    def _estimate_congestion(self, gas_gwei: float) -> float:
        """Rough congestion estimate from gas price vs baseline."""
        baseline = self._baseline_gas_gwei()
        if baseline <= 0:
            return 0.0
        ratio = gas_gwei / baseline
        return min(100.0, max(0.0, (ratio - 1.0) * 50.0))

    def _baseline_gas_gwei(self) -> float:
        return 20.0  # Override per chain


# =============================================================================
# CONCRETE ORACLES - Account-Model L1s
# =============================================================================

class EthereumOracle(ChainOracle):
    name = "Ethereum"
    chain_type = "Account-model L1"

    def __init__(self, rpc_url: str = None, timeout: int = 10):
        url = rpc_url or os.getenv("ETHEREUM_RPC", "https://ethereum-rpc.publicnode.com")
        super().__init__(url, timeout)

    def fetch_metrics(self) -> ChainMetrics:
        return self._eth_gas_and_block()

    def _default_block_time_ms(self) -> int:
        return 12_000

    def _default_finality_ms(self) -> int:
        return 780_000  # ~13 min (2 epochs)

    def _baseline_gas_gwei(self) -> float:
        return 20.0


class AvalancheOracle(ChainOracle):
    name = "Avalanche"
    chain_type = "Account-model L1"

    def __init__(self, rpc_url: str = None, timeout: int = 10):
        url = rpc_url or os.getenv("AVALANCHE_RPC", "https://api.avax.network/ext/bc/C/rpc")
        super().__init__(url, timeout)

    def fetch_metrics(self) -> ChainMetrics:
        return self._eth_gas_and_block()

    def _default_block_time_ms(self) -> int:
        return 2_000

    def _default_finality_ms(self) -> int:
        return 2_000  # Sub-second with Snowman++

    def _baseline_gas_gwei(self) -> float:
        return 25.0


class SolanaOracle(ChainOracle):
    name = "Solana"
    chain_type = "Account-model L1"

    def __init__(self, rpc_url: str = None, timeout: int = 10):
        url = rpc_url or os.getenv("SOLANA_RPC", "https://api.mainnet-beta.solana.com")
        super().__init__(url, timeout)

    def fetch_metrics(self) -> ChainMetrics:
        try:
            # Get latest slot (block height equivalent)
            slot_resp = self._rpc_post({
                "jsonrpc": "2.0", "id": 1,
                "method": "getSlot", "params": []
            })
            slot = slot_resp.get("result", 0)

            # Get recent prioritization fees for congestion estimate
            fee_resp = self._rpc_post({
                "jsonrpc": "2.0", "id": 2,
                "method": "getRecentPrioritizationFees", "params": []
            })
            fees = fee_resp.get("result", [])
            avg_fee = 0.0
            if fees:
                avg_fee = sum(f.get("prioritizationFee", 0) for f in fees[-10:]) / min(len(fees), 10)

            # Convert lamports to approximate Gwei equivalent
            gas_gwei = avg_fee / 1e3  # rough normalization

            return ChainMetrics(
                chain=self.name,
                gas_price_gwei=gas_gwei,
                block_time_ms=400,
                last_block=slot,
                congestion_pct=min(100.0, avg_fee / 100.0),
                finality_ms=6_400,
                timestamp=time.time(),
            )
        except Exception as e:
            return ChainMetrics(
                chain=self.name, gas_price_gwei=0.0,
                block_time_ms=400, last_block=0,
                congestion_pct=0.0, finality_ms=6_400,
                timestamp=time.time(), stale=True, error=str(e),
            )


# =============================================================================
# CONCRETE ORACLES - L2 Rollups
# =============================================================================

class PolygonOracle(ChainOracle):
    name = "Polygon"
    chain_type = "L2 Rollup"

    def __init__(self, rpc_url: str = None, timeout: int = 10):
        url = rpc_url or os.getenv("POLYGON_RPC", "https://polygon-rpc.com")
        super().__init__(url, timeout)

    def fetch_metrics(self) -> ChainMetrics:
        return self._eth_gas_and_block()

    def _default_block_time_ms(self) -> int:
        return 800

    def _default_finality_ms(self) -> int:
        return 256_000  # ~4.3 min checkpoint

    def _baseline_gas_gwei(self) -> float:
        return 30.0


class ArbitrumOracle(ChainOracle):
    name = "Arbitrum"
    chain_type = "L2 Rollup"

    def __init__(self, rpc_url: str = None, timeout: int = 10):
        url = rpc_url or os.getenv("ARBITRUM_RPC", "https://arb1.arbitrum.io/rpc")
        super().__init__(url, timeout)

    def fetch_metrics(self) -> ChainMetrics:
        return self._eth_gas_and_block()

    def _default_block_time_ms(self) -> int:
        return 1_500

    def _default_finality_ms(self) -> int:
        return 604_800_000  # 7d challenge window

    def _baseline_gas_gwei(self) -> float:
        return 0.1


class BaseOracle(ChainOracle):
    name = "Base"
    chain_type = "L2 Rollup"

    def __init__(self, rpc_url: str = None, timeout: int = 10):
        url = rpc_url or os.getenv("BASE_RPC", "https://mainnet.base.org")
        super().__init__(url, timeout)

    def fetch_metrics(self) -> ChainMetrics:
        return self._eth_gas_and_block()

    def _default_block_time_ms(self) -> int:
        return 1_000

    def _default_finality_ms(self) -> int:
        return 604_800_000  # 7d challenge window

    def _baseline_gas_gwei(self) -> float:
        return 0.05


# =============================================================================
# CONCRETE ORACLES - Privacy Chains
# =============================================================================

class PhalaOracle(ChainOracle):
    name = "Phala"
    chain_type = "Privacy (TEE)"

    def __init__(self, rpc_url: str = None, timeout: int = 10):
        url = rpc_url or os.getenv("PHALA_RPC", "https://phala.api.onfinality.io/public")
        super().__init__(url, timeout)

    def fetch_metrics(self) -> ChainMetrics:
        """Substrate-based chain: use system_syncState for block height."""
        try:
            resp = self._rpc_post({
                "jsonrpc": "2.0", "id": 1,
                "method": "chain_getHeader", "params": []
            })
            result = resp.get("result", {})
            block_num = int(result.get("number", "0x0"), 16)

            return ChainMetrics(
                chain=self.name,
                gas_price_gwei=0.5,  # Weight-based, approximate
                block_time_ms=3_000,
                last_block=block_num,
                congestion_pct=0.0,
                finality_ms=3_000,
                timestamp=time.time(),
            )
        except Exception as e:
            return ChainMetrics(
                chain=self.name, gas_price_gwei=0.5,
                block_time_ms=3_000, last_block=0,
                congestion_pct=0.0, finality_ms=3_000,
                timestamp=time.time(), stale=True, error=str(e),
            )


class OasisOracle(ChainOracle):
    name = "Oasis"
    chain_type = "Privacy (ZK)"

    def __init__(self, rpc_url: str = None, timeout: int = 10):
        url = rpc_url or os.getenv("OASIS_RPC", "https://emerald.oasis.io")
        super().__init__(url, timeout)

    def fetch_metrics(self) -> ChainMetrics:
        return self._eth_gas_and_block()

    def _default_block_time_ms(self) -> int:
        return 6_000

    def _default_finality_ms(self) -> int:
        return 6_000  # Tendermint BFT instant finality

    def _baseline_gas_gwei(self) -> float:
        return 100.0  # Oasis uses higher base gas


# =============================================================================
# CONCRETE ORACLES - eUTXO / Cardano Ecosystem
# =============================================================================

class CardanoOracle(ChainOracle):
    name = "Cardano"
    chain_type = "eUTXO"

    def __init__(self, rpc_url: str = None, timeout: int = 10):
        url = rpc_url or os.getenv("CARDANO_RPC", "https://cardano-mainnet.blockfrost.io/api/v0")
        super().__init__(url, timeout)
        self.api_key = os.getenv("BLOCKFROST_API_KEY", "")

    def fetch_metrics(self) -> ChainMetrics:
        """Blockfrost REST API for Cardano metrics."""
        try:
            headers = {"project_id": self.api_key} if self.api_key else {}

            # Latest block
            resp = requests.get(
                f"{self.rpc_url}/blocks/latest",
                headers=headers, timeout=self.timeout,
            )
            resp.raise_for_status()
            block = resp.json()

            block_height = block.get("height", 0)
            block_time = block.get("time", 0)
            tx_count = block.get("tx_count", 0)

            # Epoch parameters for fee estimation
            epoch_resp = requests.get(
                f"{self.rpc_url}/epochs/latest/parameters",
                headers=headers, timeout=self.timeout,
            )
            epoch_resp.raise_for_status()
            params = epoch_resp.json()

            min_fee_a = int(params.get("min_fee_a", 44))
            min_fee_b = int(params.get("min_fee_b", 155381))

            # Approximate gas equivalent: min_fee for a ~250 byte tx in ADA → Gwei
            fee_lovelace = min_fee_a * 250 + min_fee_b
            fee_ada = fee_lovelace / 1_000_000
            gas_gwei_equiv = fee_ada * 1000  # rough normalization

            # Congestion: tx_count relative to max (~340 tx/block)
            congestion = min(100.0, (tx_count / 340.0) * 100.0)

            return ChainMetrics(
                chain=self.name,
                gas_price_gwei=gas_gwei_equiv,
                block_time_ms=20_000,
                last_block=block_height,
                congestion_pct=congestion,
                finality_ms=720_000,  # ~12 min
                timestamp=time.time(),
            )
        except Exception as e:
            return ChainMetrics(
                chain=self.name, gas_price_gwei=0.17,
                block_time_ms=20_000, last_block=0,
                congestion_pct=0.0, finality_ms=720_000,
                timestamp=time.time(), stale=True, error=str(e),
            )


class MidnightOracle(ChainOracle):
    name = "Midnight"
    chain_type = "eUTXO Sidechain"

    def __init__(self, rpc_url: str = None, timeout: int = 10):
        url = rpc_url or os.getenv("MIDNIGHT_RPC", "https://midnight.network/api/v0")
        super().__init__(url, timeout)

    def fetch_metrics(self) -> ChainMetrics:
        """Midnight is not yet publicly queryable — return estimated defaults
        derived from Cardano sidechain specs. Will be upgraded when Midnight
        mainnet launches with a public API."""
        try:
            # Attempt Blockfrost-style query
            resp = requests.get(
                f"{self.rpc_url}/blocks/latest",
                timeout=self.timeout,
            )
            resp.raise_for_status()
            block = resp.json()
            block_height = block.get("height", 0)

            return ChainMetrics(
                chain=self.name,
                gas_price_gwei=0.40,
                block_time_ms=10_000,
                last_block=block_height,
                congestion_pct=0.0,
                finality_ms=60_000,
                timestamp=time.time(),
            )
        except Exception:
            # Expected: Midnight mainnet not yet live — use spec defaults
            return ChainMetrics(
                chain=self.name,
                gas_price_gwei=0.40,
                block_time_ms=10_000,
                last_block=0,
                congestion_pct=0.0,
                finality_ms=60_000,
                timestamp=time.time(),
                stale=True,
                error="Midnight mainnet not yet live — using spec defaults",
            )


# =============================================================================
# ORACLE MANAGER
# =============================================================================

# Default TTL for cached metrics (seconds)
ORACLE_CACHE_TTL = int(os.getenv("ORACLE_CACHE_TTL", "30"))


class OracleManager:
    """Manages all chain oracles with TTL-cached metrics.

    Thread-safe. Graceful degradation: returns stale data when RPC is
    unreachable.

    Usage:
        manager = OracleManager()
        all_metrics = manager.get_all_metrics()    # dict[str, ChainMetrics]
        eth = manager.get_metrics("Ethereum")      # single chain
        manager.refresh()                          # force-refresh all
    """

    def __init__(self, ttl: int = None, oracles: List[ChainOracle] = None):
        self.ttl = ttl or ORACLE_CACHE_TTL
        self._lock = threading.Lock()
        self._cache: Dict[str, ChainMetrics] = {}

        # Initialize all 10 CLR chain oracles
        self._oracles: Dict[str, ChainOracle] = {}
        if oracles:
            for o in oracles:
                self._oracles[o.name] = o
        else:
            default_oracles = [
                EthereumOracle(),
                AvalancheOracle(),
                SolanaOracle(),
                PolygonOracle(),
                ArbitrumOracle(),
                BaseOracle(),
                PhalaOracle(),
                OasisOracle(),
                CardanoOracle(),
                MidnightOracle(),
            ]
            for o in default_oracles:
                self._oracles[o.name] = o

    @property
    def chain_names(self) -> List[str]:
        return list(self._oracles.keys())

    def get_metrics(self, chain: str) -> Optional[ChainMetrics]:
        """Get metrics for a single chain, using cache if fresh."""
        oracle = self._oracles.get(chain)
        if not oracle:
            return None

        with self._lock:
            cached = self._cache.get(chain)
            if cached and cached.age_seconds < self.ttl:
                return cached

        # Cache miss or stale — fetch live
        try:
            metrics = oracle.fetch_metrics()
        except Exception as e:
            # Graceful degradation: return stale data
            with self._lock:
                cached = self._cache.get(chain)
                if cached:
                    cached.stale = True
                    return cached
            metrics = ChainMetrics(
                chain=chain, gas_price_gwei=0.0,
                block_time_ms=0, last_block=0,
                congestion_pct=0.0, finality_ms=0,
                timestamp=time.time(), stale=True, error=str(e),
            )

        with self._lock:
            self._cache[chain] = metrics
        return metrics

    def get_all_metrics(self) -> Dict[str, ChainMetrics]:
        """Get metrics for all chains. Uses cache where fresh."""
        result = {}
        for name in self._oracles:
            m = self.get_metrics(name)
            if m:
                result[name] = m
        return result

    def refresh(self) -> Dict[str, ChainMetrics]:
        """Force-refresh all chain metrics (ignores TTL)."""
        with self._lock:
            self._cache.clear()
        return self.get_all_metrics()

    def get_status(self) -> Dict[str, OracleStatus]:
        """Get status of each oracle (live/stale/offline)."""
        statuses = {}
        for name in self._oracles:
            with self._lock:
                cached = self._cache.get(name)
            if not cached:
                statuses[name] = OracleStatus.OFFLINE
            elif cached.stale:
                statuses[name] = OracleStatus.STALE
            else:
                statuses[name] = OracleStatus.LIVE
        return statuses

    def print_metrics_table(self) -> None:
        """Print a formatted table of all chain metrics."""
        metrics = self.get_all_metrics()

        print(f"\n{'=' * 95}")
        print(f"  VAMS Chain Oracle — Live Metrics (TTL: {self.ttl}s)")
        print(f"{'=' * 95}")
        print(f"  {'Chain':<12} {'Type':<20} {'Gas (Gwei)':>12} "
              f"{'Block Time':>12} {'Block #':>12} {'Cong%':>7} "
              f"{'Status':>8}")
        print(f"  {'-' * 12} {'-' * 20} {'-' * 12} {'-' * 12} "
              f"{'-' * 12} {'-' * 7} {'-' * 8}")

        for name, m in metrics.items():
            oracle = self._oracles.get(name)
            chain_type = oracle.chain_type if oracle else "unknown"
            status = "STALE" if m.stale else "LIVE"
            status_symbol = "⚠️" if m.stale else "✅"

            print(f"  {m.chain:<12} {chain_type:<20} {m.gas_price_gwei:>12.4f} "
                  f"{m.block_time_ms:>10}ms {m.last_block:>12,} "
                  f"{m.congestion_pct:>6.1f}% {status_symbol} {status}")

        print(f"{'=' * 95}")
        print(f"  Fetched at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  Chains: {len(metrics)} / {len(self._oracles)}")
        print()


# =============================================================================
# STANDALONE ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    print("[Oracle] Fetching live metrics from all 10 CLR chains...")
    manager = OracleManager()
    manager.print_metrics_table()
