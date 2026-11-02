"""
app/models/schemas.py
Shared enums and types used across request/response models.
"""

from enum import Enum


class DiagnosticLabel(str, Enum):
    """
    Six skin lesion diagnostic classes output by the model.
    Ordered from lowest to highest clinical risk.
    """
    NEV = "NEV"   # Nevus                    — benign mole
    SEK = "SEK"   # Seborrheic Keratosis     — benign growth
    ACK = "ACK"   # Actinic Keratosis        — pre-malignant
    BCC = "BCC"   # Basal Cell Carcinoma     — malignant
    SCC = "SCC"   # Squamous Cell Carcinoma  — malignant
    MEL = "MEL"   # Melanoma                 — highly malignant
    UNKNOWN = "UNKNOWN"


class DiagnosticLabelFull(str, Enum):
    """Human-readable full names for each diagnostic class."""
    NEV = "Nevus"
    SEK = "Seborrheic Keratosis"
    ACK = "Actinic Keratosis"
    BCC = "Basal Cell Carcinoma"
    SCC = "Squamous Cell Carcinoma"
    MEL = "Melanoma"
    UNKNOWN = "Unknown Lesion"


LABEL_FULL_NAME: dict[str, str] = {
    "NEV": "Nevus",
    "SEK": "Seborrheic Keratosis",
    "ACK": "Actinic Keratosis",
    "BCC": "Basal Cell Carcinoma",
    "SCC": "Squamous Cell Carcinoma",
    "MEL": "Melanoma",
    "UNKNOWN": "Unknown Lesion",
}


class BodyRegion(str, Enum):
    """Common anatomical locations for skin lesions."""
    SCALP          = "scalp"
    FACE           = "face"
    EAR            = "ear"
    NECK           = "neck"
    CHEST          = "chest"
    ABDOMEN        = "abdomen"
    BACK           = "back"
    UPPER_EXTREMITY = "upper extremity"
    LOWER_EXTREMITY = "lower extremity"
    HAND           = "hand"
    FOOT           = "foot"
    ACRAL          = "acral"
    GENITAL        = "genital"
    UNKNOWN        = "unknown"


class SexLabel(str, Enum):
    """Patient biological sex."""
    MALE    = "male"
    FEMALE  = "female"
    UNKNOWN = "unknown"


class RiskLevel(str, Enum):
    """
    Clinical risk level derived from predicted diagnosis + confidence.

    Mapping logic:
        LOW          → NEV, SEK  (benign)
        MODERATE     → ACK        (pre-malignant / watch & wait)
        HIGH         → BCC, SCC  (malignant, treatment required)
        CRITICAL     → MEL        (aggressive, urgent referral)
        INCONCLUSIVE → Low confidence (< 50%) requiring specialist verification
    """
    LOW          = "LOW"
    MODERATE     = "MODERATE"
    HIGH         = "HIGH"
    CRITICAL     = "CRITICAL"
    INCONCLUSIVE = "INCONCLUSIVE"


RISK_COLOR: dict[RiskLevel, str] = {
    RiskLevel.LOW:          "#22c55e",   # green
    RiskLevel.MODERATE:     "#f59e0b",   # amber
    RiskLevel.HIGH:         "#ef4444",   # red
    RiskLevel.CRITICAL:     "#7c3aed",   # purple
    RiskLevel.INCONCLUSIVE: "#64748b",   # slate / gray warning
}
