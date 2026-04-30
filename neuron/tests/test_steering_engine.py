"""
Tests for VAMS Intelligence Layer — Steering Engine
=====================================================
Tests activation steering, alpha clamping, batch operations,
multi-direction steering, and impact estimation.
"""

import numpy as np
import pytest

from neuron.intelligence.skill_discovery import SkillDiscovery
from neuron.intelligence.steering_engine import SteeringEngine


# ─────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────

@pytest.fixture
def fitted_skill_model():
    """A SkillDiscovery fitted on synthetic data."""
    np.random.seed(42)
    activations = np.random.randn(200, 16).astype(np.float32)
    activations[:, 0] += np.random.randn(200).astype(np.float32) * 5.0
    activations[:, 1] += np.random.randn(200).astype(np.float32) * 3.0

    model = SkillDiscovery(n_components=5)
    model.fit(activations)
    return model


@pytest.fixture
def engine(fitted_skill_model):
    """A SteeringEngine with default settings."""
    return SteeringEngine(fitted_skill_model, max_alpha=0.3)


# ─────────────────────────────────────────────────────
# Construction Tests
# ─────────────────────────────────────────────────────

class TestConstruction:
    def test_basic_construction(self, fitted_skill_model):
        engine = SteeringEngine(fitted_skill_model)
        assert engine.max_alpha == 0.3
        assert engine.n_skill_directions == 5

    def test_custom_max_alpha(self, fitted_skill_model):
        engine = SteeringEngine(fitted_skill_model, max_alpha=0.5)
        assert engine.max_alpha == 0.5

    def test_invalid_max_alpha(self, fitted_skill_model):
        with pytest.raises(ValueError, match="positive"):
            SteeringEngine(fitted_skill_model, max_alpha=-1.0)

    def test_unfitted_model_raises(self):
        model = SkillDiscovery(n_components=5)
        with pytest.raises(RuntimeError, match="fitted"):
            SteeringEngine(model)


# ─────────────────────────────────────────────────────
# Single Steering Tests
# ─────────────────────────────────────────────────────

class TestSingleSteering:
    def test_basic_steer(self, engine):
        activation = np.random.randn(16).astype(np.float32)
        steered = engine.steer(activation, skill_index=0, alpha=0.1)
        assert steered.shape == (16,)
        assert not np.allclose(steered, activation)

    def test_zero_alpha_no_change(self, engine):
        activation = np.random.randn(16).astype(np.float32)
        steered = engine.steer(activation, skill_index=0, alpha=0.0)
        np.testing.assert_allclose(steered, activation, atol=1e-6)

    def test_opposite_alpha_reverses(self, engine):
        activation = np.random.randn(16).astype(np.float32)
        pos = engine.steer(activation, skill_index=0, alpha=0.2)
        neg = engine.steer(activation, skill_index=0, alpha=-0.2)

        # The difference between pos and neg should be 2 * alpha * v
        diff = pos - neg
        assert np.linalg.norm(diff) > 0

    def test_invalid_skill_index(self, engine):
        activation = np.random.randn(16).astype(np.float32)
        with pytest.raises(IndexError):
            engine.steer(activation, skill_index=99, alpha=0.1)

    def test_wrong_shape_raises(self, engine):
        with pytest.raises(ValueError, match="1-D"):
            engine.steer(np.ones((2, 16)), skill_index=0, alpha=0.1)


# ─────────────────────────────────────────────────────
# Alpha Clamping Tests
# ─────────────────────────────────────────────────────

class TestAlphaClamping:
    def test_alpha_clamped_high(self, engine):
        activation = np.random.randn(16).astype(np.float32)
        # alpha=1.0 should be clamped to 0.3
        steered_clamped = engine.steer(activation, skill_index=0, alpha=1.0)
        steered_max = engine.steer(activation, skill_index=0, alpha=0.3)
        np.testing.assert_allclose(steered_clamped, steered_max, atol=1e-6)

    def test_alpha_clamped_low(self, engine):
        activation = np.random.randn(16).astype(np.float32)
        # alpha=-1.0 should be clamped to -0.3
        steered_clamped = engine.steer(activation, skill_index=0, alpha=-1.0)
        steered_min = engine.steer(activation, skill_index=0, alpha=-0.3)
        np.testing.assert_allclose(steered_clamped, steered_min, atol=1e-6)


# ─────────────────────────────────────────────────────
# Batch Steering Tests
# ─────────────────────────────────────────────────────

class TestBatchSteering:
    def test_batch_steer(self, engine):
        activations = np.random.randn(10, 16).astype(np.float32)
        steered = engine.steer_batch(activations, skill_index=0, alpha=0.1)
        assert steered.shape == (10, 16)

    def test_batch_vs_individual(self, engine):
        np.random.seed(99)
        activations = np.random.randn(5, 16).astype(np.float32)
        batch = engine.steer_batch(activations, skill_index=1, alpha=0.2)

        for i in range(5):
            individual = engine.steer(activations[i], skill_index=1, alpha=0.2)
            np.testing.assert_allclose(batch[i], individual, atol=1e-5)

    def test_batch_wrong_shape(self, engine):
        with pytest.raises(ValueError, match="2-D"):
            engine.steer_batch(np.ones(16), skill_index=0, alpha=0.1)


# ─────────────────────────────────────────────────────
# Multi-Direction Steering Tests
# ─────────────────────────────────────────────────────

class TestMultiSteering:
    def test_multi_steer(self, engine):
        activation = np.random.randn(16).astype(np.float32)
        spec = [
            {"skill_index": 0, "alpha": 0.1},
            {"skill_index": 1, "alpha": 0.2},
        ]
        steered = engine.steer_multi(activation, spec)
        assert steered.shape == (16,)
        assert not np.allclose(steered, activation)

    def test_multi_steer_empty_spec(self, engine):
        activation = np.random.randn(16).astype(np.float32)
        steered = engine.steer_multi(activation, [])
        np.testing.assert_allclose(steered, activation, atol=1e-6)

    def test_composite_vector(self, engine):
        spec = [
            {"skill_index": 0, "alpha": 0.1},
            {"skill_index": 2, "alpha": 0.15},
        ]
        vec = engine.create_composite_vector(spec)
        assert vec.shape == (16,)
        assert np.linalg.norm(vec) > 0


# ─────────────────────────────────────────────────────
# Steering Vector Tests
# ─────────────────────────────────────────────────────

class TestSteeringVector:
    def test_create_vector(self, engine):
        vec = engine.create_steering_vector(skill_index=0, alpha=0.2)
        assert vec.shape == (16,)
        # Vector should be alpha * unit_vector
        assert abs(np.linalg.norm(vec) - 0.2) < 0.01

    def test_vector_application_matches_steer(self, engine):
        """Manually adding vector should match steer()."""
        activation = np.random.randn(16).astype(np.float32)
        vec = engine.create_steering_vector(skill_index=0, alpha=0.2)
        manual = activation + vec
        steered = engine.steer(activation, skill_index=0, alpha=0.2)
        np.testing.assert_allclose(manual, steered, atol=1e-5)


# ─────────────────────────────────────────────────────
# Impact Estimation Tests
# ─────────────────────────────────────────────────────

class TestImpactEstimation:
    def test_impact_structure(self, engine):
        activation = np.random.randn(16).astype(np.float32)
        impact = engine.estimate_impact(activation, skill_index=0, alpha=0.2)

        assert "norm_change_pct" in impact
        assert "cosine_shift" in impact
        assert "projection_before" in impact
        assert "projection_after" in impact

    def test_zero_alpha_no_impact(self, engine):
        activation = np.random.randn(16).astype(np.float32)
        impact = engine.estimate_impact(activation, skill_index=0, alpha=0.0)
        assert impact["norm_change_pct"] < 0.01
        assert impact["cosine_shift"] < 1e-4

    def test_projection_increases_with_positive_alpha(self, engine):
        np.random.seed(77)
        activation = np.random.randn(16).astype(np.float32)
        impact = engine.estimate_impact(activation, skill_index=0, alpha=0.3)
        assert impact["projection_after"] > impact["projection_before"]


# ─────────────────────────────────────────────────────
# Statistics Tests
# ─────────────────────────────────────────────────────

class TestStatistics:
    def test_initial_stats(self, engine):
        stats = engine.get_stats()
        assert stats["total_steerings"] == 0

    def test_stats_after_steering(self, engine):
        activation = np.random.randn(16).astype(np.float32)
        engine.steer(activation, skill_index=0, alpha=0.1)
        engine.steer(activation, skill_index=0, alpha=0.2)
        stats = engine.get_stats()
        assert stats["total_steerings"] == 2
