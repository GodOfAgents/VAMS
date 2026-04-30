"""
Tests for VAMS Intelligence Layer — Activation Cache
=====================================================
Tests the ring buffer, thread safety, serialization, and
batch operations of the ActivationCache.
"""

import os
import tempfile
import threading

import numpy as np
import pytest

from neuron.intelligence.activation_cache import (
    ActivationCache,
    ActivationMetadata,
)


# ─────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────

@pytest.fixture
def small_cache():
    """A small cache for unit tests."""
    return ActivationCache(buffer_size=10, hidden_dim=8)


@pytest.fixture
def populated_cache():
    """A cache with 5 entries."""
    cache = ActivationCache(buffer_size=10, hidden_dim=8)
    for i in range(5):
        vec = np.ones(8, dtype=np.float32) * (i + 1)
        cache.append(vec, ActivationMetadata(node_id=f"node-{i}"))
    return cache


# ─────────────────────────────────────────────────────
# Construction Tests
# ─────────────────────────────────────────────────────

class TestCacheConstruction:
    def test_default_construction(self):
        cache = ActivationCache(buffer_size=100, hidden_dim=64)
        assert cache.count == 0
        assert cache.buffer_size == 100
        assert cache.hidden_dim == 64
        assert not cache.is_full

    def test_invalid_buffer_size(self):
        with pytest.raises(ValueError, match="buffer_size"):
            ActivationCache(buffer_size=0, hidden_dim=8)

    def test_invalid_hidden_dim(self):
        with pytest.raises(ValueError, match="hidden_dim"):
            ActivationCache(buffer_size=10, hidden_dim=0)

    def test_stats_initial(self, small_cache):
        stats = small_cache.get_stats()
        assert stats["count"] == 0
        assert stats["utilization_pct"] == 0.0
        assert stats["total_appended"] == 0
        assert stats["total_overwrites"] == 0
        assert stats["memory_mb"] >= 0


# ─────────────────────────────────────────────────────
# Append Tests
# ─────────────────────────────────────────────────────

class TestAppend:
    def test_single_append(self, small_cache):
        vec = np.random.randn(8).astype(np.float32)
        idx = small_cache.append(vec)
        assert idx == 0
        assert small_cache.count == 1

    def test_multiple_appends(self, small_cache):
        for i in range(5):
            small_cache.append(np.ones(8) * i)
        assert small_cache.count == 5

    def test_ring_buffer_wraps(self, small_cache):
        """When buffer is full, oldest entries are overwritten."""
        for i in range(15):  # 15 > buffer_size=10
            small_cache.append(np.ones(8) * i)

        assert small_cache.count == 10
        assert small_cache.is_full

        # Most recent entries should be 5..14
        activations = small_cache.get_activations()
        assert activations.shape == (10, 8)
        # The most recent (last) should be 14
        np.testing.assert_allclose(activations[-1], np.ones(8) * 14)
        # The oldest (first) should be 5
        np.testing.assert_allclose(activations[0], np.ones(8) * 5)

    def test_wrong_dimension_raises(self, small_cache):
        with pytest.raises(ValueError, match="dim"):
            small_cache.append(np.ones(16))  # hidden_dim=8 expected

    def test_2d_input_raises(self, small_cache):
        with pytest.raises(ValueError, match="1-D"):
            small_cache.append(np.ones((2, 8)))

    def test_metadata_auto_timestamp(self, small_cache):
        small_cache.append(np.ones(8))
        entries = small_cache.get_activation_with_metadata()
        assert len(entries) == 1
        assert entries[0][1].timestamp > 0

    def test_metadata_preserved(self, small_cache):
        meta = ActivationMetadata(
            node_id="test-node",
            task_type="gpu_benchmark",
            model_id="llama-8b",
        )
        small_cache.append(np.ones(8), meta)
        entries = small_cache.get_activation_with_metadata()
        assert entries[0][1].node_id == "test-node"
        assert entries[0][1].task_type == "gpu_benchmark"


# ─────────────────────────────────────────────────────
# Batch Tests
# ─────────────────────────────────────────────────────

class TestBatch:
    def test_batch_append(self, small_cache):
        batch = np.random.randn(5, 8).astype(np.float32)
        count = small_cache.append_batch(batch)
        assert count == 5
        assert small_cache.count == 5

    def test_batch_wrong_dim(self, small_cache):
        with pytest.raises(ValueError, match="dim"):
            small_cache.append_batch(np.ones((5, 16)))

    def test_batch_1d_raises(self, small_cache):
        with pytest.raises(ValueError, match="2-D"):
            small_cache.append_batch(np.ones(8))

    def test_batch_metadata_length_mismatch(self, small_cache):
        batch = np.ones((3, 8))
        meta = [ActivationMetadata()] * 2  # 2 != 3
        with pytest.raises(ValueError, match="metadata_list"):
            small_cache.append_batch(batch, meta)


# ─────────────────────────────────────────────────────
# Read Tests
# ─────────────────────────────────────────────────────

class TestRead:
    def test_get_all(self, populated_cache):
        activations = populated_cache.get_activations()
        assert activations.shape == (5, 8)

    def test_get_n(self, populated_cache):
        activations = populated_cache.get_activations(n=3)
        assert activations.shape == (3, 8)
        # Most recent 3 are values 3, 4, 5
        np.testing.assert_allclose(activations[-1], np.ones(8) * 5)

    def test_get_n_exceeds_count(self, populated_cache):
        activations = populated_cache.get_activations(n=100)
        assert activations.shape == (5, 8)  # Only 5 available

    def test_get_empty(self, small_cache):
        activations = small_cache.get_activations()
        assert activations.shape == (0, 8)

    def test_chronological_order(self, populated_cache):
        """Activations should be returned oldest-first."""
        activations = populated_cache.get_activations()
        for i in range(5):
            np.testing.assert_allclose(activations[i], np.ones(8) * (i + 1))

    def test_returns_copy(self, populated_cache):
        """Returned array should be a copy, not a view."""
        a1 = populated_cache.get_activations()
        a2 = populated_cache.get_activations()
        a1[0] = 999
        assert not np.allclose(a1[0], a2[0])


# ─────────────────────────────────────────────────────
# Serialization Tests
# ─────────────────────────────────────────────────────

class TestSerialization:
    def test_export_and_load(self, populated_cache):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test_cache.npz")
            populated_cache.export(path)

            assert os.path.exists(path)

            loaded = ActivationCache.load(path)
            assert loaded.count == 5
            assert loaded.hidden_dim == 8

            original = populated_cache.get_activations()
            reloaded = loaded.get_activations()
            np.testing.assert_allclose(original, reloaded)

    def test_export_empty_warns(self, small_cache, caplog):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "empty.npz")
            small_cache.export(path)
            # Empty cache export should still succeed


# ─────────────────────────────────────────────────────
# Thread Safety Tests
# ─────────────────────────────────────────────────────

class TestThreadSafety:
    def test_concurrent_appends(self):
        """Multiple threads appending simultaneously should not corrupt data."""
        cache = ActivationCache(buffer_size=1000, hidden_dim=8)
        errors = []

        def writer(thread_id: int, n: int):
            try:
                for i in range(n):
                    vec = np.ones(8) * (thread_id * 1000 + i)
                    cache.append(vec)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=writer, args=(t, 100))
            for t in range(4)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert cache.count == 400  # 4 threads × 100 appends


# ─────────────────────────────────────────────────────
# Clear Tests
# ─────────────────────────────────────────────────────

class TestClear:
    def test_clear_resets(self, populated_cache):
        populated_cache.clear()
        assert populated_cache.count == 0
        activations = populated_cache.get_activations()
        assert activations.shape == (0, 8)

    def test_clear_allows_reuse(self, populated_cache):
        populated_cache.clear()
        populated_cache.append(np.ones(8) * 42)
        assert populated_cache.count == 1
        activations = populated_cache.get_activations()
        np.testing.assert_allclose(activations[0], np.ones(8) * 42)


# ─────────────────────────────────────────────────────
# Statistics Tests
# ─────────────────────────────────────────────────────

class TestStatistics:
    def test_overwrite_tracking(self):
        cache = ActivationCache(buffer_size=5, hidden_dim=4)
        for i in range(8):
            cache.append(np.ones(4) * i)

        stats = cache.get_stats()
        assert stats["total_appended"] == 8
        assert stats["total_overwrites"] == 3  # 8 - 5
        assert stats["utilization_pct"] == 100.0
