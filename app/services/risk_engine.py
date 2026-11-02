"""
app/services/risk_engine.py
V2.0 Clinical Risk Engine.
Evaluates diagnostic risk, detects inconclusive low-confidence predictions,
and generates clinical referral recommendations.
"""

from dataclasses import dataclass
from typing import List

from app.models.schemas import DiagnosticLabel, RiskLevel

# ── Base Clinical Risk Table ──────────────────────────────────────────────────

BASE_RISK_MAP: dict[DiagnosticLabel, RiskLevel] = {
    DiagnosticLabel.NEV: RiskLevel.LOW,
    DiagnosticLabel.SEK: RiskLevel.LOW,
    DiagnosticLabel.ACK: RiskLevel.MODERATE,
    DiagnosticLabel.BCC: RiskLevel.HIGH,
    DiagnosticLabel.SCC: RiskLevel.HIGH,
    DiagnosticLabel.MEL: RiskLevel.CRITICAL,
    DiagnosticLabel.UNKNOWN: RiskLevel.INCONCLUSIVE,
}

BASE_EXPLANATIONS: dict[DiagnosticLabel, str] = {
    DiagnosticLabel.NEV: (
        "Nevus (common mole) — benign melanocytic proliferation. "
        "Routine periodic self-monitoring is sufficient."
    ),
    DiagnosticLabel.SEK: (
        "Seborrheic Keratosis — benign epidermal lesion. "
        "No intervention required unless irritated or inflamed."
    ),
    DiagnosticLabel.ACK: (
        "Actinic Keratosis — pre-malignant dysplasia caused by cumulative UV exposure. "
        "Clinical evaluation recommended to monitor for malignant progression."
    ),
    DiagnosticLabel.BCC: (
        "Basal Cell Carcinoma — common locally invasive cutaneous malignancy. "
        "Requires specialist dermatologist evaluation for definitive excision."
    ),
    DiagnosticLabel.SCC: (
        "Squamous Cell Carcinoma — invasive malignancy with risk of regional metastasis. "
        "Prompt dermatologist evaluation and biopsy required."
    ),
    DiagnosticLabel.MEL: (
        "Melanoma — highly aggressive cutaneous malignancy with high metastatic potential. "
        "URGENT immediate referral to a specialist dermatologist/oncologist is required."
    ),
    DiagnosticLabel.UNKNOWN: (
        "Indeterminate skin lesion — clinical evaluation required."
    ),
}

BASE_RECOMMENDATIONS: dict[DiagnosticLabel, List[str]] = {
    DiagnosticLabel.NEV: [
        "Monitor lesion for changes in size, shape, or color (ABCDE criteria).",
        "Perform annual skin examination with a dermatologist.",
        "Apply broad-spectrum SPF 30+ sunscreen daily.",
    ],
    DiagnosticLabel.SEK: [
        "No medical intervention required unless lesion becomes irritated or symptomatic.",
        "Dermoscopy or shave biopsy can be performed if clinical diagnosis is uncertain.",
        "Maintain routine skin protection and sun hygiene.",
    ],
    DiagnosticLabel.ACK: [
        "Schedule appointment with a dermatologist within 4 weeks.",
        "Discuss treatment modalities (cryotherapy, topical 5-FU, or PDT).",
        "Strict UV protection: wear protective clothing and broad-spectrum SPF 50+.",
    ],
    DiagnosticLabel.BCC: [
        "Refer to specialist dermatologist for dermoscopy and confirmatory biopsy.",
        "Discuss surgical excision or Mohs micrographic surgery.",
        "Schedule appointment within 2 weeks.",
        "Avoid UV exposure to the affected area.",
    ],
    DiagnosticLabel.SCC: [
        "URGENT: Expedited referral to a specialist dermatologist or surgical oncologist.",
        "Confirmatory biopsy and regional lymph node assessment required.",
        "Avoid any manipulation or mechanical irritation of the lesion.",
    ],
    DiagnosticLabel.MEL: [
        "URGENT EMERGENCY: Immediate specialist referral to dermatologist/oncologist.",
        "Complete diagnostic excision biopsy with appropriate margins required.",
        "Full-body cutaneous and regional lymph node staging indicated.",
        "Do not delay specialist consultation.",
    ],
    DiagnosticLabel.UNKNOWN: [
        "Refer to a dermatologist for clinical in-person examination.",
    ],
}

LOW_CONFIDENCE_THRESHOLD = 0.50


@dataclass
class RiskEvaluation:
    """Structured clinical risk assessment result."""
    risk_level: RiskLevel
    base_risk: RiskLevel
    risk_escalated: bool
    suggest_referral: bool
    explanation: str
    recommendations: List[str]


def evaluate_clinical_risk(
    label: DiagnosticLabel,
    confidence: float,
) -> RiskEvaluation:
    """
    Evaluate diagnostic risk for MedAssist AI V2.0:
    - If confidence < 50%:
        risk_level is set to INCONCLUSIVE.
        suggest_referral is set to True.
        base_risk is preserved in the explanation.
    - If confidence >= 50%:
        risk_level matches base clinical risk.
        suggest_referral is True for HIGH and CRITICAL.
    """
    base_risk = BASE_RISK_MAP.get(label, RiskLevel.INCONCLUSIVE)
    is_low_confidence = confidence < LOW_CONFIDENCE_THRESHOLD

    if is_low_confidence:
        risk_level = RiskLevel.INCONCLUSIVE
        risk_escalated = True
        suggest_referral = True
        explanation = (
            f"INCONCLUSIVE diagnosis: Model confidence is low ({confidence:.1%}). "
            f"Preliminary algorithm indication is {label.value} (base risk: {base_risk.value}), "
            "but tele-dermatology specialist referral is required for safety."
        )
        recommendations = [
            "⚠️ Inconclusive AI prediction — specialist referral strongly advised.",
            f"Review clinical metadata and dermoscopic pattern under polarized light.",
            *BASE_RECOMMENDATIONS.get(label, []),
        ]
    else:
        risk_level = base_risk
        risk_escalated = False
        suggest_referral = risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)
        explanation = BASE_EXPLANATIONS.get(label, BASE_EXPLANATIONS[DiagnosticLabel.UNKNOWN])
        recommendations = list(BASE_RECOMMENDATIONS.get(label, []))

    return RiskEvaluation(
        risk_level=risk_level,
        base_risk=base_risk,
        risk_escalated=risk_escalated,
        suggest_referral=suggest_referral,
        explanation=explanation,
        recommendations=recommendations,
    )

