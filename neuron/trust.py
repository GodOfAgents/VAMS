"""
VAMS Neuron - Trust Provider Abstraction Layer (Layer 4)
========================================================
TEE (Trusted Execution Environment) provider monitoring.

Supported Providers:
- Phala Network - Intel SGX Enclaves (Phat Contracts)
- Marlin Oyster - AWS Nitro Enclaves (TLS termination)
- Automata Network - Multi-Prover AVS (1RPC privacy relay)
"""

import time
import requests
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum


class TrustStatus(Enum):
    """Health status of a TEE provider."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


@dataclass
class TrustInfo:
    """Information from a TEE provider."""
    provider: str
    status: TrustStatus
    technology: str
    capacity: Optional[Dict[str, Any]] = None
    latency_ms: float = 0
    error: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "status": self.status.value,
            "technology": self.technology,
            "capacity": self.capacity,
            "latency_ms": self.latency_ms,
            "error": self.error,
            "timestamp": self.timestamp
        }


class TrustProvider(ABC):
    """Abstract base class for TEE providers."""
    
    name: str = "base"
    technology: str = "unknown"
    description: str = "Base TEE provider"
    
    def __init__(self, endpoint: str, timeout: int = 15):
        self.endpoint = endpoint
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "VAMS-Neuron/0.5",
            "Accept": "text/html,application/json"
        })
    
    @abstractmethod
    def get_status(self) -> TrustInfo:
        """Get provider status."""
        pass


class PhalaProvider(TrustProvider):
    """
    Phala Network - Intel SGX Enclaves
    
    Provides confidential computing via Phat Contracts.
    Now running on Ethereum L2.
    """
    
    name = "phala"
    technology = "Intel SGX"
    description = "Phat Contracts - Private Compute"
    
    def __init__(self, endpoint: str = "https://phala.network", timeout: int = 15):
        super().__init__(endpoint, timeout)
    
    def get_status(self) -> TrustInfo:
        """Check Phala Network reachability."""
        start = time.time()
        try:
            response = self.session.get(
                self.endpoint,
                timeout=self.timeout
            )
            latency = (time.time() - start) * 1000
            
            if response.status_code == 200:
                return TrustInfo(
                    provider=self.name,
                    status=TrustStatus.HEALTHY,
                    technology=self.technology,
                    capacity={"network": "Ethereum L2"},
                    latency_ms=latency
                )
            else:
                return TrustInfo(
                    provider=self.name,
                    status=TrustStatus.DEGRADED,
                    technology=self.technology,
                    latency_ms=latency,
                    error=f"Status {response.status_code}"
                )
                
        except requests.exceptions.RequestException as e:
            latency = (time.time() - start) * 1000
            return TrustInfo(
                provider=self.name,
                status=TrustStatus.OFFLINE,
                technology=self.technology,
                latency_ms=latency,
                error=str(e)[:50]
            )


class MarlinProvider(TrustProvider):
    """
    Marlin Oyster - AWS Nitro Enclaves
    
    Provides TEE coprocessors with TLS termination.
    Bridges Web2 APIs with on-chain verification.
    """
    
    name = "marlin"
    technology = "AWS Nitro"
    description = "Oyster - TEE Coprocessors"
    
    def __init__(self, endpoint: str = "https://www.marlin.org", timeout: int = 15):
        super().__init__(endpoint, timeout)
    
    def get_status(self) -> TrustInfo:
        """Check Marlin Oyster reachability."""
        start = time.time()
        try:
            response = self.session.get(
                self.endpoint,
                timeout=self.timeout
            )
            latency = (time.time() - start) * 1000
            
            if response.status_code == 200:
                return TrustInfo(
                    provider=self.name,
                    status=TrustStatus.HEALTHY,
                    technology=self.technology,
                    capacity={"service": "Oyster Serverless"},
                    latency_ms=latency
                )
            else:
                return TrustInfo(
                    provider=self.name,
                    status=TrustStatus.DEGRADED,
                    technology=self.technology,
                    latency_ms=latency,
                    error=f"Status {response.status_code}"
                )
                
        except requests.exceptions.RequestException as e:
            latency = (time.time() - start) * 1000
            return TrustInfo(
                provider=self.name,
                status=TrustStatus.OFFLINE,
                technology=self.technology,
                latency_ms=latency,
                error=str(e)[:50]
            )


class AutomataProvider(TrustProvider):
    """
    Automata Network - Multi-Prover AVS
    
    Provides privacy-protected RPC relay (1RPC).
    On-chain TEE attestation verification.
    """
    
    name = "automata"
    technology = "Multi-Prover"
    description = "1RPC - Privacy Relay"
    
    def __init__(self, endpoint: str = "https://1rpc.io/ata", timeout: int = 15):
        super().__init__(endpoint, timeout)
    
    def get_status(self) -> TrustInfo:
        """Check Automata 1RPC reachability with eth_chainId."""
        start = time.time()
        try:
            # Query 1RPC with eth_chainId
            response = self.session.post(
                self.endpoint,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "eth_chainId",
                    "params": []
                },
                headers={"Content-Type": "application/json"},
                timeout=self.timeout
            )
            latency = (time.time() - start) * 1000
            
            if response.status_code == 200:
                data = response.json()
                if 'result' in data:
                    chain_id = int(data['result'], 16)
                    return TrustInfo(
                        provider=self.name,
                        status=TrustStatus.HEALTHY,
                        technology=self.technology,
                        capacity={"chain_id": chain_id, "service": "1RPC"},
                        latency_ms=latency
                    )
            
            return TrustInfo(
                provider=self.name,
                status=TrustStatus.DEGRADED,
                technology=self.technology,
                latency_ms=latency,
                error=f"Status {response.status_code}"
            )
                
        except requests.exceptions.RequestException as e:
            latency = (time.time() - start) * 1000
            return TrustInfo(
                provider=self.name,
                status=TrustStatus.OFFLINE,
                technology=self.technology,
                latency_ms=latency,
                error=str(e)[:50]
            )


class TrustManager:
    """Manages TEE providers with health monitoring."""
    
    def __init__(
        self, 
        providers: Optional[List[TrustProvider]] = None,
        mock_mode: bool = False
    ):
        self.mock_mode = mock_mode
        
        if providers is None:
            providers = [
                PhalaProvider(),
                MarlinProvider(),
                AutomataProvider()
            ]
        
        self.providers: Dict[str, TrustProvider] = {p.name: p for p in providers}
        self.status_cache: Dict[str, TrustInfo] = {}
    
    def get_provider(self, name: str) -> Optional[TrustProvider]:
        return self.providers.get(name)
    
    def check_all_status(self) -> Dict[str, TrustInfo]:
        """Check status of all TEE providers."""
        if self.mock_mode:
            return self._get_mock_status()
        
        for name, provider in self.providers.items():
            self.status_cache[name] = provider.get_status()
        return self.status_cache
    
    def _get_mock_status(self) -> Dict[str, TrustInfo]:
        """Return mock status for testing."""
        self.status_cache = {
            "phala": TrustInfo(
                provider="phala",
                status=TrustStatus.HEALTHY,
                technology="Intel SGX",
                capacity={"network": "mock", "mock": True},
                latency_ms=50.0
            ),
            "marlin": TrustInfo(
                provider="marlin",
                status=TrustStatus.HEALTHY,
                technology="AWS Nitro",
                capacity={"service": "mock", "mock": True},
                latency_ms=45.0
            ),
            "automata": TrustInfo(
                provider="automata",
                status=TrustStatus.HEALTHY,
                technology="Multi-Prover",
                capacity={"chain_id": 1, "mock": True},
                latency_ms=40.0
            )
        }
        return self.status_cache
    
    def get_healthy_providers(self) -> List[str]:
        return [
            name for name, info in self.status_cache.items()
            if info.status == TrustStatus.HEALTHY
        ]
    
    def list_providers(self) -> List[Dict[str, Any]]:
        result = []
        for name, provider in self.providers.items():
            status = self.status_cache.get(name)
            result.append({
                "name": name,
                "technology": provider.technology,
                "description": provider.description,
                "endpoint": provider.endpoint,
                "status": status.status.value if status else "unknown",
                "latency_ms": status.latency_ms if status else None
            })
        return result


def create_trust_manager(mock_mode: bool = False) -> TrustManager:
    """Create a trust manager with all default providers."""
    return TrustManager(mock_mode=mock_mode)

