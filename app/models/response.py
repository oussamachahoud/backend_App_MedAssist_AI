"""
app/models/response.py
Pydantic response models returned by the API endpoints.
Updated for V2.0 to support persistent AnalysisRecords, Grad-CAM, and referral suggestions.
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from app.models.schemas import (
    BodyRegion,
    DiagnosticLabel,
    LABEL_FULL_NAME,
    RISK_COLOR,
    RiskLevel,
)


# ── Health ────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    """Response from GET /health."""

    status: str = Field(..., examples=["ok"])
    model_loaded: bool = Field(..., description="Whether the ML model is loaded and ready")
    uptime_seconds: float = Field(..., description="Seconds since the API started")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version: str = Field(..., examples=["2.0.0"])


# ── Model Info ────────────────────────────────────────────────────────────────

class ModelInfoResponse(BaseModel):
    """Response from GET /model/info."""

    model_name: str = Field(..., examples=["Multimodal Skin Lesion Classifier"])
    architecture: str = Field(..., examples=["CNN + Tabular MLP"])
    input_image_size: int = Field(..., examples=[256])
    input_channels: int = Field(default=3, examples=[3])
    tabular_features: List[str] = Field(
        default=["age", "sex", "grew", "bleed", "diameter_1", "skin_cancer_history", "elevation"],
        description="Tabular feature names fed to the model",
    )
    diagnostic_classes: Dict[str, str] = Field(
        ...,
        description="Mapping of class code → full name",
        examples=[{"NEV": "Nevus", "MEL": "Melanoma"}],
    )
    version: str = Field(..., examples=["2.0.0"])
    is_loaded: bool


# ── Prediction ────────────────────────────────────────────────────────────────

class ClassProbability(BaseModel):
    """Probability for a single diagnostic class."""
    label: str = Field(..., examples=["MEL"])
    full_name: str = Field(..., examples=["Melanoma"])
    probability: float = Field(..., ge=0.0, le=1.0, examples=[0.87])


class PredictResponse(BaseModel):
    """
    Full prediction response from POST /predict.
    Contains diagnosis, confidence scores, risk assessment, timing, and V2 telemedicine hooks.
    """

    # ── Primary Prediction ────────────────────────────────
    predicted_label: DiagnosticLabel = Field(
        ...,
        description="Predicted diagnostic class code",
        examples=["MEL"],
    )
    predicted_label_full: str = Field(
        ...,
        description="Full name of predicted diagnosis",
        examples=["Melanoma"],
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence of the top prediction (softmax probability)",
        examples=[0.872],
    )

    # ── All Class Probabilities ───────────────────────────
    all_probabilities: List[ClassProbability] = Field(
        ...,
        description="Softmax probabilities for all 6 diagnostic classes",
    )

    # ── Region Prediction ─────────────────────────────────
    predicted_region: Optional[BodyRegion] = Field(
        default=None,
        description="Predicted anatomical region (if model outputs region)",
    )

    # ── Risk Assessment ───────────────────────────────────
    risk_level: RiskLevel = Field(
        ...,
        description="Clinical risk level derived from diagnosis + confidence",
        examples=["CRITICAL"],
    )
    risk_color: str = Field(
        ...,
        description="Hex color associated with risk level for UI display",
        examples=["#7c3aed"],
    )
    risk_explanation: str = Field(
        ...,
        description="Human-readable explanation of the risk level",
        examples=["Melanoma is highly malignant. Urgent referral recommended."],
    )
    recommendations: List[str] = Field(
        default=[],
        description="Clinical action recommendations based on risk level",
    )
    suggest_referral: bool = Field(
        default=False,
        description="Whether tele-dermatology specialist referral is recommended",
    )
    risk_escalated: bool = Field(
        default=False,
        description="Whether risk level was escalated due to low confidence (<50%)",
    )

    # ── V2 Telemedicine & Storage Hooks ───────────────────
    analysis_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Database UUID of the stored analysis record in PostgreSQL",
    )
    image_url: Optional[str] = Field(
        default=None,
        description="Presigned URL or object key of the uploaded dermoscopy image in MinIO",
    )
    gradcam_url: Optional[str] = Field(
        default=None,
        description="Presigned URL or object key of the generated Grad-CAM++ visualization in MinIO",
    )

    # ── Metadata ──────────────────────────────────────────
    patient_id: Optional[str] = Field(default=None, examples=["PAT-00123"])
    lesion_tag: Optional[str] = Field(default=None, examples=["Right Arm Mole"])
    inference_time_ms: float = Field(
        ...,
        description="Model inference time in milliseconds",
        examples=[34.7],
    )
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def build(
        cls,
        *,
        predicted_label: str,
        confidence: float,
        all_probs: Dict[str, float],
        risk_level: RiskLevel,
        risk_explanation: str,
        recommendations: List[str],
        inference_time_ms: float,
        predicted_region: Optional[str] = None,
        patient_id: Optional[str] = None,
        lesion_tag: Optional[str] = None,
        analysis_id: Optional[uuid.UUID] = None,
        suggest_referral: bool = False,
        risk_escalated: bool = False,
        image_url: Optional[str] = None,
        gradcam_url: Optional[str] = None,
    ) -> "PredictResponse":
        """Factory method to build a PredictResponse cleanly."""
        prob_list = [
            ClassProbability(
                label=lbl,
                full_name=LABEL_FULL_NAME.get(lbl, lbl),
                probability=round(prob, 6),
            )
            for lbl, prob in sorted(all_probs.items(), key=lambda x: -x[1])
        ]

        try:
            diag_label = DiagnosticLabel(predicted_label)
        except ValueError:
            diag_label = DiagnosticLabel.UNKNOWN

        return cls(
            predicted_label=diag_label,
            predicted_label_full=LABEL_FULL_NAME.get(predicted_label, predicted_label),
            confidence=round(confidence, 6),
            all_probabilities=prob_list,
            predicted_region=BodyRegion(predicted_region) if predicted_region else None,
            risk_level=risk_level,
            risk_color=RISK_COLOR.get(risk_level, "#64748b"),
            risk_explanation=risk_explanation,
            recommendations=recommendations,
            suggest_referral=suggest_referral,
            risk_escalated=risk_escalated,
            analysis_id=analysis_id,
            image_url=image_url,
            gradcam_url=gradcam_url,
            patient_id=patient_id,
            lesion_tag=lesion_tag,
            inference_time_ms=round(inference_time_ms, 3),
        )
