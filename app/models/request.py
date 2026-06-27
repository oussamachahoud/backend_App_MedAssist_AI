"""
app/models/request.py
Pydantic / FastAPI request models for the V6.0 prediction endpoint.
The endpoint accepts multipart/form-data: image file + 7 clinical metadata fields.

V6.0 metadata features (matching training notebook 02):
    age                 — numeric, required
    sex                 — SexLabel enum (mapped to binary gender in preprocessing)
    localization        — BodyRegion enum (kept for API compatibility, not fed to model)
    grew                — bool, was the lesion growing?
    bleed               — bool, does the lesion bleed?
    diameter_1          — float, largest lesion diameter in cm
    skin_cancer_history — bool, prior skin cancer history?
    elevation           — bool, is the lesion elevated?
"""

from typing import Optional
from pydantic import BaseModel, Field, field_validator

from app.models.schemas import BodyRegion, SexLabel


class PatientMetadata(BaseModel):
    """
    Full set of clinical features for V6.0 inference.
    Only `age` is required; all other fields are optional (will be imputed if absent).
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
        description="Patient biological sex (male / female / unknown)",
        examples=["male"],
    )
    localization: BodyRegion = Field(
        default=BodyRegion.UNKNOWN,
        description="Anatomical site of the lesion (informational, not fed to V6.0 model)",
        examples=["back"],
    )
    grew: Optional[bool] = Field(
        default=None,
        description="Was the lesion growing? (True/False)",
        examples=[False],
    )
    bleed: Optional[bool] = Field(
        default=None,
        description="Does the lesion bleed? (True/False)",
        examples=[False],
    )
    diameter_1: Optional[float] = Field(
        default=None,
        ge=0,
        le=50,
        description="Largest lesion diameter in cm (0–50)",
        examples=[1.2],
    )
    skin_cancer_history: Optional[bool] = Field(
        default=None,
        description="Prior personal skin cancer history? (True/False)",
        examples=[False],
    )
    elevation: Optional[bool] = Field(
        default=None,
        description="Is the lesion elevated / raised? (True/False)",
        examples=[True],
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
    Helper model that mirrors the Form fields received in POST /predict.
    FastAPI parses these directly from the multipart form — not JSON body.
    """

    age: float = Field(..., ge=0, le=120)
    sex: SexLabel = Field(default=SexLabel.UNKNOWN)
    localization: BodyRegion = Field(default=BodyRegion.UNKNOWN)
    grew: Optional[bool] = Field(default=None)
    bleed: Optional[bool] = Field(default=None)
    diameter_1: Optional[float] = Field(default=None, ge=0, le=50)
    skin_cancer_history: Optional[bool] = Field(default=None)
    elevation: Optional[bool] = Field(default=None)
    patient_id: Optional[str] = Field(default=None, max_length=64)
