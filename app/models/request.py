"""
app/models/request.py
Pydantic/FastAPI request models for the prediction endpoint.
The endpoint accepts multipart/form-data: image file + patient metadata.
"""

from typing import Optional
from pydantic import BaseModel, Field, field_validator

from app.models.schemas import BodyRegion, SexLabel


class PatientMetadata(BaseModel):
    """
    Tabular features sent alongside the image.
    These are fed into the tabular branch of the multimodal model.
    """

    age: float = Field(
        ...,
        ge=0,
        le=120,
        description="Patient age in years (0–120)",
        examples=[45.0],
    )

    sex: SexLabel = Field(
        default=SexLabel.UNKNOWN,
        description="Patient biological sex",
        examples=["male"],
    )

    localization: BodyRegion = Field(
        default=BodyRegion.UNKNOWN,
        description="Anatomical site of the lesion",
        examples=["back"],
    )

    patient_id: Optional[str] = Field(
        default=None,
        max_length=64,
        description="Optional patient identifier for tracking",
        examples=["PAT-00123"],
    )

    @field_validator("age", mode="before")
    @classmethod
    def round_age(cls, v: float) -> float:
        """Round age to one decimal place."""
        return round(float(v), 1)


class PredictFormData(BaseModel):
    """
    Helper model that mirrors the Form fields received in /predict.
    FastAPI parses these directly from the multipart form — not JSON body.
    """

    age: float = Field(..., ge=0, le=120)
    sex: SexLabel = Field(default=SexLabel.UNKNOWN)
    localization: BodyRegion = Field(default=BodyRegion.UNKNOWN)
    patient_id: Optional[str] = Field(default=None, max_length=64)
