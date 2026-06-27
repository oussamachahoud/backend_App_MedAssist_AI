"""
app/api/endpoints/predict.py
Main prediction endpoint — accepts image + patient metadata, returns diagnosis.

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
    summary="Skin Lesion Prediction",
    description=(
        "Upload a dermoscopy image alongside patient metadata (age, sex, localization) "
        "to receive a diagnostic prediction with confidence scores and clinical risk assessment."
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
    # ── Patient metadata (form fields) ────────────────────
    age: Annotated[
        float,
        Form(description="Patient age in years (0–120)", ge=0, le=120),
    ],
    sex: Annotated[
        SexLabel,
        Form(description="Patient biological sex: male | female | unknown"),
    ] = SexLabel.UNKNOWN,
    localization: Annotated[
        BodyRegion,
        Form(description="Anatomical site of the skin lesion"),
    ] = BodyRegion.UNKNOWN,
    patient_id: Annotated[
        Optional[str],
        Form(description="Optional patient identifier for tracking", max_length=64),
    ] = None,
    # ── Injected dependency ───────────────────────────────
    svc: ModelService = Depends(get_model_service),
) -> PredictResponse:
    """
    Full prediction pipeline:
        1. Validate & preprocess the uploaded image → image tensor
        2. Encode tabular features (age, sex, localization) → tabular tensor
        3. Run multimodal forward pass → logits → softmax probabilities
        4. Calculate clinical risk level based on prediction + confidence
        5. Return structured PredictResponse
    """
    t_start = time.perf_counter()

    logger.info(
        f"Prediction request | patient_id={patient_id} | "
        f"age={age} | sex={sex} | localization={localization} | "
        f"filename={file.filename}"
    )

    # ── Step 1: Preprocess image ──────────────────────────
    try:
        image_tensor, original_size = await preprocess_image(file)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"Unexpected error during image preprocessing: {exc}")
        raise HTTPException(status_code=500, detail="Failed to process image.") from exc

    # ── Step 2: Encode tabular features ───────────────────
    sex_encoded     = svc.encode_sex(sex.value)
    region_encoded  = svc.encode_region(localization.value)
    tabular_tensor  = build_tabular_tensor(
        age=age,
        sex_encoded=sex_encoded,
        region_encoded=region_encoded,
    )

    logger.debug(
        f"Tabular features: age={age} → {age/120:.3f} | "
        f"sex={sex.value} → {sex_encoded} | "
        f"region={localization.value} → {region_encoded}"
    )

    # ── Step 3: Model inference ───────────────────────────
    if not svc.is_loaded:
        logger.warning(f"MOCK MODE: Returning dummy prediction for patient_id={patient_id}")
        predicted_label = "MEL"
        confidence = 0.895
        all_probs = {"MEL": 0.895, "NV": 0.05, "BCC": 0.055}
    else:
        try:
            predicted_label, confidence, all_probs = svc.predict(
                image_tensor=image_tensor,
                tabular_tensor=tabular_tensor,
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
