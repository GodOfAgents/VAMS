"""
VAMS Intelligence Layer — Activation Cache
===========================================
Hook-based extraction of final-layer hidden states from model
inference. Stores activations in a bounded ring buffer for
downstream PCA analysis and anomaly detection.

Design Constraints:
    - Non-blocking: async-safe write to buffer
    - Memory-bounded: configurable ring buffer (default 10k samples)
    - Serializable: numpy .npz export for offline PCA
    - Framework-agnostic: works with raw numpy arrays (no PyTorch dep)

Usage:
    cache = ActivationCache(buffer_size=10000, hidden_dim=4096)
    cache.append(activation_vector)
    activations = cache.get_activations(n=1000)
    cache.export("activations.npz")

Architecture Reference:
    - AUTOSKILL Paper, Section 2.2: Activation Extraction
    - VAMS Phase 4, Intelligence Layer
"""

from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger("VAMS-ActivationCache")


@dataclass
class ActivationMetadata:
    """Metadata attached to each captured activation."""
    node_id: str = ""
    task_type: str = ""          # e.g., "gpu_benchmark", "contract_audit"
    timestamp: float = 0.0
    model_id: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)


class ActivationCache:
    """
    Thread-safe ring buffer for model activation vectors.

    Stores final-layer hidden state vectors produced during model
    inference. The buffer is bounded to prevent unbounded memory
    growth — when full, the oldest entries are overwritten.

    The cache is designed to be consumed by SkillDiscovery (PCA)
    and AnomalyDetector (Mahalanobis distance).

    Thread Safety:
        All mutating operations are guarded by a threading.Lock
        to allow concurrent writes from inference threads.
    """

    def __init__(
        self,
        buffer_size: int = 10_000,
        hidden_dim: int = 4096,
    ):
        """
        Initialize the activation cache.

        Args:
            buffer_size: Maximum number of activation vectors to retain.
            hidden_dim: Dimensionality of each activation vector.
                        Must match the model's final hidden layer size.
        """
        if buffer_size < 1:
            raise ValueError(f"buffer_size must be >= 1, got {buffer_size}")
        if hidden_dim < 1:
            raise ValueError(f"hidden_dim must be >= 1, got {hidden_dim}")

        self._buffer_size = buffer_size
        self._hidden_dim = hidden_dim

        # Pre-allocate the ring buffer as a contiguous numpy array
        self._buffer: np.ndarray = np.zeros(
            (buffer_size, hidden_dim), dtype=np.float32
        )
        self._metadata: List[Optional[ActivationMetadata]] = [
            None
        ] * buffer_size

        # Ring buffer state
        self._write_idx: int = 0       # Next position to write
        self._count: int = 0           # Number of valid entries (capped at buffer_size)

        # Thread safety
        self._lock = threading.Lock()

        # Statistics
        self._total_appended: int = 0
        self._total_overwrites: int = 0

        logger.info(
            f"ActivationCache initialized: buffer_size={buffer_size}, "
            f"hidden_dim={hidden_dim}, "
            f"memory={buffer_size * hidden_dim * 4 / 1024 / 1024:.1f} MB"
        )

    # ──────────────────────────────────────────────────
    # Public API — Write
    # ──────────────────────────────────────────────────

    def append(
        self,
        activation: np.ndarray,
        metadata: Optional[ActivationMetadata] = None,
    ) -> int:
        """
        Append a single activation vector to the ring buffer.

        Args:
            activation: 1-D numpy array of shape (hidden_dim,).
            metadata: Optional metadata for this activation.

        Returns:
            The index at which the activation was stored.

        Raises:
            ValueError: If activation shape doesn't match hidden_dim.
        """
        activation = np.asarray(activation, dtype=np.float32)

        if activation.ndim != 1:
            raise ValueError(
                f"Expected 1-D activation, got shape {activation.shape}"
            )
        if activation.shape[0] != self._hidden_dim:
            raise ValueError(
                f"Activation dim {activation.shape[0]} != "
                f"expected {self._hidden_dim}"
            )

        with self._lock:
            idx = self._write_idx

            # Write activation into the ring buffer
            self._buffer[idx] = activation

            # Write metadata
            if metadata is None:
                metadata = ActivationMetadata(timestamp=time.time())
            elif metadata.timestamp == 0.0:
                metadata.timestamp = time.time()
            self._metadata[idx] = metadata

            # Advance ring buffer pointer
            if self._count == self._buffer_size:
                self._total_overwrites += 1
            else:
                self._count += 1

            self._write_idx = (idx + 1) % self._buffer_size
            self._total_appended += 1

        return idx

    def append_batch(
        self,
        activations: np.ndarray,
        metadata_list: Optional[List[ActivationMetadata]] = None,
    ) -> int:
        """
        Append a batch of activation vectors.

        Args:
            activations: 2-D array of shape (batch_size, hidden_dim).
            metadata_list: Optional list of metadata per activation.

        Returns:
            Number of activations appended.
        """
        activations = np.asarray(activations, dtype=np.float32)

        if activations.ndim != 2:
            raise ValueError(
                f"Expected 2-D batch, got shape {activations.shape}"
            )
        if activations.shape[1] != self._hidden_dim:
            raise ValueError(
                f"Activation dim {activations.shape[1]} != "
                f"expected {self._hidden_dim}"
            )

        batch_size = activations.shape[0]
        if metadata_list and len(metadata_list) != batch_size:
            raise ValueError(
                f"metadata_list length {len(metadata_list)} != "
                f"batch_size {batch_size}"
            )

        for i in range(batch_size):
            meta = metadata_list[i] if metadata_list else None
            self.append(activations[i], meta)

        return batch_size

    # ──────────────────────────────────────────────────
    # Public API — Read
    # ──────────────────────────────────────────────────

    def get_activations(
        self,
        n: Optional[int] = None,
    ) -> np.ndarray:
        """
        Get the most recent n activation vectors.

        Args:
            n: Number of most-recent activations to return.
               If None, returns all valid entries.

        Returns:
            2-D numpy array of shape (min(n, count), hidden_dim).
        """
        with self._lock:
            count = self._count
            if count == 0:
                return np.zeros((0, self._hidden_dim), dtype=np.float32)

            if n is None or n >= count:
                n = count

            # Compute indices of the n most recent entries
            # The most recent entry is at (write_idx - 1) % buffer_size
            indices = [
                (self._write_idx - 1 - i) % self._buffer_size
                for i in range(n)
            ]
            indices.reverse()  # Chronological order (oldest first)

            return self._buffer[indices].copy()

    def get_activation_with_metadata(
        self,
        n: Optional[int] = None,
    ) -> List[Tuple[np.ndarray, Optional[ActivationMetadata]]]:
        """
        Get the most recent n activations with their metadata.

        Returns:
            List of (activation_vector, metadata) tuples.
        """
        with self._lock:
            count = self._count
            if count == 0:
                return []

            if n is None or n >= count:
                n = count

            indices = [
                (self._write_idx - 1 - i) % self._buffer_size
                for i in range(n)
            ]
            indices.reverse()

            result = []
            for idx in indices:
                result.append((
                    self._buffer[idx].copy(),
                    self._metadata[idx],
                ))
            return result

    # ──────────────────────────────────────────────────
    # Public API — Persistence
    # ──────────────────────────────────────────────────

    def export(self, path: str) -> str:
        """
        Export all valid activations to a .npz file.

        Args:
            path: File path for the export (should end in .npz).

        Returns:
            The absolute path of the exported file.
        """
        activations = self.get_activations()
        if activations.shape[0] == 0:
            logger.warning("No activations to export")
            return path

        # Collect serializable metadata
        metadata_records = []
        with self._lock:
            for i in range(self._count):
                idx = (self._write_idx - self._count + i) % self._buffer_size
                meta = self._metadata[idx]
                if meta:
                    metadata_records.append({
                        "node_id": meta.node_id,
                        "task_type": meta.task_type,
                        "timestamp": meta.timestamp,
                        "model_id": meta.model_id,
                    })

        # Ensure directory exists
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)

        np.savez_compressed(
            path,
            activations=activations,
            hidden_dim=np.array([self._hidden_dim]),
            count=np.array([activations.shape[0]]),
        )

        abs_path = os.path.abspath(path)
        logger.info(
            f"Exported {activations.shape[0]} activations to {abs_path} "
            f"({os.path.getsize(abs_path) / 1024:.1f} KB)"
        )
        return abs_path

    @classmethod
    def load(cls, path: str) -> "ActivationCache":
        """
        Load activations from a .npz file into a new cache.

        Args:
            path: Path to the .npz file.

        Returns:
            A new ActivationCache populated with the loaded data.
        """
        data = np.load(path, allow_pickle=False)
        activations = data["activations"]
        hidden_dim = int(data["hidden_dim"][0])

        cache = cls(
            buffer_size=max(activations.shape[0], 1),
            hidden_dim=hidden_dim,
        )
        cache.append_batch(activations)

        logger.info(
            f"Loaded {activations.shape[0]} activations from {path} "
            f"(hidden_dim={hidden_dim})"
        )
        return cache

    # ──────────────────────────────────────────────────
    # Public API — Statistics
    # ──────────────────────────────────────────────────

    @property
    def count(self) -> int:
        """Number of valid activations in the buffer."""
        return self._count

    @property
    def buffer_size(self) -> int:
        """Maximum capacity of the ring buffer."""
        return self._buffer_size

    @property
    def hidden_dim(self) -> int:
        """Dimensionality of each activation vector."""
        return self._hidden_dim

    @property
    def is_full(self) -> bool:
        """Whether the ring buffer has wrapped around."""
        return self._count == self._buffer_size

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            memory_bytes = self._buffer.nbytes
            return {
                "buffer_size": self._buffer_size,
                "hidden_dim": self._hidden_dim,
                "count": self._count,
                "is_full": self.is_full,
                "total_appended": self._total_appended,
                "total_overwrites": self._total_overwrites,
                "memory_mb": round(memory_bytes / 1024 / 1024, 2),
                "utilization_pct": round(
                    self._count / self._buffer_size * 100, 1
                ),
            }

    def clear(self) -> None:
        """Reset the cache, zeroing all entries."""
        with self._lock:
            self._buffer[:] = 0
            self._metadata = [None] * self._buffer_size
            self._write_idx = 0
            self._count = 0
            logger.info("ActivationCache cleared")
