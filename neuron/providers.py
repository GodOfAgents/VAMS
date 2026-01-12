"""
VAMS Neuron - DA Provider Abstraction Layer
============================================
Modular provider system for multiple Data Availability networks.

Supported Providers:
- Celestia (Mocha Testnet) - Default DA
- EigenDA (Holesky Testnet) - High-value enterprise
- Near DA (Testnet) - High-frequency operations  
- Avail (Turing Testnet) - ZK/Validium operations
"""

import time
import requests
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from enum import Enum


class ProviderStatus(Enum):
    """Health status of a DA provider."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


@dataclass
class BlockInfo:
    """Information about a block from any DA provider."""
    height: int
    network: str
    provider: str
    timestamp: float
    block_hash: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "height": self.height,
            "network": self.network,
            "provider": self.provider,
            "timestamp": self.timestamp,
            "block_hash": self.block_hash
        }


@dataclass
class HealthStatus:
    """Health check result for a provider."""
    provider: str
    status: ProviderStatus
    latency_ms: float
    last_block: Optional[int] = None
    error: Optional[str] = None


class DAProvider(ABC):
    """Abstract base class for Data Availability providers."""
    
    name: str = "base"
    network: str = "unknown"
    
    def __init__(self, rpc_url: str, timeout: int = 10):
        self.rpc_url = rpc_url
        self.timeout = timeout
        self.session = requests.Session()
        self._last_block: Optional[int] = None
        self._last_check: float = 0
    
    @abstractmethod
    def get_latest_block(self) -> Optional[BlockInfo]:
        """Fetch the latest block from this provider."""
        pass
    
    def get_health(self) -> HealthStatus:
        """Check provider health by fetching latest block."""
        start = time.time()
        try:
            block = self.get_latest_block()
            latency = (time.time() - start) * 1000
            
            if block:
                self._last_block = block.height
                return HealthStatus(
                    provider=self.name,
                    status=ProviderStatus.HEALTHY,
                    latency_ms=latency,
                    last_block=block.height
                )
            else:
                return HealthStatus(
                    provider=self.name,
                    status=ProviderStatus.DEGRADED,
                    latency_ms=latency,
                    error="No block returned"
                )
        except Exception as e:
            latency = (time.time() - start) * 1000
            return HealthStatus(
                provider=self.name,
                status=ProviderStatus.OFFLINE,
                latency_ms=latency,
                error=str(e)
            )


class CelestiaProvider(DAProvider):
    """Celestia Mocha Testnet provider."""
    
    name = "celestia"
    network = "mocha-4"
    
    def __init__(self, rpc_url: str = "https://rpc-mocha.pops.one", timeout: int = 10):
        super().__init__(rpc_url, timeout)
    
    def get_latest_block(self) -> Optional[BlockInfo]:
        """Query Celestia RPC for latest block."""
        try:
            response = self.session.get(
                f"{self.rpc_url}/status",
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                sync_info = data['result']['sync_info']
                node_info = data['result']['node_info']
                
                return BlockInfo(
                    height=int(sync_info['latest_block_height']),
                    network=node_info['network'],
                    provider=self.name,
                    timestamp=time.time(),
                    block_hash=sync_info.get('latest_block_hash')
                )
        except Exception:
            pass
        return None


class EigenDAProvider(DAProvider):
    """EigenDA on Holesky Testnet provider (via Holesky ETH RPC)."""
    
    name = "eigenda"
    network = "holesky"
    
    def __init__(self, rpc_url: str = "https://holesky.drpc.org", timeout: int = 10):
        super().__init__(rpc_url, timeout)
    
    def get_latest_block(self) -> Optional[BlockInfo]:
        """Query Holesky ETH RPC for latest block (EigenDA uses Holesky)."""
        try:
            # Query Holesky Ethereum RPC (EigenDA is deployed on Holesky)
            response = self.session.post(
                self.rpc_url,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "eth_blockNumber",
                    "params": []
                },
                headers={"Content-Type": "application/json"},
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                if 'result' in data:
                    # Ethereum returns hex block number
                    height = int(data['result'], 16)
                    return BlockInfo(
                        height=height,
                        network=self.network,
                        provider=self.name,
                        timestamp=time.time()
                    )
        except Exception:
            pass
        return None


class NearDAProvider(DAProvider):
    """Near Protocol DA Testnet provider."""
    
    name = "near"
    network = "testnet"
    
    def __init__(self, rpc_url: str = "https://rpc.testnet.near.org", timeout: int = 10):
        super().__init__(rpc_url, timeout)
    
    def get_latest_block(self) -> Optional[BlockInfo]:
        """Query Near RPC for latest block."""
        try:
            response = self.session.post(
                self.rpc_url,
                json={
                    "jsonrpc": "2.0",
                    "id": "vams",
                    "method": "status",
                    "params": []
                },
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                if 'result' in data:
                    sync_info = data['result']['sync_info']
                    return BlockInfo(
                        height=int(sync_info['latest_block_height']),
                        network=self.network,
                        provider=self.name,
                        timestamp=time.time(),
                        block_hash=sync_info.get('latest_block_hash')
                    )
        except Exception:
            pass
        return None


class AvailProvider(DAProvider):
    """Avail Turing Testnet provider (via OnFinality)."""
    
    name = "avail"
    network = "turing"
    
    def __init__(self, rpc_url: str = "https://avail-turing.api.onfinality.io/public", timeout: int = 10):
        super().__init__(rpc_url, timeout)
    
    def get_latest_block(self) -> Optional[BlockInfo]:
        """Query Avail RPC for latest block (Substrate-based)."""
        try:
            # Avail uses Substrate JSON-RPC
            response = self.session.post(
                self.rpc_url,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "chain_getHeader",
                    "params": []
                },
                headers={"Content-Type": "application/json"},
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                if 'result' in data:
                    header = data['result']
                    # Substrate returns hex block number
                    height = int(header['number'], 16)
                    return BlockInfo(
                        height=height,
                        network=self.network,
                        provider=self.name,
                        timestamp=time.time(),
                        block_hash=header.get('parentHash')
                    )
        except Exception:
            pass
        return None


class ProviderManager:
    """
    Manages multiple DA providers with health monitoring and failover.
    """
    
    def __init__(self, providers: Optional[List[DAProvider]] = None):
        if providers is None:
            # Default provider order based on VAMS architecture
            providers = [
                CelestiaProvider(),
                EigenDAProvider(),
                NearDAProvider(),
                AvailProvider()
            ]
        
        self.providers: Dict[str, DAProvider] = {p.name: p for p in providers}
        self.provider_order = [p.name for p in providers]
        self.current_provider: str = self.provider_order[0]
        self.health_cache: Dict[str, HealthStatus] = {}
        self._failover_enabled = True
    
    def set_primary(self, provider_name: str):
        """Set the primary provider."""
        if provider_name in self.providers:
            self.current_provider = provider_name
    
    def enable_failover(self, enabled: bool = True):
        """Enable or disable automatic failover."""
        self._failover_enabled = enabled
    
    def get_provider(self, name: str) -> Optional[DAProvider]:
        """Get a provider by name."""
        return self.providers.get(name)
    
    def get_current_provider(self) -> DAProvider:
        """Get the current active provider."""
        return self.providers[self.current_provider]
    
    def check_all_health(self) -> Dict[str, HealthStatus]:
        """Check health of all providers."""
        for name, provider in self.providers.items():
            self.health_cache[name] = provider.get_health()
        return self.health_cache
    
    def get_latest_block(self) -> Optional[BlockInfo]:
        """
        Get latest block from current provider.
        Falls back to other providers if failover is enabled.
        """
        # Try current provider first
        provider = self.providers[self.current_provider]
        block = provider.get_latest_block()
        
        if block:
            return block
        
        # Failover if enabled
        if self._failover_enabled:
            for name in self.provider_order:
                if name == self.current_provider:
                    continue
                
                provider = self.providers[name]
                block = provider.get_latest_block()
                
                if block:
                    # Switch to working provider
                    self.current_provider = name
                    return block
        
        return None
    
    def list_providers(self) -> List[Dict[str, Any]]:
        """List all available providers with status."""
        result = []
        for name in self.provider_order:
            provider = self.providers[name]
            health = self.health_cache.get(name)
            
            result.append({
                "name": name,
                "network": provider.network,
                "rpc_url": provider.rpc_url,
                "is_current": name == self.current_provider,
                "status": health.status.value if health else "unknown",
                "latency_ms": health.latency_ms if health else None
            })
        
        return result


# Convenience function
def create_provider_manager() -> ProviderManager:
    """Create a provider manager with all default providers."""
    return ProviderManager()
