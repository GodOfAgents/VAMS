"""
VAMS Gas Abstraction Premium Calculator
=======================================
Computes cost surcharges for execution traces containing compliance
and fiat-linked service blocks.
"""

from typing import List, Optional

class GasAbstractionPremiumCalculator:
    """
    Computes premium surcharge on resource consumption for compliance routing.
    Matches Tokenomics v2.0.0 specs for gas abstraction buyback-and-burn loops.
    """
    
    def __init__(self, base_premium_bps: int = 200):
        """
        Args:
            base_premium_bps: Base premium rate in basis points (default 200 BPS = 2%)
        """
        self.base_premium_bps = base_premium_bps
        
    def calculate_premium_rate(self, required_service_blocks: List[str]) -> float:
        """
        Calculate the total premium rate based on loaded service blocks.
        
        Args:
            required_service_blocks: List of active service blocks for the agent
            
        Returns:
            Premium rate as a float (e.g. 0.07 for 7%)
        """
        if not required_service_blocks:
            return 0.0
            
        bps = self.base_premium_bps
        
        # Surcharge for Coinme / Trails / compliance integrations
        if "ServiceBlock_OMS_v1" in required_service_blocks:
            bps += 500  # Add 5% premium for fiat-linked compliance rails
            
        # Surcharge for confidential enclaves
        if "tee_wrapper" in required_service_blocks:
            bps += 300  # Add 3% premium for TEE compute enclaves
            
        # Surcharge for MEV protection
        if "mev_protection" in required_service_blocks:
            bps += 200  # Add 2% premium
            
        # Cap premium rate at 15% maximum
        bps = min(bps, 1500)
        
        return bps / 10000.0

    def calculate_premium_cost(self, base_cost: float, required_service_blocks: List[str]) -> float:
        """
        Calculate the premium surcharge in tokens.
        """
        rate = self.calculate_premium_rate(required_service_blocks)
        return round(base_cost * rate, 6)
        
    def calculate_total_cost(self, base_cost: float, required_service_blocks: List[str]) -> float:
        """
        Calculate total cost (base cost + premium surcharge).
        """
        premium = self.calculate_premium_cost(base_cost, required_service_blocks)
        return round(base_cost + premium, 6)
