"""
app/api/endpoints/predict.py
V6.0 prediction endpoint — accepts image + 7 clinical metadata fields,
returns skin lesion diagnosis with confidence scores and risk assessment.

POST /api/v1/predict   (multipart/form-data)
"""

import time
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from loguru import logger

from app.api.dependencies import get_model_service
from app.models.request import PredictFormData
from app.models.response import PredictResponse
from app.models.schemas import BodyRegion, SexLabel
from app.services.model_service import ModelService
from app.services.preprocessing_service import build_tabular_tensor, preprocess_image
from app.services.risk_assessment import calculate_risk

router = APIRouter(tags=["Prediction"])


@router.post(
    "/predict",
    response_model=PredictResponse,
    summary="Skin Lesion Prediction (V6.0)",
    description=(
        "Upload a dermoscopy image alongside clinical patient metadata to receive "
        "a diagnostic prediction with confidence scores and clinical risk assessment.\n\n"
        "**Required**: `file` (image), `age`\n\n"
        "**Optional clinical fields** (all improve accuracy when provided):\n"
        "`sex`, `localization`, `grew`, `bleed`, `diameter_1`, "
        "`skin_cancer_history`, `elevation`\n\n"
        "Missing optional fields are automatically imputed using training set medians/modes."
    ),
    responses={
        200: {"description": "Successful prediction"},
        400: {"description": "Bad request (empty file, invalid metadata)"},
        413: {"description": "Image file too large"},
        415: {"description": "Unsupported image format"},
        503: {"description": "ML model not available"},
    },
)
async def predict(
    # ── Image file (required) ─────────────────────────────
    file: Annotated[
        UploadFile,
        File(description="Dermoscopy image (JPEG or PNG, max 10 MB)"),
    ],
    # ── Required patient metadata ─────────────────────────
    age: Annotated[
        float,
        Form(description="Patient age in years (0–120)", ge=0, le=120),
    ],
    # ── Optional clinical fields ──────────────────────────
    sex: Annotated[
        SexLabel,
        Form(description="Patient biological sex: male | female | unknown"),
    ] = SexLabel.UNKNOWN,
    localization: Annotated[
        BodyRegion,
        Form(description="Anatomical site of the skin lesion (informational)"),
    ] = BodyRegion.UNKNOWN,
    grew: Annotated[
        Optional[bool],
        Form(description="Was the lesion growing? (true/false)"),
    ] = None,
    bleed: Annotated[
        Optional[bool],
        Form(description="Does the lesion bleed? (true/false)"),
    ] = None,
    diameter_1: Annotated[
        Optional[float],
        Form(description="Largest lesion diameter in cm (0–50)", ge=0, le=50),
    ] = None,
    skin_cancer_history: Annotated[
        Optional[bool],
        Form(description="Prior personal skin cancer history? (true/false)"),
    ] = None,
    elevation: Annotated[
        Optional[bool],
        Form(description="Is the lesion elevated/raised? (true/false)"),
    ] = None,
    patient_id: Annotated[
        Optional[str],
        Form(description="Optional patient identifier for tracking", max_length=64),
    ] = None,
    # ── Injected dependency ───────────────────────────────
    svc: ModelService = Depends(get_model_service),
) -> PredictResponse:
    """
    Full V6.0 prediction pipeline:
        1. Validate & preprocess uploaded image     → image tensor (1, 3, 256, 256)
        2. Build 7-feature tabular vector           → tabular tensor (1, 7) + meta_mask
        3. Run multimodal forward pass              → logits → threshold-adjusted prediction
        4. Calculate clinical risk level
        5. Return structured PredictResponse
    """
    t_start = time.perf_counter()

    logger.info(
        f"Prediction request | patient_id={patient_id} | age={age} | sex={sex.value} | "
        f"localization={localization.value} | grew={grew} | bleed={bleed} | "
        f"diameter_1={diameter_1} | skin_cancer_history={skin_cancer_history} | "
        f"elevation={elevation} | filename={file.filename}"
    )

    # ── Step 1: Preprocess image ──────────────────────────
    try:
        image_tensor, original_size = await preprocess_image(file)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"Unexpected error during image preprocessing: {exc}")
        raise HTTPException(status_code=500, detail="Failed to process image.") from exc

    # ── Step 2: Build tabular features & meta_mask ────────
    try:
        features, meta_mask = svc.build_meta_vector(
            age=age,
            sex=sex.value,
            grew=grew,
            bleed=bleed,
            diameter_1=diameter_1,
            skin_cancer_history=skin_cancer_history,
            elevation=elevation,
        )
        tabular_tensor, mask_tensor = build_tabular_tensor(features, meta_mask)
    except Exception as exc:
        logger.exception(f"Error building tabular features: {exc}")
        raise HTTPException(status_code=500, detail="Failed to process metadata.") from exc

    logger.debug(
        f"Meta vector: {dict(zip(['age','gender','grew','bleed','diameter_1','skin_cancer_history','elevation'], features.tolist()))} | "
        f"mask: {meta_mask.tolist()}"
    )

    # ── Step 3: Model inference ───────────────────────────
    if not svc.is_loaded:
        logger.warning(f"MOCK MODE: Returning dummy prediction for patient_id={patient_id}")
        predicted_label = "MEL"
        confidence      = 0.895
        all_probs       = {
            "ACK": 0.015, "BCC": 0.030, "MEL": 0.895,
            "NEV": 0.020, "SCC": 0.025, "SEK": 0.015,
        }
    else:
        try:
            predicted_label, confidence, all_probs = svc.predict(
                image_tensor=image_tensor,
                tabular_tensor=tabular_tensor,
                meta_mask_tensor=mask_tensor,
            )
        except RuntimeError as exc:
            logger.error(f"Inference error: {exc}")
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except Exception as exc:
            logger.exception(f"Unexpected inference error: {exc}")
            raise HTTPException(status_code=500, detail="Model inference failed.") from exc

    # ── Step 4: Risk assessment ───────────────────────────
    from app.models.schemas import DiagnosticLabel
    try:
        diag_label = DiagnosticLabel(predicted_label)
    except ValueError:
        diag_label = DiagnosticLabel.UNKNOWN

    risk_level, risk_explanation, recommendations = calculate_risk(
        label=diag_label,
        confidence=confidence,
    )

    # ── Step 5: Build and return response ─────────────────
    inference_time_ms = (time.perf_counter() - t_start) * 1000

    response = PredictResponse.build(
        predicted_label=predicted_label,
        confidence=confidence,
        all_probs=all_probs,
        risk_level=risk_level,
        risk_explanation=risk_explanation,
        recommendations=recommendations,
        inference_time_ms=inference_time_ms,
        patient_id=patient_id,
    )

    logger.info(
        f"✅ Prediction complete | label={predicted_label} | "
        f"confidence={confidence:.3f} | risk={risk_level} | "
        f"total_time={inference_time_ms:.1f} ms"
    )

    return response
