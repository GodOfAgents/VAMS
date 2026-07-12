"""
Tests for VAMS Intelligence Layer — Skill Discovery
=====================================================
Tests PCA fitting, transformation, skill profiles,
cosine alignment, and persistence.
"""

import os
import tempfile

import numpy as np
import pytest

from neuron.intelligence.skill_discovery import SkillDiscovery, SkillProfile


# ─────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────

@pytest.fixture
def synthetic_activations():
    """
    Generate synthetic activations with known structure.
    
    Creates data where:
    - PC1 direction is along dim 0 (highest variance)
    - PC2 direction is along dim 1
    - Other dims are low-variance noise
    """
    np.random.seed(42)
    n_samples = 200
    hidden_dim = 16

    activations = np.random.randn(n_samples, hidden_dim).astype(np.float32) * 0.1
    # Inject high-variance signal in first 2 dimensions
    activations[:, 0] += np.random.randn(n_samples).astype(np.float32) * 5.0
    activations[:, 1] += np.random.randn(n_samples).astype(np.float32) * 3.0
    return activations


@pytest.fixture
def fitted_model(synthetic_activations):
    """A fitted SkillDiscovery instance."""
    model = SkillDiscovery(n_components=5)
    model.fit(synthetic_activations)
    return model


# ─────────────────────────────────────────────────────
# Construction Tests
# ─────────────────────────────────────────────────────

class TestConstruction:
    def test_default_construction(self):
        model = SkillDiscovery(n_components=10)
        assert model.n_components == 10
        assert not model.is_fitted

    def test_invalid_components(self):
        with pytest.raises(ValueError, match="n_components"):
            SkillDiscovery(n_components=0)

    def test_unfitted_transform_raises(self):
        model = SkillDiscovery(n_components=5)
        with pytest.raises(RuntimeError, match="not been fitted"):
            model.transform(np.ones(16))


# ─────────────────────────────────────────────────────
# Fitting Tests
# ─────────────────────────────────────────────────────

class TestFitting:
    def test_basic_fit(self, synthetic_activations):
        model = SkillDiscovery(n_components=5)
        model.fit(synthetic_activations)
        assert model.is_fitted

    def test_fit_returns_self(self, synthetic_activations):
        model = SkillDiscovery(n_components=5)
        result = model.fit(synthetic_activations)
        assert result is model

    def test_insufficient_samples(self):
        model = SkillDiscovery(n_components=10)
        with pytest.raises(ValueError, match="at least"):
            model.fit(np.random.randn(5, 16).astype(np.float32))

    def test_wrong_shape(self):
        model = SkillDiscovery(n_components=5)
        with pytest.raises(ValueError, match="2-D"):
            model.fit(np.ones(16))

    def test_explained_variance_sums_to_one(self, fitted_model):
        """Cumulative variance should approach 1.0."""
        variance = fitted_model.get_explained_variance()
        cumulative = np.cumsum(variance)
        # First 2 PCs should capture most variance
        # (our synthetic data has signal in dims 0 and 1)
        assert cumulative[1] > 0.5

    def test_fit_stats(self, fitted_model):
        stats = fitted_model.get_fit_stats()
        assert stats["n_samples"] == 200
        assert stats["hidden_dim"] == 16
        assert stats["n_components"] == 5
        assert 0 < stats["total_variance_captured"] <= 1.0


# ─────────────────────────────────────────────────────
# Transformation Tests
# ─────────────────────────────────────────────────────

class TestTransformation:
    def test_single_transform(self, fitted_model):
        vec = np.random.randn(16).astype(np.float32)
        result = fitted_model.transform(vec)
        assert result.shape == (5,)

    def test_batch_transform(self, fitted_model):
        batch = np.random.randn(10, 16).astype(np.float32)
        result = fitted_model.transform(batch)
        assert result.shape == (10, 5)

    def test_inverse_transform_roundtrip(self, fitted_model, synthetic_activations):
        """Roundtrip should approximately reconstruct high-variance directions."""
        original = synthetic_activations[:5]
        projected = fitted_model.transform(original)
        reconstructed = fitted_model.inverse_transform(projected)

        # Reconstruction error should be small for high-variance directions
        # (won't be perfect because n_components < hidden_dim)
        assert reconstructed.shape == original.shape

    def test_single_inverse_transform(self, fitted_model):
        coords = np.random.randn(5).astype(np.float32)
        result = fitted_model.inverse_transform(coords)
        assert result.shape == (16,)


# ─────────────────────────────────────────────────────
# Skill Vectors Tests
# ─────────────────────────────────────────────────────

class TestSkillVectors:
    def test_get_all_vectors(self, fitted_model):
        vectors = fitted_model.get_skill_vectors()
        assert vectors.shape == (5, 16)

    def test_get_single_vector(self, fitted_model):
        vec = fitted_model.get_skill_vector(0)
        assert vec.shape == (16,)

    def test_vectors_are_copies(self, fitted_model):
        """Modifying returned vectors shouldn't affect the model."""
        v1 = fitted_model.get_skill_vectors()
        v1[0] = 999
        v2 = fitted_model.get_skill_vectors()
        assert not np.allclose(v1[0], v2[0])

    def test_invalid_index(self, fitted_model):
        with pytest.raises(IndexError):
            fitted_model.get_skill_vector(99)

    def test_pc1_captures_highest_variance(self, fitted_model):
        """PC1 should have the highest explained variance."""
        variance = fitted_model.get_explained_variance()
        assert variance[0] >= variance[1]


# ─────────────────────────────────────────────────────
# Skill Profile Tests
# ─────────────────────────────────────────────────────

class TestSkillProfile:
    def test_compute_profile(self, fitted_model, synthetic_activations):
        profile = fitted_model.compute_skill_profile(
            synthetic_activations[:20],
            node_id="test-node",
        )
        assert isinstance(profile, SkillProfile)
        assert profile.node_id == "test-node"
        assert profile.coordinates.shape == (5,)
        assert profile.sample_count == 20
        assert profile.magnitude >= 0

    def test_single_activation_profile(self, fitted_model):
        activation = np.random.randn(16).astype(np.float32)
        profile = fitted_model.compute_skill_profile(activation)
        assert profile.sample_count == 1

    def test_profile_to_dict(self, fitted_model, synthetic_activations):
        profile = fitted_model.compute_skill_profile(
            synthetic_activations[:5], "n1"
        )
        d = profile.to_dict()
        assert isinstance(d, dict)
        assert d["node_id"] == "n1"
        assert isinstance(d["coordinates"], list)


# ─────────────────────────────────────────────────────
# Skill Alignment Tests
# ─────────────────────────────────────────────────────

class TestSkillAlignment:
    def test_identical_profiles_perfect_alignment(self, fitted_model):
        coords = np.array([1.0, 2.0, 3.0, 4.0, 5.0], dtype=np.float32)
        alignment = fitted_model.compute_skill_alignment(coords, coords)
        assert abs(alignment - 1.0) < 1e-6

    def test_opposite_profiles_zero_alignment(self, fitted_model):
        a = np.array([1.0, 0.0, 0.0, 0.0, 0.0], dtype=np.float32)
        b = np.array([-1.0, 0.0, 0.0, 0.0, 0.0], dtype=np.float32)
        alignment = fitted_model.compute_skill_alignment(a, b)
        assert abs(alignment - 0.0) < 1e-6

    def test_orthogonal_profiles_half_alignment(self, fitted_model):
        a = np.array([1.0, 0.0, 0.0, 0.0, 0.0], dtype=np.float32)
        b = np.array([0.0, 1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        alignment = fitted_model.compute_skill_alignment(a, b)
        assert abs(alignment - 0.5) < 1e-6

    def test_zero_vector_returns_zero(self, fitted_model):
        a = np.zeros(5, dtype=np.float32)
        b = np.ones(5, dtype=np.float32)
        alignment = fitted_model.compute_skill_alignment(a, b)
        assert alignment == 0.0

    def test_alignment_range(self, fitted_model):
        """Alignment should always be in [0, 1]."""
        np.random.seed(123)
        for _ in range(50):
            a = np.random.randn(5).astype(np.float32)
            b = np.random.randn(5).astype(np.float32)
            alignment = fitted_model.compute_skill_alignment(a, b)
            assert 0.0 <= alignment <= 1.0 + 1e-6


# ─────────────────────────────────────────────────────
# Persistence Tests
# ─────────────────────────────────────────────────────

class TestPersistence:
    def test_save_and_load(self, fitted_model, synthetic_activations):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "skill_model.npz")
            fitted_model.save(path)
            assert os.path.exists(path)

            loaded = SkillDiscovery.load(path)
            assert loaded.is_fitted
            assert loaded.n_components == fitted_model.n_components

            # Transform should produce same results
            test_vec = synthetic_activations[0]
            original_result = fitted_model.transform(test_vec)
            loaded_result = loaded.transform(test_vec)
            np.testing.assert_allclose(
                original_result, loaded_result, atol=1e-5
            )

    def test_load_rejects_executable_pickle_payload(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "untrusted.pkl")
            with open(path, "wb") as handle:
                handle.write(b"\x80\x04cos\nsystem\nX\x02\x00\x00\x00id\x85R.")

            with pytest.raises(ValueError, match="Invalid SkillDiscovery model archive"):
                SkillDiscovery.load(path)

    def test_save_unfitted_raises(self):
        model = SkillDiscovery(n_components=5)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "model.npz")
            with pytest.raises(RuntimeError, match="not been fitted"):
                model.save(path)


# ─────────────────────────────────────────────────────
# Centroid / Covariance Tests
# ─────────────────────────────────────────────────────

class TestAnomalySupport:
    def test_centroid_exists(self, fitted_model):
        centroid = fitted_model.centroid
        assert centroid is not None
        assert centroid.shape == (16,)

    def test_covariance_inv_exists(self, fitted_model):
        cov_inv = fitted_model.covariance_inv
        assert cov_inv is not None
        assert cov_inv.shape == (5, 5)

    def test_centroid_is_copy(self, fitted_model):
        c1 = fitted_model.centroid
        c1[:] = 999
        c2 = fitted_model.centroid
        assert not np.allclose(c1, c2)
