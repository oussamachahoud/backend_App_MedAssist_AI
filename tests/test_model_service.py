"""
tests/test_model_service.py
Unit tests for risk assessment logic and preprocessing utilities.
No real model weights are required.
"""

import io

import pytest
import torch
from PIL import Image

from app.models.schemas import DiagnosticLabel, RiskLevel
from app.services.risk_assessment import calculate_risk
from app.services.preprocessing_service import build_tabular_tensor


# ── Risk Assessment Tests ─────────────────────────────────────────────────────

class TestRiskAssessment:

    @pytest.mark.parametrize("label,expected_risk", [
        (DiagnosticLabel.NEV, RiskLevel.LOW),
        (DiagnosticLabel.SEK, RiskLevel.LOW),
        (DiagnosticLabel.ACK, RiskLevel.MODERATE),
        (DiagnosticLabel.BCC, RiskLevel.HIGH),
        (DiagnosticLabel.SCC, RiskLevel.HIGH),
        (DiagnosticLabel.MEL, RiskLevel.CRITICAL),
    ])
    def test_risk_levels_high_confidence(self, label, expected_risk):
        """With high confidence (0.95), risk matches base mapping."""
        risk, explanation, recs = calculate_risk(label, confidence=0.95)
        assert risk == expected_risk

    def test_low_confidence_escalates_risk(self):
        """NEV with low confidence should escalate from LOW to MODERATE."""
        risk, explanation, recs = calculate_risk(DiagnosticLabel.NEV, confidence=0.30)
        assert risk == RiskLevel.MODERATE

    def test_low_confidence_adds_warning_recommendation(self):
        risk, explanation, recs = calculate_risk(DiagnosticLabel.ACK, confidence=0.40)
        assert any("Low model confidence" in r for r in recs)

    def test_explanation_is_string(self):
        risk, explanation, recs = calculate_risk(DiagnosticLabel.MEL, confidence=0.88)
        assert isinstance(explanation, str)
        assert len(explanation) > 0

    def test_recommendations_are_list(self):
        _, _, recs = calculate_risk(DiagnosticLabel.BCC, confidence=0.75)
        assert isinstance(recs, list)
        assert len(recs) > 0

    def test_mel_is_always_critical_high_confidence(self):
        risk, _, _ = calculate_risk(DiagnosticLabel.MEL, confidence=0.99)
        assert risk == RiskLevel.CRITICAL

    def test_mel_low_confidence_stays_critical(self):
        """MEL risk cannot be escalated beyond CRITICAL."""
        risk, _, _ = calculate_risk(DiagnosticLabel.MEL, confidence=0.10)
        assert risk == RiskLevel.CRITICAL


# ── Tabular Tensor Tests ──────────────────────────────────────────────────────

class TestBuildTabularTensor:

    def test_output_shape(self):
        tensor = build_tabular_tensor(age=45.0, sex_encoded=1.0, region_encoded=0.5)
        assert tensor.shape == (1, 3)

    def test_output_dtype_float32(self):
        tensor = build_tabular_tensor(age=30.0, sex_encoded=0.0, region_encoded=0.2)
        assert tensor.dtype == torch.float32

    def test_age_normalisation(self):
        tensor = build_tabular_tensor(age=120.0, sex_encoded=0.0, region_encoded=0.0)
        age_value = tensor[0, 0].item()
        assert abs(age_value - 1.0) < 1e-5  # 120/120 = 1.0

    def test_zero_age(self):
        tensor = build_tabular_tensor(age=0.0, sex_encoded=0.0, region_encoded=0.0)
        age_value = tensor[0, 0].item()
        assert abs(age_value - 0.0) < 1e-5

    def test_values_in_range(self):
        tensor = build_tabular_tensor(age=60.0, sex_encoded=0.5, region_encoded=0.3)
        for val in tensor[0].tolist():
            assert 0.0 <= val <= 1.0


# ── Preprocessing Tests ───────────────────────────────────────────────────────

class TestPreprocessing:
    """Tests for image preprocessing (sync parts only)."""

    def test_pil_image_to_tensor_shape(self):
        """Verify the transform pipeline produces the right tensor shape."""
        from app.services.preprocessing_service import _transform
        img = Image.new("RGB", (500, 400))
        tensor = _transform(img)
        assert tensor.shape == (3, 224, 224)

    def test_pil_image_normalised(self):
        """Verify tensor is float and normalised (can be negative after norm)."""
        from app.services.preprocessing_service import _transform
        img = Image.new("RGB", (224, 224), color=(128, 128, 128))
        tensor = _transform(img)
        assert tensor.dtype == torch.float32
        # After ImageNet normalize, values can be outside [0, 1]
        assert tensor.min() < 1.1

    def test_unsqueeze_adds_batch_dim(self):
        from app.services.preprocessing_service import _transform
        img = Image.new("RGB", (224, 224))
        tensor = _transform(img).unsqueeze(0)
        assert tensor.shape == (1, 3, 224, 224)
