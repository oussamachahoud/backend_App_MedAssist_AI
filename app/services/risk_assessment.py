"""
app/services/risk_assessment.py
Derives clinical risk level and recommendations from model predictions.

Risk Mapping:
    LOW      → NEV, SEK   (benign lesions)
    MODERATE → ACK         (pre-malignant — watch & wait)
    HIGH     → BCC, SCC   (malignant — treatment required)
    CRITICAL → MEL         (aggressive — urgent referral)
"""

from typing import List, Tuple

from app.models.schemas import DiagnosticLabel, RiskLevel


# ── Risk mapping table ─────────────────────────────────────────────────────────

_BASE_RISK: dict[DiagnosticLabel, RiskLevel] = {
    DiagnosticLabel.NEV: RiskLevel.LOW,
    DiagnosticLabel.SEK: RiskLevel.LOW,
    DiagnosticLabel.ACK: RiskLevel.MODERATE,
    DiagnosticLabel.BCC: RiskLevel.HIGH,
    DiagnosticLabel.SCC: RiskLevel.HIGH,
    DiagnosticLabel.MEL: RiskLevel.CRITICAL,
}

_EXPLANATIONS: dict[DiagnosticLabel, str] = {
    DiagnosticLabel.NEV: (
        "Nevus (common mole) — benign lesion. "
        "Routine monitoring is sufficient."
    ),
    DiagnosticLabel.SEK: (
        "Seborrheic Keratosis — benign epidermal growth. "
        "No treatment required unless symptomatic."
    ),
    DiagnosticLabel.ACK: (
        "Actinic Keratosis — pre-malignant lesion caused by UV damage. "
        "Medical evaluation and treatment recommended to prevent progression."
    ),
    DiagnosticLabel.BCC: (
        "Basal Cell Carcinoma — most common skin cancer. "
        "Malignant but slow-growing. Dermatologist referral required."
    ),
    DiagnosticLabel.SCC: (
        "Squamous Cell Carcinoma — malignant skin cancer with metastatic risk. "
        "Prompt dermatologist referral and biopsy required."
    ),
    DiagnosticLabel.MEL: (
        "Melanoma — highly aggressive skin cancer with high metastatic potential. "
        "URGENT referral to a dermatologist/oncologist is recommended."
    ),
}

_RECOMMENDATIONS: dict[DiagnosticLabel, List[str]] = {
    DiagnosticLabel.NEV: [
        "Monitor lesion for changes in size, shape, or color (ABCDE rule).",
        "Annual skin examination by a dermatologist.",
        "Use broad-spectrum SPF 30+ sunscreen daily.",
    ],
    DiagnosticLabel.SEK: [
        "No treatment required unless lesion is irritated or symptomatic.",
        "If uncertain, a biopsy can confirm the diagnosis.",
        "Protect skin from excessive sun exposure.",
    ],
    DiagnosticLabel.ACK: [
        "Schedule appointment with a dermatologist within 4 weeks.",
        "Treatment options: cryotherapy, topical fluorouracil, or photodynamic therapy.",
        "Avoid sun exposure — use SPF 50+ and protective clothing.",
        "Do not scratch or irritate the lesion.",
    ],
    DiagnosticLabel.BCC: [
        "Refer to a dermatologist for biopsy confirmation.",
        "Treatment options: surgical excision, Mohs surgery, or radiation.",
        "Schedule appointment within 2 weeks.",
        "Strict sun protection required.",
    ],
    DiagnosticLabel.SCC: [
        "URGENT: Refer to a dermatologist/oncologist immediately.",
        "Biopsy and staging required to assess metastatic risk.",
        "Do not delay treatment — SCC can spread to lymph nodes.",
        "Avoid any trauma to the lesion area.",
    ],
    DiagnosticLabel.MEL: [
        "URGENT: Seek immediate specialist care (dermatologist/oncologist).",
        "Complete excision biopsy required as soon as possible.",
        "Lymph node assessment and staging scan may be needed.",
        "Do not attempt self-treatment.",
        "Inform close family members — melanoma has a hereditary component.",
    ],
}


# ── Confidence threshold adjustment ────────────────────────────────────────────

_LOW_CONFIDENCE_THRESHOLD = 0.50   # Below this: bump risk up one level


def _bump_risk(risk: RiskLevel) -> RiskLevel:
    """Escalate risk by one level when model confidence is low."""
    order = [RiskLevel.LOW, RiskLevel.MODERATE, RiskLevel.HIGH, RiskLevel.CRITICAL]
    idx = order.index(risk)
    return order[min(idx + 1, len(order) - 1)]


# ── Public API ─────────────────────────────────────────────────────────────────

def calculate_risk(
    label: DiagnosticLabel,
    confidence: float,
) -> Tuple[RiskLevel, str, List[str]]:
    """
    Calculate clinical risk based on predicted label and confidence.

    Args:
        label:      Predicted DiagnosticLabel enum value.
        confidence: Softmax probability of the top prediction (0.0 – 1.0).

    Returns:
        Tuple of (RiskLevel, explanation_str, recommendations_list)
    """
    risk = _BASE_RISK[label]

    # If confidence is low, escalate risk to be safe (err on the side of caution)
    low_confidence = confidence < _LOW_CONFIDENCE_THRESHOLD
    if low_confidence:
        risk = _bump_risk(risk)

    explanation = _EXPLANATIONS[label]
    if low_confidence:
        explanation += (
            f" (Note: model confidence is low [{confidence:.0%}]) — "
            "clinical judgment should override this result."
        )

    recommendations = _RECOMMENDATIONS[label]
    if low_confidence:
        recommendations = [
            "⚠️  Low model confidence — manual clinical review strongly recommended.",
            *recommendations,
        ]

    return risk, explanation, recommendations
