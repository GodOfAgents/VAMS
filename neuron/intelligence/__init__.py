"""
VAMS Intelligence Layer — AUTOSKILL Integration
================================================
Implements model-native skill discovery, activation-space anomaly
detection, and inference-time steering based on the AUTOSKILL
methodology (PCA on final-layer hidden states).

Modules:
    - activation_cache: Ring-buffer capture of model activations
    - skill_discovery: PCA-based skill direction extraction
    - anomaly_detector: Activation-space anomaly scoring
    - steering_engine: Inference-time activation bias injection

Architecture Reference:
    - AUTOSKILL Paper: "Characterizing Model-Native Skills"
    - VAMS Phase 4, Intelligence Layer
"""

__version__ = "0.1.0"
