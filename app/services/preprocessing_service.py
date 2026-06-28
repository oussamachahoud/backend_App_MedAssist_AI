"""
app/services/preprocessing_service.py
Image and tabular data preprocessing pipeline for MedAssist AI V6.0.

Image pipeline (matches training notebook 05_evaluation_V6.0.ipynb):
    1. Resize to 256×256 (INTER_AREA for downscaling)
    2. Shades-of-Gray color constancy  (power=6)
    3. DullRazor hair removal          (kernel=17, threshold=10)
    4. CLAHE local contrast enhancement (clip_limit=2.0)
    5. ImageNet normalisation           (mean=[0.485,0.456,0.406], std=[0.229,0.224,0.225])
    6. Convert to float32 tensor (1, 3, H, W)

Tabular pipeline:
    - Accept all 7 clinical features (see model_service.ModelService.build_meta_vector)
    - Returns torch.Tensor shape (1, 7) and meta_mask tensor shape (1, 7)
"""

import io
from typing import Optional, Tuple

import numpy as np
import torch
import torchvision.transforms.functional as TF
from PIL import Image, UnidentifiedImageError
from fastapi import HTTPException, UploadFile
from loguru import logger

from app.core.config import get_settings

settings = get_settings()

# ── ImageNet normalisation constants ─────────────────────────────────────────
_IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_IMAGENET_STD  = np.array([0.229, 0.224, 0.225], dtype=np.float32)

_ALLOWED_CONTENT_TYPES = {
    "image/jpeg", "image/jpg", "image/png", "image/webp", "application/octet-stream"
}

# Try to import cv2 for advanced preprocessing
try:
    import cv2 as _cv2
    _CV2_AVAILABLE = True
except ImportError:
    _cv2 = None
    _CV2_AVAILABLE = False
    logger.warning(
        "opencv-python not installed. Advanced preprocessing (Shades-of-Gray, "
        "DullRazor, CLAHE) will be skipped — only basic resize + normalise."
    )


# ── Advanced image preprocessing helpers ─────────────────────────────────────

def _shades_of_gray(img_rgb: np.ndarray, power: float = 6) -> np.ndarray:
    """
    Shades-of-Gray color constancy illumination correction (power=6).
    Normalises the illuminant of the image to reduce color-cast artefacts.
    """
    img_f = img_rgb.astype(np.float32) + 1e-7
    if power == -1:
        norm = np.max(img_f, axis=(0, 1))
    else:
        norm = np.power(np.mean(np.power(img_f, power), axis=(0, 1)), 1.0 / power)
    norm   = norm + 1e-7
    result = img_f / norm * np.mean(norm)
    return np.clip(result, 0, 255).astype(np.uint8)


def _dullrazor_hair_removal(
    img_rgb: np.ndarray,
    kernel_size: int = 17,
    threshold: int = 10,
) -> np.ndarray:
    """
    Optimised DullRazor hair removal.
    Detects hair via black-hat morphology and inpaints with median-blurred background.
    """
    if not _CV2_AVAILABLE:
        return img_rgb

    gray    = _cv2.cvtColor(img_rgb, _cv2.COLOR_RGB2GRAY)
    kernel  = _cv2.getStructuringElement(_cv2.MORPH_RECT, (kernel_size, kernel_size))
    blackhat = _cv2.morphologyEx(gray, _cv2.MORPH_BLACKHAT, kernel)
    _, mask  = _cv2.threshold(blackhat, threshold, 255, _cv2.THRESH_BINARY)

    blurred      = _cv2.medianBlur(img_rgb, 15)
    mask_3d      = np.expand_dims(mask, axis=-1)
    result       = np.where(mask_3d > 0, blurred, img_rgb)
    return result.astype(np.uint8)


def _apply_clahe(img_rgb: np.ndarray, clip_limit: float = 2.0) -> np.ndarray:
    """
    Apply CLAHE (Contrast Limited Adaptive Histogram Equalisation) to L channel
    of LAB colour space and convert back to RGB.
    """
    if not _CV2_AVAILABLE:
        return img_rgb

    lab  = _cv2.cvtColor(img_rgb, _cv2.COLOR_RGB2LAB)
    l, a, b = _cv2.split(lab)
    clahe_op = _cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(8, 8))
    l_clahe  = clahe_op.apply(l)
    lab_out  = _cv2.merge([l_clahe, a, b])
    return _cv2.cvtColor(lab_out, _cv2.COLOR_LAB2RGB)


def _preprocess_numpy(img_rgb: np.ndarray) -> torch.Tensor:
    """
    Apply the full V6.0 preprocessing pipeline to an RGB uint8 image array.

    Steps:
        1. Shades-of-Gray (if cv2 available)
        2. DullRazor hair removal (if cv2 available)
        3. CLAHE (if cv2 available)
        4. Convert to float32 [0, 1]
        5. ImageNet normalise
        6. Permute to (C, H, W)

    Returns:
        torch.Tensor of shape (3, 256, 256) — float32
    """
    if _CV2_AVAILABLE:
        img_rgb = _shades_of_gray(img_rgb)
        img_rgb = _dullrazor_hair_removal(img_rgb)
        img_rgb = _apply_clahe(img_rgb)

    img_f  = img_rgb.astype(np.float32) / 255.0
    img_f  = (img_f - _IMAGENET_MEAN) / _IMAGENET_STD

    tensor = torch.from_numpy(img_f).permute(2, 0, 1).float()  # (3, H, W)
    return tensor


# ── File I/O helpers ──────────────────────────────────────────────────────────

async def _read_upload(file: UploadFile) -> bytes:
    """Read and validate the uploaded file bytes."""
    content_type = (file.content_type or "").lower()
    if content_type not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail=(
                f"Unsupported image type '{content_type}'. "
                f"Accepted: {', '.join(sorted(_ALLOWED_CONTENT_TYPES))}"
            ),
        )

    raw = await file.read()

    if len(raw) > settings.max_image_size_bytes:
        raise HTTPException(
            status_code=413,
            detail=(
                f"Image too large ({len(raw) / 1_048_576:.1f} MB). "
                f"Maximum: {settings.max_image_size_mb} MB."
            ),
        )

    if len(raw) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    return raw


def _bytes_to_pil(raw: bytes) -> Image.Image:
    """Convert raw bytes to a PIL RGB image."""
    try:
        return Image.open(io.BytesIO(raw)).convert("RGB")
    except UnidentifiedImageError:
        raise HTTPException(
            status_code=422,
            detail="Could not decode image. Ensure the file is a valid JPEG or PNG.",
        )


# ── Public API ────────────────────────────────────────────────────────────────

async def preprocess_image(
    file: UploadFile,
) -> Tuple[torch.Tensor, Tuple[int, int]]:
    """
    Read an uploaded image and apply the full V6.0 preprocessing pipeline.

    Returns:
        image_tensor  : shape (1, 3, 256, 256) — float32, normalised
        original_size : (width, height) of the original image
    """
    raw           = await _read_upload(file)
    pil_img       = _bytes_to_pil(raw)
    original_size: Tuple[int, int] = pil_img.size   # PIL: (width, height)

    target = settings.image_size  # 256

    logger.debug(
        f"Preprocessing image: original={original_size}, target=({target}×{target})"
    )

    # Resize to 256×256 using high-quality Lanczos (PIL doesn't support INTER_AREA
    # directly but LANCZOS gives equivalent quality for downscaling)
    pil_resized = pil_img.resize((target, target), Image.LANCZOS)
    img_np      = np.array(pil_resized, dtype=np.uint8)  # (H, W, 3) RGB

    tensor = _preprocess_numpy(img_np)   # (3, H, W)
    tensor = tensor.unsqueeze(0)         # (1, 3, H, W)

    return tensor, original_size


def build_tabular_tensor(
    features: np.ndarray,
    meta_mask: np.ndarray,
) -> Tuple[torch.Tensor, torch.Tensor]:
    """
    Convert pre-processed feature array and mask into PyTorch tensors.

    Args:
        features  : np.ndarray of shape (7,) — already scaled & imputed
        meta_mask : np.ndarray of shape (7,) — 1.0 present, 0.0 imputed

    Returns:
        tab_tensor  : torch.Tensor shape (1, 7) — float32
        mask_tensor : torch.Tensor shape (1, 7) — float32
    """
    tab_tensor  = torch.from_numpy(np.stack([features])).float()
    mask_tensor = torch.from_numpy(np.stack([meta_mask])).float()
    return tab_tensor, mask_tensor
