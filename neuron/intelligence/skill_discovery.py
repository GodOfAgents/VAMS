"""
VAMS Intelligence Layer — Skill Discovery
===========================================
PCA-based extraction of orthogonal model-native skill directions
from cached activation vectors.

Each principal component represents a "model-native skill" axis —
a direction in activation space along which the model's behavior
varies most. These directions can be used for:

    1. Data selection: Choosing training examples that maximally
       exercise specific skills (Section 3.1 of AUTOSKILL paper)
    2. Inference-time steering: Biasing activations along skill
       directions to enhance specific capabilities (Section 3.2)
    3. Anomaly detection: Measuring deviation from the learned
       activation manifold (Section 4)

Key Findings from AUTOSKILL Paper:
    - PC1 typically captures 'symbolic calculus derivations' vs.
      'conceptual discrete reasoning'
    - Model-native skills outperform human heuristics by 3-11%
      on downstream SFT benchmarks
    - 1k pilot fine-tuning samples sufficient to identify useful PCs

Usage:
    discovery = SkillDiscovery(n_components=10)
    discovery.fit(activations)  # (N, hidden_dim) array
    
    # Get skill directions (principal components)
    skills = discovery.get_skill_vectors()
    
    # Project a new activation onto skill space
    skill_coords = discovery.transform(activation)
    
    # Compute skill profile for a node
    profile = discovery.compute_skill_profile(node_activations)

Architecture Reference:
    - AUTOSKILL Paper, Section 2: Method
    - VAMS Phase 4, Intelligence Layer
"""

from __future__ import annotations

import logging
import os
import pickle
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from sklearn.decomposition import IncrementalPCA

logger = logging.getLogger("VAMS-SkillDiscovery")


@dataclass
class SkillProfile:
    """
    A node's skill profile: its activation footprint projected
    onto the discovered skill axes.

    Used by the Composer's CandidateScorer to compute
    skill-alignment scores between blueprints and nodes.
    """
    node_id: str
    coordinates: np.ndarray          # Shape: (n_components,)
    magnitude: float = 0.0          # L2 norm of the projection
    dominant_skill: int = 0         # Index of the strongest PC
    sample_count: int = 0           # How many activations were averaged
    timestamp: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "coordinates": self.coordinates.tolist(),
            "magnitude": round(self.magnitude, 6),
            "dominant_skill": self.dominant_skill,
            "sample_count": self.sample_count,
        }


class SkillDiscovery:
    """
    Discovers model-native skill directions via PCA on activation
    vectors.

    Uses IncrementalPCA from scikit-learn for memory-efficient
    streaming compatibility — can fit on large activation datasets
    without loading everything into memory.

    The fitted model persists as a .pkl file for reuse across
    sessions.
    """

    def __init__(
        self,
        n_components: int = 10,
        variance_threshold: float = 0.90,
        batch_size: int = 256,
    ):
        """
        Args:
            n_components: Number of principal components to extract.
            variance_threshold: Cumulative explained variance threshold
                               for automatic component selection.
            batch_size: Batch size for IncrementalPCA fitting.
        """
        if n_components < 1:
            raise ValueError(f"n_components must be >= 1, got {n_components}")

        self._n_components = n_components
        self._variance_threshold = variance_threshold
        self._batch_size = batch_size

        self._pca: Optional[IncrementalPCA] = None
        self._is_fitted: bool = False
        self._hidden_dim: int = 0

        # Cached centroid of the training data (for anomaly detection)
        self._centroid: Optional[np.ndarray] = None
        self._covariance_inv: Optional[np.ndarray] = None

        # Fitting statistics
        self._fit_stats: Dict[str, Any] = {}

    # ──────────────────────────────────────────────────
    # Public API — Fitting
    # ──────────────────────────────────────────────────

    def fit(self, activations: np.ndarray) -> "SkillDiscovery":
        """
        Fit PCA on activation data to discover skill directions.

        Args:
            activations: 2-D array of shape (n_samples, hidden_dim).
                        Minimum n_samples = n_components.

        Returns:
            self (for chaining)

        Raises:
            ValueError: If insufficient samples or wrong shape.
        """
        activations = np.asarray(activations, dtype=np.float32)

        if activations.ndim != 2:
            raise ValueError(
                f"Expected 2-D array, got shape {activations.shape}"
            )

        n_samples, hidden_dim = activations.shape

        if n_samples < self._n_components:
            raise ValueError(
                f"Need at least {self._n_components} samples, "
                f"got {n_samples}"
            )

        self._hidden_dim = hidden_dim

        # Cap n_components to min(n_samples, hidden_dim)
        effective_components = min(
            self._n_components, n_samples, hidden_dim
        )

        logger.info(
            f"Fitting SkillDiscovery: {n_samples} samples, "
            f"hidden_dim={hidden_dim}, "
            f"n_components={effective_components}"
        )

        # Fit IncrementalPCA
        self._pca = IncrementalPCA(
            n_components=effective_components,
            batch_size=self._batch_size,
        )
        self._pca.fit(activations)
        self._is_fitted = True

        # Cache centroid and inverse covariance for anomaly detection
        self._centroid = activations.mean(axis=0)

        # Compute inverse covariance in PCA space for Mahalanobis distance
        projected = self._pca.transform(activations)
        cov = np.cov(projected, rowvar=False)
        # Regularize to avoid singular matrix
        cov += np.eye(cov.shape[0]) * 1e-6
        self._covariance_inv = np.linalg.inv(cov)

        # Record statistics
        explained = self._pca.explained_variance_ratio_
        cumulative = np.cumsum(explained)
        n_above_threshold = int(
            np.searchsorted(cumulative, self._variance_threshold) + 1
        )

        self._fit_stats = {
            "n_samples": n_samples,
            "hidden_dim": hidden_dim,
            "n_components": effective_components,
            "explained_variance_ratio": explained.tolist(),
            "cumulative_variance": cumulative.tolist(),
            "components_for_threshold": min(
                n_above_threshold, effective_components
            ),
            "total_variance_captured": float(cumulative[-1]),
        }

        logger.info(
            f"Skill Discovery fitted: "
            f"{effective_components} components, "
            f"total variance captured: {cumulative[-1]:.4f}, "
            f"components for {self._variance_threshold:.0%} threshold: "
            f"{n_above_threshold}"
        )

        return self

    # ──────────────────────────────────────────────────
    # Public API — Transformation
    # ──────────────────────────────────────────────────

    def transform(self, activations: np.ndarray) -> np.ndarray:
        """
        Project activation(s) onto the discovered skill space.

        Args:
            activations: Shape (hidden_dim,) for single vector,
                        or (n_samples, hidden_dim) for batch.

        Returns:
            Skill-space coordinates of shape (n_components,)
            or (n_samples, n_components).
        """
        self._check_fitted()
        activations = np.asarray(activations, dtype=np.float32)

        if activations.ndim == 1:
            activations = activations.reshape(1, -1)
            return self._pca.transform(activations).squeeze(0)

        return self._pca.transform(activations)

    def inverse_transform(self, coordinates: np.ndarray) -> np.ndarray:
        """
        Reconstruct activation vectors from skill-space coordinates.

        Useful for understanding what each skill direction represents
        in the original activation space.
        """
        self._check_fitted()
        coordinates = np.asarray(coordinates, dtype=np.float32)

        if coordinates.ndim == 1:
            coordinates = coordinates.reshape(1, -1)
            return self._pca.inverse_transform(coordinates).squeeze(0)

        return self._pca.inverse_transform(coordinates)

    # ──────────────────────────────────────────────────
    # Public API — Skill Vectors & Profiles
    # ──────────────────────────────────────────────────

    def get_skill_vectors(self) -> np.ndarray:
        """
        Get the principal component vectors (skill directions).

        Returns:
            2-D array of shape (n_components, hidden_dim).
            Each row is a unit direction in activation space.
        """
        self._check_fitted()
        return self._pca.components_.copy()

    def get_skill_vector(self, index: int) -> np.ndarray:
        """
        Get a single skill direction vector.

        Args:
            index: Skill index (0 = highest variance PC).

        Returns:
            1-D array of shape (hidden_dim,).
        """
        self._check_fitted()
        if index < 0 or index >= self._pca.n_components_:
            raise IndexError(
                f"Skill index {index} out of range "
                f"[0, {self._pca.n_components_ - 1}]"
            )
        return self._pca.components_[index].copy()

    def get_explained_variance(self) -> np.ndarray:
        """
        Get the explained variance ratio for each component.

        Returns:
            1-D array of shape (n_components,).
        """
        self._check_fitted()
        return self._pca.explained_variance_ratio_.copy()

    def compute_skill_profile(
        self,
        activations: np.ndarray,
        node_id: str = "",
    ) -> SkillProfile:
        """
        Compute a node's skill profile from its activations.

        Averages the skill-space projections across all activations
        to produce a stable skill fingerprint.

        Args:
            activations: (n_samples, hidden_dim) array from a node.
            node_id: Identifier for the node.

        Returns:
            SkillProfile with averaged coordinates.
        """
        self._check_fitted()
        activations = np.asarray(activations, dtype=np.float32)

        if activations.ndim == 1:
            activations = activations.reshape(1, -1)

        projected = self.transform(activations)
        mean_coords = projected.mean(axis=0)
        magnitude = float(np.linalg.norm(mean_coords))
        dominant = int(np.argmax(np.abs(mean_coords)))

        return SkillProfile(
            node_id=node_id,
            coordinates=mean_coords,
            magnitude=magnitude,
            dominant_skill=dominant,
            sample_count=activations.shape[0],
        )

    def compute_skill_alignment(
        self,
        profile_a: np.ndarray,
        profile_b: np.ndarray,
    ) -> float:
        """
        Compute cosine similarity between two skill profiles.

        Used by the Composer to score how well a node's skill
        profile matches a blueprint's required skill vector.

        Args:
            profile_a: Skill-space coordinates (n_components,).
            profile_b: Skill-space coordinates (n_components,).

        Returns:
            Cosine similarity in [-1.0, 1.0], remapped to [0.0, 1.0].
        """
        a = np.asarray(profile_a, dtype=np.float32)
        b = np.asarray(profile_b, dtype=np.float32)

        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)

        if norm_a < 1e-8 or norm_b < 1e-8:
            return 0.0

        cosine_sim = float(np.dot(a, b) / (norm_a * norm_b))
        # Remap from [-1, 1] to [0, 1]
        return (cosine_sim + 1.0) / 2.0

    # ──────────────────────────────────────────────────
    # Public API — Anomaly Support
    # ──────────────────────────────────────────────────

    @property
    def centroid(self) -> Optional[np.ndarray]:
        """Get the centroid of the fitted activation data."""
        return self._centroid.copy() if self._centroid is not None else None

    @property
    def covariance_inv(self) -> Optional[np.ndarray]:
        """Get the inverse covariance matrix in PCA space."""
        return (
            self._covariance_inv.copy()
            if self._covariance_inv is not None
            else None
        )

    # ──────────────────────────────────────────────────
    # Public API — Persistence
    # ──────────────────────────────────────────────────

    def save(self, path: str) -> str:
        """
        Save the fitted model to disk.

        Args:
            path: File path (should end in .pkl).

        Returns:
            Absolute path of the saved file.
        """
        self._check_fitted()

        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)

        state = {
            "pca": self._pca,
            "centroid": self._centroid,
            "covariance_inv": self._covariance_inv,
            "hidden_dim": self._hidden_dim,
            "n_components": self._n_components,
            "variance_threshold": self._variance_threshold,
            "fit_stats": self._fit_stats,
        }

        with open(path, "wb") as f:
            pickle.dump(state, f, protocol=pickle.HIGHEST_PROTOCOL)

        abs_path = os.path.abspath(path)
        logger.info(f"SkillDiscovery model saved to {abs_path}")
        return abs_path

    @classmethod
    def load(cls, path: str) -> "SkillDiscovery":
        """
        Load a fitted model from disk.

        Args:
            path: Path to the .pkl file.

        Returns:
            A fitted SkillDiscovery instance.
        """
        # SkillDiscovery loads trusted local model artifacts only.
        with open(path, "rb") as f:
            state = pickle.load(f)  # nosec B301

        instance = cls(
            n_components=state["n_components"],
            variance_threshold=state["variance_threshold"],
        )
        instance._pca = state["pca"]
        instance._centroid = state["centroid"]
        instance._covariance_inv = state["covariance_inv"]
        instance._hidden_dim = state["hidden_dim"]
        instance._fit_stats = state["fit_stats"]
        instance._is_fitted = True

        logger.info(
            f"SkillDiscovery model loaded from {path} "
            f"(hidden_dim={instance._hidden_dim}, "
            f"components={instance._n_components})"
        )
        return instance

    # ──────────────────────────────────────────────────
    # Public API — Statistics
    # ──────────────────────────────────────────────────

    @property
    def is_fitted(self) -> bool:
        """Whether the model has been fitted."""
        return self._is_fitted

    @property
    def n_components(self) -> int:
        """Number of principal components."""
        return self._n_components

    def get_fit_stats(self) -> Dict[str, Any]:
        """Get fitting statistics."""
        return {**self._fit_stats}

    # ──────────────────────────────────────────────────
    # Internal
    # ──────────────────────────────────────────────────

    def _check_fitted(self) -> None:
        """Raise if the model hasn't been fitted yet."""
        if not self._is_fitted:
            raise RuntimeError(
                "SkillDiscovery has not been fitted. "
                "Call .fit(activations) first."
            )
