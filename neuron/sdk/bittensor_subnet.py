"""
VAMS Neuron - Bittensor Subnet SDK
==================================
Real integration with Bittensor decentralized AI network.

Features:
- Subtensor chain connectivity
- Subnet registration and querying
- Metagraph inspection
- Inference requests via subnet miners
- TAO balance and staking info

Requires:
- bittensor package: pip install bittensor
- Wallet with TAO for transactions

Usage:
    from sdk.bittensor_subnet import BittensorSubnet
    
    bt = BittensorSubnet(network="test")
    
    # Get subnet info
    info = bt.get_subnet_info(1)  # Subnet 1 (Text)
    
    # Query metagraph
    miners = bt.get_active_miners(1)
"""

import time
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from enum import Enum

# Try to import bittensor, will fail gracefully if not installed
BITTENSOR_AVAILABLE = False
try:
    import bittensor as bt
    BITTENSOR_AVAILABLE = True
except ImportError:
    bt = None


class BittensorNetwork(Enum):
    """Bittensor network endpoints."""
    MAINNET = "finney"
    TESTNET = "test"
    LOCAL = "local"


@dataclass
class SubnetInfo:
    """Information about a Bittensor subnet."""
    netuid: int
    name: str
    emission: float
    validators: int
    miners: int
    registration_cost: float
    updated_at: float
    
    def to_dict(self) -> dict:
        return {
            "netuid": self.netuid,
            "name": self.name,
            "emission": self.emission,
            "validators": self.validators,
            "miners": self.miners,
            "registration_cost": self.registration_cost,
            "updated_at": self.updated_at
        }


@dataclass
class MinerInfo:
    """Information about a subnet miner."""
    uid: int
    hotkey: str
    coldkey: str
    stake: float
    trust: float
    consensus: float
    incentive: float
    emission: float
    active: bool
    
    def to_dict(self) -> dict:
        return {
            "uid": self.uid,
            "hotkey": self.hotkey[:16] + "..." if self.hotkey else "",
            "stake": self.stake,
            "trust": self.trust,
            "consensus": self.consensus,
            "incentive": self.incentive,
            "emission": self.emission,
            "active": self.active
        }


@dataclass
class InferenceResult:
    """Result from a subnet inference request."""
    success: bool
    response: Any
    miner_uid: int
    latency_ms: float
    error: Optional[str] = None


# Known subnet names
SUBNET_NAMES = {
    1: "Text Prompting (Subnet 1)",
    2: "Machine Translation",
    3: "Data Scraping",
    4: "Multi-Modal",
    5: "Open-Kaito (Research)",
    6: "Nous Research",
    7: "Storage (FileTao)",
    8: "Proprietary Trading",
    9: "Pre-Training (BT-Pretraining)",
    11: "Transcription",
    13: "Dataverse (Data)",
    14: "LLM Defender",
    18: "Cortex.t (Vision)",
    19: "Vision/Image",
    21: "FileTao (Storage)",
    22: "Meta Search",
    23: "Social Tensor",
    24: "BitAgent (Agents)",
    25: "Protein Folding"
}


class BittensorSubnet:
    """
    Bittensor Subnet SDK for VAMS Neuron.
    
    Implements Layer 2 Compute operations per ARCHITECTURE_v0-3-0.md:
    - Connect to Bittensor network
    - Query subnet metagraphs
    - Submit inference requests
    - Monitor emissions and incentives
    
    Key subnets for VAMS agents:
    - SN1: Text/Reasoning
    - SN18: Vision 
    - SN24: BitAgent (Agent coordination)
    """
    
    def __init__(
        self,
        network: str = "test",
        wallet_name: Optional[str] = None,
        wallet_hotkey: Optional[str] = None
    ):
        """
        Initialize Bittensor SDK client.
        
        Args:
            network: Network to connect to (finney, test, local)
            wallet_name: Optional wallet name for transactions
            wallet_hotkey: Optional hotkey name
        """
        self.network = network
        self.wallet_name = wallet_name
        self.wallet_hotkey = wallet_hotkey
        
        self._subtensor = None
        self._wallet = None
        self._metagraph_cache: Dict[int, Any] = {}
        
        if BITTENSOR_AVAILABLE:
            self._init_subtensor()
    
    def _init_subtensor(self):
        """Initialize subtensor connection."""
        try:
            self._subtensor = bt.subtensor(network=self.network)
            
            if self.wallet_name:
                self._wallet = bt.wallet(
                    name=self.wallet_name,
                    hotkey=self.wallet_hotkey or "default"
                )
        except Exception as e:
            print(f"[WARN] Could not initialize subtensor: {e}")
            self._subtensor = None
    
    @property
    def is_connected(self) -> bool:
        """Check if connected to subtensor."""
        return self._subtensor is not None
    
    def get_block_number(self) -> int:
        """Get current block number from subtensor chain."""
        if not self._subtensor:
            return 0
        try:
            return self._subtensor.block
        except Exception:
            return 0
    
    def get_subnet_info(self, netuid: int) -> Optional[SubnetInfo]:
        """
        Get information about a specific subnet.
        
        Args:
            netuid: Subnet ID (1, 2, 3, etc.)
            
        Returns:
            SubnetInfo or None if not found
        """
        if not self._subtensor:
            # Return mock data when not connected
            return self._mock_subnet_info(netuid)
        
        try:
            # Get subnet hyperparameters
            subnet = self._subtensor.get_subnet_hyperparameters(netuid)
            metagraph = self._subtensor.metagraph(netuid)
            
            return SubnetInfo(
                netuid=netuid,
                name=SUBNET_NAMES.get(netuid, f"Subnet {netuid}"),
                emission=float(subnet.emission_value) if hasattr(subnet, 'emission_value') else 0.0,
                validators=len([n for n in metagraph.validator_permit if n]),
                miners=metagraph.n.item(),
                registration_cost=float(self._subtensor.burn(netuid).tao),
                updated_at=time.time()
            )
        except Exception as e:
            print(f"[WARN] Could not get subnet {netuid} info: {e}")
            return self._mock_subnet_info(netuid)
    
    def _mock_subnet_info(self, netuid: int) -> SubnetInfo:
        """Return mock subnet info for demo/testing."""
        return SubnetInfo(
            netuid=netuid,
            name=SUBNET_NAMES.get(netuid, f"Subnet {netuid}"),
            emission=0.05,
            validators=100,
            miners=500,
            registration_cost=0.1,
            updated_at=time.time()
        )
    
    def get_metagraph(self, netuid: int, refresh: bool = False) -> Optional[Any]:
        """
        Get metagraph for a subnet (cached).
        
        Args:
            netuid: Subnet ID
            refresh: Force refresh of cached data
            
        Returns:
            Metagraph object or None
        """
        if not self._subtensor:
            return None
        
        if refresh or netuid not in self._metagraph_cache:
            try:
                self._metagraph_cache[netuid] = self._subtensor.metagraph(netuid)
            except Exception:
                return None
        
        return self._metagraph_cache.get(netuid)
    
    def get_active_miners(self, netuid: int, min_stake: float = 0.0) -> List[MinerInfo]:
        """
        Get list of active miners on a subnet.
        
        Args:
            netuid: Subnet ID
            min_stake: Minimum stake to filter by
            
        Returns:
            List of MinerInfo
        """
        metagraph = self.get_metagraph(netuid)
        
        if not metagraph:
            # Return mock data
            return self._mock_miners(netuid)
        
        miners = []
        try:
            for uid in range(metagraph.n.item()):
                stake = float(metagraph.S[uid].item())
                if stake >= min_stake:
                    miners.append(MinerInfo(
                        uid=uid,
                        hotkey=str(metagraph.hotkeys[uid]),
                        coldkey=str(metagraph.coldkeys[uid]),
                        stake=stake,
                        trust=float(metagraph.T[uid].item()),
                        consensus=float(metagraph.C[uid].item()),
                        incentive=float(metagraph.I[uid].item()),
                        emission=float(metagraph.E[uid].item()),
                        active=bool(metagraph.active[uid].item())
                    ))
        except Exception as e:
            print(f"[WARN] Error getting miners: {e}")
            return self._mock_miners(netuid)
        
        return miners
    
    def _mock_miners(self, netuid: int) -> List[MinerInfo]:
        """Return mock miner data for demo/testing."""
        return [
            MinerInfo(
                uid=i,
                hotkey=f"5{'x'*47}",
                coldkey=f"5{'y'*47}",
                stake=100.0 + i * 10,
                trust=0.8,
                consensus=0.75,
                incentive=0.01,
                emission=0.001,
                active=True
            )
            for i in range(5)
        ]
    
    def get_balance(self, address: Optional[str] = None) -> float:
        """
        Get TAO balance for an address.
        
        Args:
            address: SS58 address (uses wallet if not provided)
            
        Returns:
            Balance in TAO
        """
        if not self._subtensor:
            return 0.0
        
        try:
            if address:
                balance = self._subtensor.get_balance(address)
            elif self._wallet:
                balance = self._subtensor.get_balance(
                    self._wallet.coldkeypub.ss58_address
                )
            else:
                return 0.0
            
            return float(balance.tao) if hasattr(balance, 'tao') else float(balance)
        except Exception as e:
            print(f"[WARN] Could not get balance: {e}")
            return 0.0
    
    def query_miner(
        self, 
        netuid: int, 
        uid: int, 
        prompt: str,
        timeout: float = 30.0
    ) -> InferenceResult:
        """
        Send inference request to a specific miner.
        
        Args:
            netuid: Subnet ID
            uid: Miner UID
            prompt: Input prompt for inference
            timeout: Request timeout
            
        Returns:
            InferenceResult with response or error
        """
        start = time.time()
        
        if not self._subtensor or not self._wallet:
            return InferenceResult(
                success=False,
                response=None,
                miner_uid=uid,
                latency_ms=(time.time() - start) * 1000,
                error="Not connected or no wallet configured"
            )
        
        try:
            metagraph = self.get_metagraph(netuid)
            if not metagraph:
                raise Exception("Could not get metagraph")
            
            # Get miner's axon info
            axon = metagraph.axons[uid]
            
            # Create dendrite for querying
            dendrite = bt.dendrite(wallet=self._wallet)
            
            # This is simplified - real implementation depends on subnet protocol
            # Each subnet has its own synapse type
            response = dendrite.query(
                axon,
                bt.Synapse(prompt=prompt),
                timeout=timeout
            )
            
            latency = (time.time() - start) * 1000
            
            return InferenceResult(
                success=True,
                response=response,
                miner_uid=uid,
                latency_ms=latency
            )
            
        except Exception as e:
            return InferenceResult(
                success=False,
                response=None,
                miner_uid=uid,
                latency_ms=(time.time() - start) * 1000,
                error=str(e)
            )
    
    def check_health(self) -> dict:
        """
        Check Bittensor network health and connectivity.
        
        Returns:
            Health status dict
        """
        start = time.time()
        
        if not BITTENSOR_AVAILABLE:
            return {
                "status": "unavailable",
                "latency_ms": 0,
                "error": "bittensor package not installed",
                "network": self.network
            }
        
        if not self._subtensor:
            return {
                "status": "offline",
                "latency_ms": (time.time() - start) * 1000,
                "error": "Could not connect to subtensor",
                "network": self.network
            }
        
        try:
            block = self.get_block_number()
            latency = (time.time() - start) * 1000
            
            return {
                "status": "healthy",
                "latency_ms": latency,
                "block": block,
                "network": self.network,
                "wallet": self.wallet_name or "none"
            }
            
        except Exception as e:
            return {
                "status": "degraded",
                "latency_ms": (time.time() - start) * 1000,
                "error": str(e)[:100],
                "network": self.network
            }
    
    def list_subnets(self) -> List[SubnetInfo]:
        """
        List all available subnets.
        
        Returns:
            List of SubnetInfo for all active subnets
        """
        subnets = []
        
        # Known active subnets
        known_netuids = [1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 13, 14, 18, 19, 21, 22, 23, 24, 25]
        
        for netuid in known_netuids:
            info = self.get_subnet_info(netuid)
            if info:
                subnets.append(info)
        
        return subnets


def check_bittensor_health(network: str = "test") -> dict:
    """Quick health check for Bittensor network."""
    subnet = BittensorSubnet(network=network)
    return subnet.check_health()


if __name__ == "__main__":
    print("VAMS Bittensor Subnet SDK")
    print("=" * 40)
    
    bt_sdk = BittensorSubnet(network="test")
    health = bt_sdk.check_health()
    
    print(f"Status: {health['status']}")
    print(f"Network: {health['network']}")
    
    if health['status'] == 'healthy':
        print(f"Block: {health.get('block', 'N/A')}")
        
        # Get SN1 info
        sn1 = bt_sdk.get_subnet_info(1)
        if sn1:
            print(f"\nSubnet 1: {sn1.name}")
            print(f"  Miners: {sn1.miners}")
            print(f"  Validators: {sn1.validators}")
