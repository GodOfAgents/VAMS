"""
VAMS Neuron - Compute Provider Abstraction Layer (Layer 2)
==========================================================
Modular provider system for decentralized compute networks.

Supported Providers:
- io.net - GPU Clusters (H100/A100) - requires auth
- Akash - Supercloud (Kubernetes/Docker) - public REST API
- Render - Visual AI / GPU Rendering - requires auth
- Bittensor - Intelligence-as-a-Service (Subnets) - TaoStats API
"""

import time
import requests
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum


class ComputeStatus(Enum):
    """Health status of a compute provider."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


@dataclass
class ComputeInfo:
    """Information from a compute provider."""
    provider: str
    status: ComputeStatus
    capacity: Optional[Dict[str, Any]] = None
    latency_ms: float = 0
    error: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "status": self.status.value,
            "capacity": self.capacity,
            "latency_ms": self.latency_ms,
            "error": self.error,
            "timestamp": self.timestamp
        }


@dataclass
class BittensorSubnetInfo:
    """Information about a Bittensor subnet."""
    netuid: int
    name: str
    neurons: int
    emission: float
    tempo: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "netuid": self.netuid,
            "name": self.name,
            "neurons": self.neurons,
            "emission": self.emission,
            "tempo": self.tempo
        }


class ComputeProvider(ABC):
    """Abstract base class for compute providers."""
    
    name: str = "base"
    description: str = "Base compute provider"
    
    def __init__(self, endpoint: str, timeout: int = 15):
        self.endpoint = endpoint
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "VAMS-Neuron/0.4",
            "Accept": "application/json"
        })
    
    @abstractmethod
    def get_status(self) -> ComputeInfo:
        """Get provider status and capacity info."""
        pass


class IoNetProvider(ComputeProvider):
    """
    io.net - Decentralized GPU Clusters
    
    Note: io.net API requires authentication. 
    We check the marketing site for basic reachability.
    """
    
    name = "io.net"
    description = "GPU Clusters (H100/A100) - Auth required"
    
    def __init__(self, endpoint: str = "https://io.net", timeout: int = 15):
        super().__init__(endpoint, timeout)
    
    def get_status(self) -> ComputeInfo:
        """Check io.net reachability (API requires auth)."""
        start = time.time()
        try:
            # Just check if the main site is reachable
            response = self.session.get(
                self.endpoint,
                timeout=self.timeout
            )
            latency = (time.time() - start) * 1000
            
            if response.status_code == 200:
                return ComputeInfo(
                    provider=self.name,
                    status=ComputeStatus.HEALTHY,
                    capacity={"note": "API requires authentication"},
                    latency_ms=latency
                )
            else:
                return ComputeInfo(
                    provider=self.name,
                    status=ComputeStatus.DEGRADED,
                    latency_ms=latency,
                    error=f"Status {response.status_code}"
                )
                
        except requests.exceptions.RequestException as e:
            latency = (time.time() - start) * 1000
            return ComputeInfo(
                provider=self.name,
                status=ComputeStatus.OFFLINE,
                latency_ms=latency,
                error=str(e)[:50]
            )


class AkashProvider(ComputeProvider):
    """
    Akash Network - Decentralized Supercloud
    
    Uses Cosmos Directory REST proxy for network stats.
    """
    
    name = "akash"
    description = "Supercloud (Kubernetes/Docker)"
    
    def __init__(self, endpoint: str = "https://rest.cosmos.directory/akash", timeout: int = 15):
        super().__init__(endpoint, timeout)
    
    def get_status(self) -> ComputeInfo:
        """Query Akash network stats via Cosmos Directory."""
        start = time.time()
        try:
            # Cosmos REST API - node info
            response = self.session.get(
                f"{self.endpoint}/cosmos/base/tendermint/v1beta1/node_info",
                timeout=self.timeout
            )
            latency = (time.time() - start) * 1000
            
            if response.status_code == 200:
                data = response.json()
                node_info = data.get("default_node_info", {})
                return ComputeInfo(
                    provider=self.name,
                    status=ComputeStatus.HEALTHY,
                    capacity={
                        "network": node_info.get("network", "akashnet-2"),
                        "version": node_info.get("version", "N/A")
                    },
                    latency_ms=latency
                )
            else:
                return ComputeInfo(
                    provider=self.name,
                    status=ComputeStatus.DEGRADED,
                    latency_ms=latency,
                    error=f"Status {response.status_code}"
                )
                
        except requests.exceptions.RequestException as e:
            latency = (time.time() - start) * 1000
            return ComputeInfo(
                provider=self.name,
                status=ComputeStatus.OFFLINE,
                latency_ms=latency,
                error=str(e)[:50]
            )


class RenderProvider(ComputeProvider):
    """
    Render Network - Distributed GPU Rendering
    
    Note: Render API requires authentication.
    We check the foundation site for basic reachability.
    """
    
    name = "render"
    description = "Visual AI / GPU Rendering - Auth required"
    
    def __init__(self, endpoint: str = "https://renderfoundation.com", timeout: int = 15):
        super().__init__(endpoint, timeout)
    
    def get_status(self) -> ComputeInfo:
        """Check Render Foundation reachability."""
        start = time.time()
        try:
            response = self.session.get(
                self.endpoint,
                timeout=self.timeout
            )
            latency = (time.time() - start) * 1000
            
            if response.status_code == 200:
                return ComputeInfo(
                    provider=self.name,
                    status=ComputeStatus.HEALTHY,
                    capacity={"note": "API requires authentication"},
                    latency_ms=latency
                )
            else:
                return ComputeInfo(
                    provider=self.name,
                    status=ComputeStatus.DEGRADED,
                    latency_ms=latency,
                    error=f"Status {response.status_code}"
                )
                
        except requests.exceptions.RequestException as e:
            latency = (time.time() - start) * 1000
            return ComputeInfo(
                provider=self.name,
                status=ComputeStatus.OFFLINE,
                latency_ms=latency,
                error=str(e)[:50]
            )


class BittensorProvider(ComputeProvider):
    """
    Bittensor - The Global Brain
    
    Checks bittensor.org for reachability. Full API requires auth.
    """
    
    name = "bittensor"
    description = "Intelligence-as-a-Service (AI Subnets)"
    
    SUBNETS = {
        1: "Text Generation",
        8: "Time Series",
        18: "Vision"
    }
    
    def __init__(self, endpoint: str = "https://bittensor.org", timeout: int = 15):
        super().__init__(endpoint, timeout)
    
    def get_status(self) -> ComputeInfo:
        """Check Bittensor reachability."""
        start = time.time()
        try:
            response = self.session.get(
                self.endpoint,
                timeout=self.timeout
            )
            latency = (time.time() - start) * 1000
            
            if response.status_code == 200:
                return ComputeInfo(
                    provider=self.name,
                    status=ComputeStatus.HEALTHY,
                    capacity={
                        "subnets": "32+",
                        "network": "finney"
                    },
                    latency_ms=latency
                )
            else:
                return ComputeInfo(
                    provider=self.name,
                    status=ComputeStatus.DEGRADED,
                    latency_ms=latency,
                    error=f"Status {response.status_code}"
                )
                
        except requests.exceptions.RequestException as e:
            latency = (time.time() - start) * 1000
            return ComputeInfo(
                provider=self.name,
                status=ComputeStatus.OFFLINE,
                latency_ms=latency,
                error=str(e)[:50]
            )
    
    def get_subnet_info(self, netuid: int) -> Optional[BittensorSubnetInfo]:
        """Get info about a specific subnet."""
        try:
            response = self.session.get(
                f"{self.endpoint}/api/subnet/{netuid}",
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                return BittensorSubnetInfo(
                    netuid=netuid,
                    name=self.SUBNETS.get(netuid, f"Subnet {netuid}"),
                    neurons=data.get("neurons", 0) if isinstance(data, dict) else 256,
                    emission=data.get("emission", 0) if isinstance(data, dict) else 0,
                    tempo=data.get("tempo", 360) if isinstance(data, dict) else 360
                )
        except Exception:
            pass
        return None


class ComputeManager:
    """Manages multiple compute providers with health monitoring."""
    
    def __init__(self, providers: Optional[List[ComputeProvider]] = None):
        if providers is None:
            providers = [
                IoNetProvider(),
                AkashProvider(),
                RenderProvider(),
                BittensorProvider()
            ]
        
        self.providers: Dict[str, ComputeProvider] = {p.name: p for p in providers}
        self.status_cache: Dict[str, ComputeInfo] = {}
    
    def get_provider(self, name: str) -> Optional[ComputeProvider]:
        return self.providers.get(name)
    
    def check_all_status(self) -> Dict[str, ComputeInfo]:
        """Check status of all compute providers."""
        for name, provider in self.providers.items():
            self.status_cache[name] = provider.get_status()
        return self.status_cache
    
    def get_healthy_providers(self) -> List[str]:
        return [
            name for name, info in self.status_cache.items()
            if info.status == ComputeStatus.HEALTHY
        ]
    
    def list_providers(self) -> List[Dict[str, Any]]:
        result = []
        for name, provider in self.providers.items():
            status = self.status_cache.get(name)
            result.append({
                "name": name,
                "description": provider.description,
                "endpoint": provider.endpoint,
                "status": status.status.value if status else "unknown",
                "latency_ms": status.latency_ms if status else None
            })
        return result
    
    def get_bittensor_subnets(self) -> List[BittensorSubnetInfo]:
        bt = self.providers.get("bittensor")
        if not isinstance(bt, BittensorProvider):
            return []
        
        subnets = []
        for netuid in BittensorProvider.SUBNETS.keys():
            info = bt.get_subnet_info(netuid)
            if info:
                subnets.append(info)
        return subnets


def create_compute_manager() -> ComputeManager:
    """Create a compute manager with all default providers."""
    return ComputeManager()
