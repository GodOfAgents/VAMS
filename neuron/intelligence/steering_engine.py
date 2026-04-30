"""
VAMS Intelligence Layer — Steering Engine
===========================================
Inference-time activation-space steering for non-destructive
behavior tuning of model nodes.

Implements the AUTOSKILL Paper Section 3.2 formula:
    h_steered = h_original + α * skill_direction

Where:
    h_original  = the model's natural hidden state at a given layer
    α           = steering strength (positive amplifies, negative suppresses)
    skill_direction = a unit vector from PCA-discovered skill axes

VAMS Use Cases:
    - Enhance "logical mapping" capability for contract verification
    - Suppress "verbose reasoning" for latency-sensitive inference
    - Amplify "security analysis" for Sentinel audit tasks

Safety Constraints:
    - α is capped at MAX_ALPHA (default 0.3) to prevent
      catastrophic capability degradation
    - Steering vectors are always unit-normalized

Usage:
    engine = SteeringEngine(skill_model, max_alpha=0.3)
    
    # Create a steering vector
    vector = engine.create_steering_vector(skill_index=0, alpha=0.2)
    
    # Apply steering to an activation
    steered = engine.steer(original_activation, skill_index=0, alpha=0.2)
    
    # Batch steering
    steered_batch = engine.steer_batch(activations, skill_index=0, alpha=0.2)

Architecture Reference:
    - AUTOSKILL Paper, Section 3.2: Inference-Time Steering
    - VAMS Phase 4, Intelligence Layer
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import numpy as np

from .skill_discovery import SkillDiscovery

logger = logging.getLogger("VAMS-SteeringEngine")


class SteeringEngine:
    """
    Non-destructive inference-time activation steering.

    Applies PCA-discovered skill direction vectors as additive
    biases to model hidden states, enabling fine-grained behavioral
    control without retraining.

    Safety guarantees:
        - Alpha values are clamped to [-MAX_ALPHA, MAX_ALPHA]
        - All steering vectors are unit-normalized
        - Pre/post steering norms are tracked for drift monitoring
    """

    DEFAULT_MAX_ALPHA = 0.3

    def __init__(
        self,
        skill_model: SkillDiscovery,
        max_alpha: float = DEFAULT_MAX_ALPHA,
    ):
        """
        Args:
            skill_model: A fitted SkillDiscovery instance.
            max_alpha: Maximum allowed steering strength.
                      Paper tests α ∈ {0.1, 0.2, 0.5}.
                      Values > 0.5 risk catastrophic degradation.
        """
        if not skill_model.is_fitted:
            raise RuntimeError(
                "SkillDiscovery must be fitted before creating "
                "SteeringEngine"
            )

        if max_alpha <= 0:
            raise ValueError(f"max_alpha must be positive, got {max_alpha}")

        self._skill_model = skill_model
        self._max_alpha = max_alpha

        # Cache normalized skill vectors for efficiency
        raw_vectors = skill_model.get_skill_vectors()
        norms = np.linalg.norm(raw_vectors, axis=1, keepdims=True)
        norms = np.maximum(norms, 1e-8)
        self._unit_vectors: np.ndarray = raw_vectors / norms

        # Steering statistics
        self._steer_count: int = 0
        self._total_drift: float = 0.0

        logger.info(
            f"SteeringEngine initialized: "
            f"{self._unit_vectors.shape[0]} skill directions, "
            f"max_alpha={max_alpha}"
        )

    # ──────────────────────────────────────────────────
    # Public API — Steering
    # ──────────────────────────────────────────────────

    def steer(
        self,
        activation: np.ndarray,
        skill_index: int,
        alpha: float,
    ) -> np.ndarray:
        """
        Apply steering to a single activation vector.

        Implements: h_steered = h + α * v_skill

        Args:
            activation: 1-D array of shape (hidden_dim,).
            skill_index: Index of the skill direction (0 = PC1).
            alpha: Steering strength. Positive amplifies the skill,
                  negative suppresses it.

        Returns:
            Steered activation of shape (hidden_dim,).
        """
        activation = np.asarray(activation, dtype=np.float32)

        if activation.ndim != 1:
            raise ValueError(
                f"Expected 1-D activation, got shape {activation.shape}"
            )

        self._validate_skill_index(skill_index)
        alpha = self._clamp_alpha(alpha)

        skill_vector = self._unit_vectors[skill_index]
        steered = activation + alpha * skill_vector

        # Track drift statistics
        original_norm = float(np.linalg.norm(activation))
        steered_norm = float(np.linalg.norm(steered))
        if original_norm > 1e-8:
            drift = abs(steered_norm - original_norm) / original_norm
        else:
            drift = 0.0

        self._steer_count += 1
        self._total_drift += drift

        return steered

    def steer_batch(
        self,
        activations: np.ndarray,
        skill_index: int,
        alpha: float,
    ) -> np.ndarray:
        """
        Apply steering to a batch of activations.

        Args:
            activations: 2-D array of shape (batch_size, hidden_dim).
            skill_index: Skill direction index.
            alpha: Steering strength.

        Returns:
            Steered activations of shape (batch_size, hidden_dim).
        """
        activations = np.asarray(activations, dtype=np.float32)

        if activations.ndim != 2:
            raise ValueError(
                f"Expected 2-D array, got shape {activations.shape}"
            )

        self._validate_skill_index(skill_index)
        alpha = self._clamp_alpha(alpha)

        skill_vector = self._unit_vectors[skill_index]
        steered = activations + alpha * skill_vector[np.newaxis, :]

        self._steer_count += activations.shape[0]

        return steered

    def steer_multi(
        self,
        activation: np.ndarray,
        steering_spec: List[Dict[str, float]],
    ) -> np.ndarray:
        """
        Apply multiple steering directions simultaneously.

        Implements: h_steered = h + Σ(αᵢ * vᵢ)

        Args:
            activation: 1-D array of shape (hidden_dim,).
            steering_spec: List of dicts, each with:
                - "skill_index": int — which skill direction
                - "alpha": float — steering strength

        Returns:
            Steered activation.
        """
        activation = np.asarray(activation, dtype=np.float32).copy()

        for spec in steering_spec:
            skill_index = int(spec["skill_index"])
            alpha = float(spec["alpha"])

            self._validate_skill_index(skill_index)
            alpha = self._clamp_alpha(alpha)

            activation = activation + alpha * self._unit_vectors[skill_index]

        self._steer_count += 1
        return activation

    # ──────────────────────────────────────────────────
    # Public API — Steering Vectors
    # ──────────────────────────────────────────────────

    def create_steering_vector(
        self,
        skill_index: int,
        alpha: float,
    ) -> np.ndarray:
        """
        Create a standalone steering vector (α * v).

        Useful for pre-computing vectors that will be applied
        repeatedly during inference.

        Args:
            skill_index: Skill direction index.
            alpha: Steering strength.

        Returns:
            Steering bias vector of shape (hidden_dim,).
        """
        self._validate_skill_index(skill_index)
        alpha = self._clamp_alpha(alpha)

        return alpha * self._unit_vectors[skill_index]

    def create_composite_vector(
        self,
        steering_spec: List[Dict[str, float]],
    ) -> np.ndarray:
        """
        Create a composite steering vector from multiple directions.

        Implements: bias = Σ(αᵢ * vᵢ)

        Args:
            steering_spec: List of {"skill_index": int, "alpha": float}.

        Returns:
            Composite bias vector of shape (hidden_dim,).
        """
        hidden_dim = self._unit_vectors.shape[1]
        composite = np.zeros(hidden_dim, dtype=np.float32)

        for spec in steering_spec:
            skill_index = int(spec["skill_index"])
            alpha = float(spec["alpha"])

            self._validate_skill_index(skill_index)
            alpha = self._clamp_alpha(alpha)

            composite += alpha * self._unit_vectors[skill_index]

        return composite

    # ──────────────────────────────────────────────────
    # Public API — Analysis
    # ──────────────────────────────────────────────────

    def estimate_impact(
        self,
        activation: np.ndarray,
        skill_index: int,
        alpha: float,
    ) -> Dict[str, float]:
        """
        Estimate the impact of steering without applying it.

        Args:
            activation: 1-D array of shape (hidden_dim,).
            skill_index: Skill direction index.
            alpha: Steering strength.

        Returns:
            Dict with impact metrics:
            - norm_change_pct: % change in activation norm
            - cosine_shift: cosine distance between original and steered
            - projection_before: projection of original onto skill direction
            - projection_after: projection of steered onto skill direction
        """
        activation = np.asarray(activation, dtype=np.float32)
        self._validate_skill_index(skill_index)
        alpha = self._clamp_alpha(alpha)

        skill_vector = self._unit_vectors[skill_index]
        steered = activation + alpha * skill_vector

        orig_norm = float(np.linalg.norm(activation))
        steer_norm = float(np.linalg.norm(steered))

        norm_change = (
            abs(steer_norm - orig_norm) / max(orig_norm, 1e-8) * 100
        )

        # Cosine similarity between original and steered
        if orig_norm > 1e-8 and steer_norm > 1e-8:
            cosine_sim = float(
                np.dot(activation, steered) / (orig_norm * steer_norm)
            )
        else:
            cosine_sim = 1.0

        # Projection onto skill direction
        proj_before = float(np.dot(activation, skill_vector))
        proj_after = float(np.dot(steered, skill_vector))

        return {
            "norm_change_pct": round(norm_change, 4),
            "cosine_shift": round(1.0 - cosine_sim, 6),
            "projection_before": round(proj_before, 6),
            "projection_after": round(proj_after, 6),
        }

    # ──────────────────────────────────────────────────
    # Public API — Statistics
    # ──────────────────────────────────────────────────

    @property
    def max_alpha(self) -> float:
        """Maximum allowed steering strength."""
        return self._max_alpha

    @property
    def n_skill_directions(self) -> int:
        """Number of available skill directions."""
        return self._unit_vectors.shape[0]

    def get_stats(self) -> Dict[str, Any]:
        """Get engine statistics."""
        avg_drift = (
            self._total_drift / self._steer_count
            if self._steer_count > 0
            else 0.0
        )
        return {
            "max_alpha": self._max_alpha,
            "n_skill_directions": self.n_skill_directions,
            "total_steerings": self._steer_count,
            "avg_drift_pct": round(avg_drift * 100, 4),
        }

    # ──────────────────────────────────────────────────
    # Internal
    # ──────────────────────────────────────────────────

    def _validate_skill_index(self, index: int) -> None:
        """Validate skill direction index."""
        n = self._unit_vectors.shape[0]
        if index < 0 or index >= n:
            raise IndexError(
                f"Skill index {index} out of range [0, {n - 1}]"
            )

    def _clamp_alpha(self, alpha: float) -> float:
        """Clamp alpha to safe range."""
        clamped = max(-self._max_alpha, min(alpha, self._max_alpha))
        if abs(clamped - alpha) > 1e-8:
            logger.warning(
                f"Alpha {alpha} clamped to {clamped} "
                f"(max_alpha={self._max_alpha})"
            )
        return clamped
