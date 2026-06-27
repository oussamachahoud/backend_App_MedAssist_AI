"""
app/services/preprocessing_service.py
Image preprocessing pipeline for the multimodal skin lesion model.

Expected input:  FastAPI UploadFile (JPEG / PNG)
Expected output: torch.Tensor of shape (1, 3, 224, 224), normalised
"""

import io
from typing import Tuple

import torch
import torchvision.transforms as T
from PIL import Image, UnidentifiedImageError
from fastapi import HTTPException, UploadFile
from loguru import logger

from app.core.config import get_settings

settings = get_settings()

# ── ImageNet normalisation stats (standard for fine-tuned CNNs) ───────────────
_IMAGENET_MEAN = (0.485, 0.456, 0.406)
_IMAGENET_STD  = (0.229, 0.224, 0.225)

_ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp", "application/octet-stream"}

# ── Transform pipeline ────────────────────────────────────────────────────────
_transform = T.Compose([
    T.Resize((settings.image_size, settings.image_size)),
    T.ToTensor(),                                           # [0,255] → [0.0,1.0]
    T.Normalize(mean=_IMAGENET_MEAN, std=_IMAGENET_STD),
])


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _read_upload(file: UploadFile) -> bytes:
    """Read and validate the uploaded file bytes."""
    # Check content type
    content_type = (file.content_type or "").lower()
    if content_type not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail=(
                f"Unsupported image type '{content_type}'. "
                f"Accepted types: {', '.join(_ALLOWED_CONTENT_TYPES)}"
            ),
        )

    raw = await file.read()

    # Enforce size limit (belt-and-suspenders alongside middleware)
    if len(raw) > settings.max_image_size_bytes:
        raise HTTPException(
            status_code=413,
            detail=(
                f"Image too large ({len(raw) / 1_048_576:.1f} MB). "
                f"Maximum allowed: {settings.max_image_size_mb} MB."
            ),
        )

    if len(raw) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    return raw


def _bytes_to_pil(raw: bytes) -> Image.Image:
    """Convert raw bytes to a PIL RGB image."""
    try:
        img = Image.open(io.BytesIO(raw)).convert("RGB")
    except UnidentifiedImageError:
        raise HTTPException(
            status_code=422,
            detail="Could not decode image. Ensure the file is a valid JPEG or PNG.",
        )
    return img


# ── Public API ────────────────────────────────────────────────────────────────

async def preprocess_image(file: UploadFile) -> Tuple[torch.Tensor, Tuple[int, int]]:
    """
    Read an uploaded image file and return a normalised tensor.

    Args:
        file: FastAPI UploadFile from the multipart form.

    Returns:
        Tuple of:
            - image_tensor: shape (1, 3, H, W) ready for model inference
            - original_size: (width, height) of the original image
    """
    raw = await _read_upload(file)
    img = _bytes_to_pil(raw)
    original_size: Tuple[int, int] = img.size  # PIL returns (width, height)

    logger.debug(
        f"Preprocessing image: original size={original_size}, "
        f"target size=({settings.image_size}x{settings.image_size})"
    )

    tensor: torch.Tensor = _transform(img)       # shape: (3, H, W)
    tensor = tensor.unsqueeze(0)                  # shape: (1, 3, H, W)

    return tensor, original_size


def build_tabular_tensor(
    age: float,
    sex_encoded: float,
    region_encoded: float,
) -> torch.Tensor:
    """
    Build the tabular feature tensor fed to the MLP branch of the model.

    Args:
        age:            Patient age (0–120), normalised to [0,1] internally.
        sex_encoded:    Numeric encoding of sex from LabelEncoder.
        region_encoded: Numeric encoding of body region from LabelEncoder.

    Returns:
        torch.Tensor of shape (1, 3) — float32
    """
    age_normalised = age / 120.0   # simple min-max normalisation

    # Base features from frontend (3)
    base_features = [age_normalised, sex_encoded, region_encoded]
    
    # Pad with 0s to reach 10 features as expected by MultimodalModel_v4
    pad_length = 10 - len(base_features)
    padded_features = base_features + [0.0] * pad_length
    
    features = torch.tensor(
        [padded_features],
        dtype=torch.float32,
    )
    return features   # shape: (1, 10)
