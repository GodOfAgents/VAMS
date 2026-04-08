"""
VAMS Economics Module
=====================
Regional economics, dynamic emission control, and reward distribution.

Phase 3: RegionalEconomics (geographic capacity balancing)
Phase 4: RegionAwareDECSimulator (emission allocation), RewardEngine (provider rewards)
"""
from neuron.economics.regional import RegionalEconomics
from neuron.economics.dec_regional import RegionAwareDECSimulator
from neuron.economics.reward_engine import RewardEngine

__all__ = [
    "RegionalEconomics",
    "RegionAwareDECSimulator",
    "RewardEngine",
]
