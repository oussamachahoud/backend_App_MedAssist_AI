"""
tests/test_model_service.py
Unit tests for risk assessment logic and V6.0 preprocessing utilities.
No real model weights are required.
"""

import numpy as np
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


# ── V6.0 Tabular Tensor Tests ─────────────────────────────────────────────────

class TestBuildTabularTensor:
    """Tests for the V6.0 build_tabular_tensor function."""

    def _make_tensors(self, age=45.0, present_all=True):
        """Helper to build dummy features and mask."""
        features = np.array([age, 1.0, 0.0, 0.0, 1.2, 0.0, 1.0], dtype=np.float32)
        mask     = np.ones(7, dtype=np.float32) if present_all else np.zeros(7, dtype=np.float32)
        return build_tabular_tensor(features, mask)

    def test_output_shapes(self):
        tab, mask = self._make_tensors()
        assert tab.shape  == (1, 7)
        assert mask.shape == (1, 7)

    def test_output_dtype_float32(self):
        tab, mask = self._make_tensors()
        assert tab.dtype  == torch.float32
        assert mask.dtype == torch.float32

    def test_all_present_mask(self):
        _, mask = self._make_tensors(present_all=True)
        assert mask.sum().item() == 7.0

    def test_all_missing_mask(self):
        _, mask = self._make_tensors(present_all=False)
        assert mask.sum().item() == 0.0

    def test_values_round_trip(self):
        features = np.array([52.0, 0.0, 1.0, 0.0, 2.5, 1.0, 0.0], dtype=np.float32)
        mask     = np.ones(7, dtype=np.float32)
        tab, _   = build_tabular_tensor(features, mask)
        np.testing.assert_allclose(tab.numpy()[0], features, rtol=1e-6)


# ── Preprocessing Tests ───────────────────────────────────────────────────────

class TestPreprocessing:
    """Tests for V6.0 image preprocessing (sync parts only)."""

    def test_pil_image_correct_size(self):
        """Verify the transform pipeline produces 256×256 tensors."""
        from app.services.preprocessing_service import _preprocess_numpy
        img = np.random.randint(0, 255, (256, 256, 3), dtype=np.uint8)
        tensor = _preprocess_numpy(img)
        assert tensor.shape == (3, 256, 256)

    def test_pil_image_dtype_float32(self):
        from app.services.preprocessing_service import _preprocess_numpy
        img    = np.random.randint(0, 255, (256, 256, 3), dtype=np.uint8)
        tensor = _preprocess_numpy(img)
        assert tensor.dtype == torch.float32

    def test_unsqueeze_adds_batch_dim(self):
        from app.services.preprocessing_service import _preprocess_numpy
        img    = np.random.randint(0, 255, (256, 256, 3), dtype=np.uint8)
        tensor = _preprocess_numpy(img).unsqueeze(0)
        assert tensor.shape == (1, 3, 256, 256)
