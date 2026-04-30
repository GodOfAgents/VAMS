"""
VAMS Intelligence Layer — Anomaly Detector
============================================
Activation-space anomaly detection for identifying adversarial,
jailbroken, or degraded model behavior.

Directly implements AUTOSKILL Paper Section 4 findings:
    - Jailbreak activations cluster in distinguishable subspaces
    - 32 attack types tested, all separable in activation space
    - Mahalanobis distance from normal centroid is effective

Detection Methods:
    1. Mahalanobis distance from the centroid of "normal" activations
       in PCA-projected skill space
    2. Projection magnitude onto known adversarial subspaces
    3. Per-component deviation analysis (which skill dimensions are
       most anomalous)

Usage:
    detector = ActivationAnomalyDetector(skill_model)
    detector.fit_baseline(normal_activations)
    
    # Score a new activation
    score = detector.score_anomaly(activation)
    is_bad = detector.is_adversarial(activation)
    
    # Detailed breakdown
    report = detector.get_anomaly_report(activation)

Architecture Reference:
    - AUTOSKILL Paper, Section 4: Adversarial Detection
    - VAMS Sentinel Module Integration
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np

from .skill_discovery import SkillDiscovery

logger = logging.getLogger("VAMS-AnomalyDetector")


@dataclass
class AnomalyReport:
    """Detailed anomaly analysis for a single activation."""
    mahalanobis_distance: float = 0.0
    anomaly_score: float = 0.0            # Normalized to [0, 1]
    is_adversarial: bool = False
    threshold: float = 3.0
    per_component_deviation: List[float] = field(default_factory=list)
    most_anomalous_component: int = 0
    reconstruction_error: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mahalanobis_distance": round(self.mahalanobis_distance, 6),
            "anomaly_score": round(self.anomaly_score, 6),
            "is_adversarial": self.is_adversarial,
            "threshold": self.threshold,
            "most_anomalous_component": self.most_anomalous_component,
            "reconstruction_error": round(self.reconstruction_error, 6),
        }


class ActivationAnomalyDetector:
    """
    Detects anomalous model behavior by measuring deviation from
    the learned activation manifold.

    Consumed by the Sentinel module during node audits to flag
    potentially adversarial or jailbroken model responses.

    The detector operates in PCA-projected skill space (not the
    raw high-dimensional activation space), which provides:
    - Better separation of normal vs. adversarial clusters
    - Lower computational cost (n_components << hidden_dim)
    - Robustness to noise in irrelevant dimensions
    """

    def __init__(
        self,
        skill_model: SkillDiscovery,
        default_threshold: float = 3.0,
    ):
        """
        Args:
            skill_model: A fitted SkillDiscovery instance.
            default_threshold: Default Mahalanobis distance threshold
                             for adversarial classification.
                             Based on chi-squared distribution:
                             3.0 ≈ 99.7% of normal data (3-sigma).
        """
        if not skill_model.is_fitted:
            raise RuntimeError(
                "SkillDiscovery must be fitted before creating "
                "AnomalyDetector"
            )

        self._skill_model = skill_model
        self._default_threshold = default_threshold

        # Baseline statistics (set by fit_baseline)
        self._baseline_centroid: Optional[np.ndarray] = None
        self._baseline_cov_inv: Optional[np.ndarray] = None
        self._baseline_std: Optional[np.ndarray] = None
        self._is_baseline_fitted: bool = False

        # Use the skill model's precomputed centroid and covariance if available
        if skill_model.centroid is not None:
            self._init_from_skill_model()

        logger.info(
            f"AnomalyDetector initialized: "
            f"threshold={default_threshold}, "
            f"baseline_fitted={self._is_baseline_fitted}"
        )

    def _init_from_skill_model(self) -> None:
        """
        Initialize baseline from the SkillDiscovery model's
        precomputed centroid and covariance.
        """
        centroid = self._skill_model.centroid
        cov_inv = self._skill_model.covariance_inv

        if centroid is not None and cov_inv is not None:
            # Project centroid into PCA space
            self._baseline_centroid = self._skill_model.transform(centroid)
            self._baseline_cov_inv = cov_inv
            # Estimate std from covariance diagonal
            cov_diag = np.diag(np.linalg.inv(cov_inv))
            self._baseline_std = np.sqrt(np.maximum(cov_diag, 1e-8))
            self._is_baseline_fitted = True

    # ──────────────────────────────────────────────────
    # Public API — Fitting
    # ──────────────────────────────────────────────────

    def fit_baseline(
        self,
        normal_activations: np.ndarray,
    ) -> "ActivationAnomalyDetector":
        """
        Fit the baseline from known "normal" activation vectors.

        Args:
            normal_activations: (n_samples, hidden_dim) array of
                              activations from verified-good responses.

        Returns:
            self (for chaining)
        """
        normal_activations = np.asarray(
            normal_activations, dtype=np.float32
        )

        if normal_activations.ndim != 2:
            raise ValueError(
                f"Expected 2-D array, got shape {normal_activations.shape}"
            )

        n_samples = normal_activations.shape[0]
        if n_samples < 2:
            raise ValueError(
                f"Need at least 2 samples for baseline, got {n_samples}"
            )

        # Project into PCA skill space
        projected = self._skill_model.transform(normal_activations)

        # Compute centroid in PCA space
        self._baseline_centroid = projected.mean(axis=0)

        # Compute covariance and its inverse
        cov = np.cov(projected, rowvar=False)
        if cov.ndim == 0:
            # Single component case
            cov = np.array([[cov]])
        cov += np.eye(cov.shape[0]) * 1e-6  # Regularize
        self._baseline_cov_inv = np.linalg.inv(cov)

        # Per-component standard deviation
        self._baseline_std = np.sqrt(np.maximum(np.diag(cov), 1e-8))

        self._is_baseline_fitted = True

        logger.info(
            f"Baseline fitted on {n_samples} normal activations "
            f"(projected to {projected.shape[1]} PCA dimensions)"
        )
        return self

    # ──────────────────────────────────────────────────
    # Public API — Scoring
    # ──────────────────────────────────────────────────

    def score_anomaly(self, activation: np.ndarray) -> float:
        """
        Compute anomaly score for a single activation.

        Returns the Mahalanobis distance from the baseline centroid
        in PCA-projected skill space.

        Args:
            activation: 1-D array of shape (hidden_dim,).

        Returns:
            Mahalanobis distance (higher = more anomalous).
        """
        self._check_baseline()
        activation = np.asarray(activation, dtype=np.float32)

        if activation.ndim != 1:
            raise ValueError(
                f"Expected 1-D activation, got shape {activation.shape}"
            )

        # Project into PCA space
        projected = self._skill_model.transform(activation)

        # Compute Mahalanobis distance
        diff = projected - self._baseline_centroid
        mahal_sq = float(diff @ self._baseline_cov_inv @ diff.T)

        # Handle numerical issues
        mahal_sq = max(mahal_sq, 0.0)
        return float(np.sqrt(mahal_sq))

    def score_anomaly_batch(
        self,
        activations: np.ndarray,
    ) -> np.ndarray:
        """
        Compute anomaly scores for a batch of activations.

        Args:
            activations: (n_samples, hidden_dim) array.

        Returns:
            1-D array of Mahalanobis distances.
        """
        self._check_baseline()
        activations = np.asarray(activations, dtype=np.float32)

        projected = self._skill_model.transform(activations)
        diff = projected - self._baseline_centroid

        # Vectorized Mahalanobis: sqrt(diag(diff @ Σ⁻¹ @ diff.T))
        mahal_sq = np.sum(
            (diff @ self._baseline_cov_inv) * diff, axis=1
        )
        mahal_sq = np.maximum(mahal_sq, 0.0)
        return np.sqrt(mahal_sq)

    def is_adversarial(
        self,
        activation: np.ndarray,
        threshold: Optional[float] = None,
    ) -> bool:
        """
        Classify whether an activation is adversarial.

        Args:
            activation: 1-D array of shape (hidden_dim,).
            threshold: Mahalanobis distance threshold (default: 3.0).

        Returns:
            True if the activation exceeds the threshold.
        """
        if threshold is None:
            threshold = self._default_threshold

        distance = self.score_anomaly(activation)
        return distance > threshold

    def get_anomaly_report(
        self,
        activation: np.ndarray,
        threshold: Optional[float] = None,
    ) -> AnomalyReport:
        """
        Generate a detailed anomaly analysis report.

        Args:
            activation: 1-D array of shape (hidden_dim,).
            threshold: Classification threshold.

        Returns:
            AnomalyReport with full breakdown.
        """
        self._check_baseline()

        if threshold is None:
            threshold = self._default_threshold

        activation = np.asarray(activation, dtype=np.float32)

        # Project and compute distance
        projected = self._skill_model.transform(activation)
        diff = projected - self._baseline_centroid

        # Mahalanobis distance
        mahal_sq = float(diff @ self._baseline_cov_inv @ diff.T)
        mahal_sq = max(mahal_sq, 0.0)
        mahal_dist = float(np.sqrt(mahal_sq))

        # Normalized anomaly score [0, 1] using sigmoid-like mapping
        anomaly_score = float(1.0 / (1.0 + np.exp(-0.5 * (mahal_dist - threshold))))

        # Per-component z-scores
        per_component = (
            np.abs(diff) / self._baseline_std
        ).tolist()

        # Reconstruction error (how much the PCA misses)
        reconstructed = self._skill_model.inverse_transform(projected)
        recon_error = float(
            np.linalg.norm(activation - reconstructed)
        )

        return AnomalyReport(
            mahalanobis_distance=mahal_dist,
            anomaly_score=anomaly_score,
            is_adversarial=mahal_dist > threshold,
            threshold=threshold,
            per_component_deviation=per_component,
            most_anomalous_component=int(np.argmax(np.abs(diff))),
            reconstruction_error=recon_error,
        )

    # ──────────────────────────────────────────────────
    # Public API — Accessors
    # ──────────────────────────────────────────────────

    @property
    def is_baseline_fitted(self) -> bool:
        """Whether the baseline has been established."""
        return self._is_baseline_fitted

    @property
    def default_threshold(self) -> float:
        """Current default threshold."""
        return self._default_threshold

    @default_threshold.setter
    def default_threshold(self, value: float) -> None:
        if value <= 0:
            raise ValueError(f"Threshold must be positive, got {value}")
        self._default_threshold = value

    # ──────────────────────────────────────────────────
    # Internal
    # ──────────────────────────────────────────────────

    def _check_baseline(self) -> None:
        """Raise if the baseline hasn't been fitted."""
        if not self._is_baseline_fitted:
            raise RuntimeError(
                "Baseline not fitted. Call .fit_baseline(normal_activations) "
                "or provide a SkillDiscovery model with precomputed centroid."
            )
