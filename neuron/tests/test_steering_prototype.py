"""
VAMS Intelligence Layer — Steering Engine Prototype
===================================================
Phase 4 prototype and validation tests for inference-time steering.
Measures the impact of steering on Sentinel audit tasks and 
validates safety constraints on unrelated model capabilities.
"""

import numpy as np
import pytest

from neuron.intelligence.skill_discovery import SkillDiscovery
from neuron.intelligence.steering_engine import SteeringEngine

# ─────────────────────────────────────────────────────
# Prototype Mocks & Helpers
# ─────────────────────────────────────────────────────

def sigmoid(x):
    return 1 / (1 + np.exp(-x))

class MockModelPredictor:
    """
    Simulates a language model's classification accuracy based on
    final layer hidden states (activations).
    """
    def __init__(self, task_vector: np.ndarray, threshold: float = 0.5):
        self.task_vector = task_vector / np.linalg.norm(task_vector)
        self.threshold = threshold

    def predict_accuracy(self, activations: np.ndarray) -> float:
        """Returns accuracy (0 to 1) based on alignment with task_vector."""
        # Logits are dot products with the task vector
        logits = np.dot(activations, self.task_vector)
        probs = sigmoid(logits)
        predictions = probs > self.threshold
        # Assume ground truth is True for all in this synthetic test
        # (we want to see how many "correctly" identify the target class)
        return float(np.mean(predictions))


@pytest.fixture
def environment():
    """Setup a controlled synthetic environment for prototype testing."""
    np.random.seed(42)
    hidden_dim = 64
    n_samples = 1000

    # 1. Base activations (mostly random noise)
    activations = np.random.randn(n_samples, hidden_dim).astype(np.float32)

    # 2. Inject a "Security Analysis" skill direction
    # We make feature 0 highly variance so PCA picks it as PC1 (skill 0)
    activations[:, 0] += np.random.randn(n_samples).astype(np.float32) * 2.0
    
    # 3. Inject an unrelated "Formatting" skill direction orthogonal to feature 0
    # We make feature 1 the second most variant so it's PC2 (skill 1)
    activations[:, 1] += np.random.randn(n_samples).astype(np.float32) * 1.5

    # Fit skill discovery
    skill_model = SkillDiscovery(n_components=5)
    skill_model.fit(activations)

    # Initialize Engine with max_alpha=0.5 to allow testing up to 0.5
    engine = SteeringEngine(skill_model, max_alpha=0.5)

    return {
        "activations": activations,
        "engine": engine,
        "skill_model": skill_model,
        "security_skill_idx": 0, # PC1 corresponds to feature 0
        "formatting_skill_idx": 1 # PC2 corresponds to feature 1
    }


# ─────────────────────────────────────────────────────
# Phase 4 Tasks: Measurement and Validation
# ─────────────────────────────────────────────────────

class TestSteeringPrototype:

    def test_prototype_steering_impact_on_audit_tasks(self, environment):
        """
        [Task: Prototype steering for Sentinel audit tasks]
        [Task: Measure steering impact on task accuracy (compare α=0, 0.1, 0.2, 0.5)]
        
        Demonstrates that amplifying the Security Analysis skill direction
        measurably increases the model's accuracy on security tasks.
        """
        engine: SteeringEngine = environment["engine"]
        activations = environment["activations"]
        skill_idx = environment["security_skill_idx"]
        
        # The skill model's first direction should align heavily with feature 0
        skill_vector = engine._unit_vectors[skill_idx]
        
        # Create a Mock Security Task aligned with the security skill
        security_task_vector = skill_vector.copy()
        # Add some noise to make it a realistic downstream task
        security_task_vector += np.random.randn(64) * 0.1 
        
        predictor = MockModelPredictor(security_task_vector, threshold=0.6)

        # Baseline accuracy (α=0)
        acc_0 = predictor.predict_accuracy(activations)

        # Apply steering with different alpha values
        steered_01 = engine.steer_batch(activations, skill_idx, alpha=0.1)
        acc_01 = predictor.predict_accuracy(steered_01)

        steered_02 = engine.steer_batch(activations, skill_idx, alpha=0.2)
        acc_02 = predictor.predict_accuracy(steered_02)

        steered_05 = engine.steer_batch(activations, skill_idx, alpha=0.5)
        acc_05 = predictor.predict_accuracy(steered_05)

        print(f"\nSteering Impact Results:")
        print(f"Alpha=0.0: {acc_0:.2%}")
        print(f"Alpha=0.1: {acc_01:.2%}")
        print(f"Alpha=0.2: {acc_02:.2%}")
        print(f"Alpha=0.5: {acc_05:.2%}")

        # Assert monotonically increasing accuracy as steering strength increases
        assert acc_01 > acc_0, "Alpha 0.1 should improve accuracy over baseline"
        assert acc_02 > acc_01, "Alpha 0.2 should improve accuracy over 0.1"
        assert acc_05 > acc_02, "Alpha 0.5 should improve accuracy over 0.2"

    def test_safety_validation_unrelated_capabilities(self, environment):
        """
        [Task: Safety validation: ensure steering doesn't degrade unrelated capabilities]
        
        Demonstrates that amplifying the Security Analysis skill does NOT
        degrade performance on an unrelated orthogonal task (Formatting).
        """
        engine: SteeringEngine = environment["engine"]
        activations = environment["activations"]
        security_idx = environment["security_skill_idx"]
        formatting_idx = environment["formatting_skill_idx"]

        # The unrelated task relies on a different skill direction
        formatting_skill_vector = engine._unit_vectors[formatting_idx]
        unrelated_task_vector = formatting_skill_vector.copy()
        # Add noise
        unrelated_task_vector += np.random.randn(64) * 0.1

        predictor = MockModelPredictor(unrelated_task_vector, threshold=0.5)

        # Baseline accuracy on the unrelated task
        base_acc = predictor.predict_accuracy(activations)

        # Apply aggressive steering on the *security* axis
        # Alpha=0.5 is high, we want to ensure it doesn't break formatting
        steered_activations = engine.steer_batch(activations, security_idx, alpha=0.5)
        
        # Accuracy on unrelated task after steering
        steered_acc = predictor.predict_accuracy(steered_activations)

        print(f"\nSafety Validation (Unrelated Task):")
        print(f"Baseline (alpha=0): {base_acc:.2%}")
        print(f"Steered (alpha=0.5 on Security): {steered_acc:.2%}")

        # Assert that the degradation is minimal (within 2%)
        degradation = base_acc - steered_acc
        assert degradation < 0.02, f"Unrelated capability degraded too much: {degradation:.2%} drop"

    def test_max_alpha_safety_clamp(self, environment):
        """
        Verifies that even if an adversarial agent requests catastrophic
        steering (α=10.0), the engine clamps it safely to prevent degradation.
        """
        engine: SteeringEngine = environment["engine"]
        activations = environment["activations"]
        security_idx = environment["security_skill_idx"]

        # Request crazy alpha
        steered_clamped = engine.steer_batch(activations, security_idx, alpha=10.0)
        
        # Request max safe alpha
        steered_safe = engine.steer_batch(activations, security_idx, alpha=engine.max_alpha)

        # Should be identical due to clamping
        np.testing.assert_allclose(steered_clamped, steered_safe, atol=1e-6)
