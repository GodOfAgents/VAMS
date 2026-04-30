"""
Tests for VAMS Intelligence Layer — Anomaly Detector
=====================================================
Tests Mahalanobis distance scoring, adversarial classification,
batch scoring, anomaly reports, and baseline fitting.
"""

import numpy as np
import pytest

from neuron.intelligence.skill_discovery import SkillDiscovery
from neuron.intelligence.anomaly_detector import (
    ActivationAnomalyDetector,
    AnomalyReport,
)


# ─────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────

@pytest.fixture
def synthetic_data():
    """Generate synthetic normal + anomalous activations."""
    np.random.seed(42)
    hidden_dim = 16
    n_normal = 200
    n_anomalous = 10

    # Normal: centered around origin with moderate variance
    normal = np.random.randn(n_normal, hidden_dim).astype(np.float32) * 0.5
    normal[:, 0] += np.random.randn(n_normal).astype(np.float32) * 3.0
    normal[:, 1] += np.random.randn(n_normal).astype(np.float32) * 2.0

    # Anomalous: far from normal cluster
    anomalous = np.random.randn(n_anomalous, hidden_dim).astype(np.float32) * 0.5
    anomalous += 20.0  # Shift far away

    return normal, anomalous


@pytest.fixture
def fitted_skill_model(synthetic_data):
    """A SkillDiscovery fitted on normal data."""
    normal, _ = synthetic_data
    model = SkillDiscovery(n_components=5)
    model.fit(normal)
    return model


@pytest.fixture
def detector(fitted_skill_model, synthetic_data):
    """A fully configured anomaly detector."""
    normal, _ = synthetic_data
    det = ActivationAnomalyDetector(fitted_skill_model, default_threshold=3.0)
    det.fit_baseline(normal)
    return det


# ─────────────────────────────────────────────────────
# Construction Tests
# ─────────────────────────────────────────────────────

class TestConstruction:
    def test_construction(self, fitted_skill_model):
        det = ActivationAnomalyDetector(fitted_skill_model)
        assert det.default_threshold == 3.0
        # Should auto-init baseline from skill model's centroid
        assert det.is_baseline_fitted

    def test_unfitted_skill_model_raises(self):
        model = SkillDiscovery(n_components=5)
        with pytest.raises(RuntimeError, match="fitted"):
            ActivationAnomalyDetector(model)

    def test_custom_threshold(self, fitted_skill_model):
        det = ActivationAnomalyDetector(
            fitted_skill_model, default_threshold=5.0
        )
        assert det.default_threshold == 5.0


# ─────────────────────────────────────────────────────
# Baseline Fitting Tests
# ─────────────────────────────────────────────────────

class TestBaselineFitting:
    def test_fit_baseline(self, fitted_skill_model, synthetic_data):
        normal, _ = synthetic_data
        det = ActivationAnomalyDetector(fitted_skill_model)
        result = det.fit_baseline(normal)
        assert result is det
        assert det.is_baseline_fitted

    def test_insufficient_samples(self, fitted_skill_model):
        det = ActivationAnomalyDetector(fitted_skill_model)
        with pytest.raises(ValueError, match="at least 2"):
            det.fit_baseline(np.ones((1, 16), dtype=np.float32))

    def test_wrong_shape(self, fitted_skill_model):
        det = ActivationAnomalyDetector(fitted_skill_model)
        with pytest.raises(ValueError, match="2-D"):
            det.fit_baseline(np.ones(16, dtype=np.float32))


# ─────────────────────────────────────────────────────
# Scoring Tests
# ─────────────────────────────────────────────────────

class TestScoring:
    def test_normal_sample_low_score(self, detector, synthetic_data):
        """Normal samples should have low anomaly scores."""
        normal, _ = synthetic_data
        score = detector.score_anomaly(normal[0])
        assert score >= 0.0
        # Most normal samples should be within threshold
        assert score < 10.0

    def test_anomalous_sample_high_score(self, detector, synthetic_data):
        """Anomalous samples should have high anomaly scores."""
        _, anomalous = synthetic_data
        score = detector.score_anomaly(anomalous[0])
        assert score > 3.0  # Should exceed default threshold

    def test_score_non_negative(self, detector, synthetic_data):
        """Scores should always be non-negative."""
        normal, _ = synthetic_data
        for activation in normal[:20]:
            score = detector.score_anomaly(activation)
            assert score >= 0.0

    def test_wrong_shape_raises(self, detector):
        with pytest.raises(ValueError, match="1-D"):
            detector.score_anomaly(np.ones((2, 16)))


# ─────────────────────────────────────────────────────
# Batch Scoring Tests
# ─────────────────────────────────────────────────────

class TestBatchScoring:
    def test_batch_scores(self, detector, synthetic_data):
        normal, _ = synthetic_data
        scores = detector.score_anomaly_batch(normal[:10])
        assert scores.shape == (10,)
        assert np.all(scores >= 0)

    def test_batch_vs_individual(self, detector, synthetic_data):
        """Batch scores should match individual scores."""
        normal, _ = synthetic_data
        batch_scores = detector.score_anomaly_batch(normal[:5])
        for i in range(5):
            individual_score = detector.score_anomaly(normal[i])
            np.testing.assert_allclose(
                batch_scores[i], individual_score, atol=1e-4
            )


# ─────────────────────────────────────────────────────
# Classification Tests
# ─────────────────────────────────────────────────────

class TestClassification:
    def test_normal_not_adversarial(self, detector, synthetic_data):
        """Most normal samples should not be classified as adversarial."""
        normal, _ = synthetic_data
        false_positives = sum(
            detector.is_adversarial(act) for act in normal[:50]
        )
        # Allow a few false positives (< 10% of 50)
        assert false_positives < 5

    def test_anomalous_is_adversarial(self, detector, synthetic_data):
        """Anomalous samples should be classified as adversarial."""
        _, anomalous = synthetic_data
        true_positives = sum(
            detector.is_adversarial(act) for act in anomalous
        )
        # Most should be caught
        assert true_positives >= 8  # Out of 10

    def test_custom_threshold(self, detector, synthetic_data):
        """Higher threshold = fewer positives."""
        _, anomalous = synthetic_data
        strict = sum(
            detector.is_adversarial(act, threshold=100.0)
            for act in anomalous
        )
        assert strict <= sum(
            detector.is_adversarial(act, threshold=1.0)
            for act in anomalous
        )

    def test_threshold_setter(self, detector):
        detector.default_threshold = 5.0
        assert detector.default_threshold == 5.0

    def test_invalid_threshold(self, detector):
        with pytest.raises(ValueError, match="positive"):
            detector.default_threshold = -1.0


# ─────────────────────────────────────────────────────
# Anomaly Report Tests
# ─────────────────────────────────────────────────────

class TestAnomalyReport:
    def test_report_structure(self, detector, synthetic_data):
        normal, _ = synthetic_data
        report = detector.get_anomaly_report(normal[0])
        assert isinstance(report, AnomalyReport)
        assert report.mahalanobis_distance >= 0
        assert 0 <= report.anomaly_score <= 1
        assert isinstance(report.is_adversarial, bool)
        assert len(report.per_component_deviation) > 0
        assert report.reconstruction_error >= 0

    def test_report_to_dict(self, detector, synthetic_data):
        normal, _ = synthetic_data
        report = detector.get_anomaly_report(normal[0])
        d = report.to_dict()
        assert isinstance(d, dict)
        assert "mahalanobis_distance" in d
        assert "anomaly_score" in d
        assert "is_adversarial" in d

    def test_anomalous_report_flagged(self, detector, synthetic_data):
        _, anomalous = synthetic_data
        report = detector.get_anomaly_report(anomalous[0])
        assert report.is_adversarial
        assert report.anomaly_score > 0.5
