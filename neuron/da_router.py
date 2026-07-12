import hashlib
import time
import random
from enum import Enum
from neuron.verifiers.celestia_light_client import CelestiaLightClient
from neuron.verifiers.polygon_dac_client import PolygonDACClient

try:
    from neuron.config import MOCK_MODE
except ImportError:
    try:
        from config import MOCK_MODE
    except ImportError:
        MOCK_MODE = True

# --- DA Providers ---
class DAProvider(Enum):
    POLYGON = "polygon"
    CELESTIA = "celestia"
    NEAR = "near"
    AVAIL = "avail"

# --- Configuration ---
DA_CONFIG = {
    DAProvider.POLYGON: {"cost": 0.001, "latency_ms": 2000, "reliability": 0.99},
    DAProvider.CELESTIA: {"cost": 0.005, "latency_ms": 12000, "reliability": 0.999}, # Higher latency (block time)
    DAProvider.NEAR: {"cost": 0.0001, "latency_ms": 1000, "reliability": 0.95},
    DAProvider.AVAIL: {"cost": 0.003, "latency_ms": 20000, "reliability": 0.99}
}

class DARouter:
    def __init__(self):
        self.da_mode = "validium" # Default for CDK L3
        self.primary_da = DAProvider.POLYGON
        self.fallback_da = DAProvider.CELESTIA
        
        # Initialize Verifiers
        self.celestia_client = CelestiaLightClient()
        self.polygon_client = PolygonDACClient()
        
    def route_data(self, data: bytes, criticality: str = "medium") -> dict:
        """
        Routes data to the optimal DA layer based on criticality.
        
        Args:
            data: The payload to store.
            criticality: "low" (gaming), "medium" (agent logs), "high" (value transfer).
            
        Returns:
            dict: { "provider": str, "tx_hash": str, "cost": float, "verified": bool }
        """
        print(f"[DARouter] Routing {len(data)} bytes (Criticality: {criticality})...")
        
        # 1. Select Provider
        selected_provider = self._select_provider(criticality)
        print(f"[DARouter] Selected Provider: {selected_provider.value}")
        
        # 2. Attempt Submission (Simulation)
        try:
            receipt = self._submit_to_da(selected_provider, data)
            return receipt
        except Exception as e:
            print(f"[DARouter] ⚠️ Primary DA ({selected_provider.value}) failed: {e}")
            print(f"[DARouter] 🔄 Initiating Fallback to {self.fallback_da.value}...")
            # Fallback
            return self._submit_to_da(self.fallback_da, data)

    def _select_provider(self, criticality: str) -> DAProvider:
        if criticality == "high":
            # High value = Security priority = Celestia or Polygon (if reliable)
            return DAProvider.CELESTIA
        elif criticality == "low":
            # Low value = Speed/Cost priority = Near
            return DAProvider.NEAR
        else:
            # Medium = Default L3 state = Polygon DA
            return self.primary_da

    def _submit_to_da(self, provider: DAProvider, data: bytes) -> dict:
        # Simulate Network Call
        # In production this calls specific clients in `neuron/verifiers/`
        
        # Simulate Random Failure for fallback testing if MOCK_MODE is enabled
        # This branch injects non-security-critical failures in mock mode only.
        if MOCK_MODE and random.random() < 0.1:  # nosec B311
            raise Exception("Network Timeout (Simulated via MOCK_MODE)")
        
        tx_hash = hashlib.sha256(data + str(time.time()).encode()).hexdigest()
        
        # Verification Logic (DAS)
        verified = self._verify_availability(provider, tx_hash)
        
        return {
            "provider": provider.value,
            "tx_hash": "0x" + tx_hash,
            "cost": DA_CONFIG[provider]["cost"],
            "verified": verified
        }

    def _verify_availability(self, provider: DAProvider, tx_hash: str) -> bool:
        """
        Performs DAS or DAC verification.
        """
        if provider == DAProvider.CELESTIA:
            return self._verify_celestia_das(tx_hash)
        elif provider == DAProvider.POLYGON:
            return self._verify_polygon_dac(tx_hash)
        else:
            return True # Optimistic for others

    def _verify_celestia_das(self, tx_hash: str) -> bool:
        return self.celestia_client.sample_availability(tx_hash)

    def _verify_polygon_dac(self, tx_hash: str) -> bool:
        # Mock signatures for simulation
        mock_signatures = ["0xSig1...", "0xSig2..."] 
        return self.polygon_client.verify_signatures(tx_hash, mock_signatures)

# --- Usage Example ---
if __name__ == "__main__":
    router = DARouter()
    
    # 1. Critical Transaction (Asset Transfer)
    router.route_data(b"Transfer 100 VAMS", criticality="high")
    
    # 2. Standard Log (Agent Memory)
    router.route_data(b"Agent thought: I am alive", criticality="medium")
    
    # 3. Game State (Player Move)
    router.route_data(b"Player moved to (10, 20)", criticality="low")
