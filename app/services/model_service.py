"""
app/services/model_service.py
Singleton service that loads the MedAssist AI V6.0 multimodal PyTorch model
and runs inference combining image tensors + tabular clinical features.

Model Architecture (V6.0):
    - ImageBranch (EfficientNet-B3 + GeM + auxiliary head)
    - MLPBranch   (7 clinical features + meta_mask)
    - GatedCrossAttentionFusion (cross-attention + learnable gate)

V6.0 preprocessing artifacts:
    - diagnostic_encoder.pkl  : LabelEncoder for 6 diagnostic classes
    - imputer.pkl             : median/mode values for missing feature imputation
    - scaler.pkl              : StandardScaler for numeric features (age, diameter_1)
    - thresholds_V6.0.json    : per-class optimal decision thresholds from 04b

Inference modes:
    - Standard (use_tta=False) : single forward pass  — fast, ~30–50 ms
    - TTA×8    (use_tta=True)  : 8-augmentation average — more accurate, ~200–400 ms
                                 Augmentations match notebook 05:
                                 original, h-flip, v-flip, both-flip,
                                 rot90, rot180, rot270, center-crop-256
"""

import json
import pickle
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import torch
import torch.nn.functional as F
from loguru import logger

from app.core.config import get_settings
from app.models.schemas import DiagnosticLabel

settings = get_settings()

# Fixed order of 7 metadata features — must match training notebook 02
SELECTED_FEATURES = ["age", "gender", "grew", "bleed",
                     "diameter_1", "skin_cancer_history", "elevation"]
NUMERIC_FEATURES  = ["age", "diameter_1"]   # indices 0, 4
BINARY_FEATURES   = ["gender", "grew", "bleed", "skin_cancer_history", "elevation"]


# ── TTA Helper ────────────────────────────────────────────────────────────────

def _apply_tta(images: torch.Tensor) -> list:
    """
    Generate 8 augmented views of a batch of images.
    Exactly matches the apply_tta() function in notebook 05_evaluation_V6.0.ipynb.

    Augmentations:
        1. Original
        2. Horizontal flip
        3. Vertical flip
        4. H-flip + V-flip
        5. Rotate 90°
        6. Rotate 180°
        7. Rotate 270°
        8. Center crop 224×224 → resize back to 256×256

    Args:
        images: tensor of shape (B, 3, H, W)

    Returns:
        List of 8 tensors, each (B, 3, H, W)
    """
    B, C, H, W = images.shape
    aug_list = [
        images,                                          # 1. Original
        torch.flip(images, dims=[3]),                    # 2. H-flip
        torch.flip(images, dims=[2]),                    # 3. V-flip
        torch.flip(images, dims=[2, 3]),                 # 4. H+V flip
        torch.rot90(images, k=1, dims=[2, 3]),           # 5. Rotate 90
        torch.rot90(images, k=2, dims=[2, 3]),           # 6. Rotate 180
        torch.rot90(images, k=3, dims=[2, 3]),           # 7. Rotate 270
    ]
    # 8. Center crop 224×224 → resize to original H×W
    crop = 224
    start = (H - crop) // 2
    cropped = images[:, :, start:start + crop, start:start + crop]
    resized = F.interpolate(cropped, size=(H, W), mode="bilinear", align_corners=False)
    aug_list.append(resized)
    return aug_list

class ModelService:
    """
    Thread-safe singleton for V6.0 model loading and inference.

    Lifecycle:
        1. Instantiated once at application startup (via FastAPI lifespan).
        2. Injected into endpoints via FastAPI dependency injection.
        3. Gracefully degrades to mock mode when model weights are absent.
    """

    def __init__(self) -> None:
        self._model: Optional[torch.nn.Module] = None
        self._le_diagnostic = None        # sklearn LabelEncoder
        self._imputer: Optional[dict] = None   # {numeric_medians, binary_modes}
        self._scaler = None                    # sklearn StandardScaler
        self._thresholds: Dict[str, float] = {}
        self._device: torch.device = torch.device(
            "cuda" if torch.cuda.is_available() else "cpu"
        )
        self._is_loaded: bool = False
        self._load_time: Optional[float] = None

    # ── Loading ───────────────────────────────────────────────────────────────

    def load(self) -> None:
        """
        Load PyTorch model and all preprocessing artifacts from disk.
        All 5 files are strictly required to ensure correct V6.0 behavior.
        """
        model_path      = Path(settings.model_path)
        le_diag_path    = Path(settings.le_diagnostic_path)
        imputer_path    = Path(settings.imputer_path)
        scaler_path     = Path(settings.scaler_path)
        thresholds_path = Path(settings.thresholds_path)

        # ── 1. Check all files exist ───────────────────────────────────
        required_files = {
            "Model weights (multimodal_model.pth)": model_path,
            "Diagnostic encoder (diagnostic_encoder.pkl)": le_diag_path,
            "Imputer (imputer.pkl)": imputer_path,
            "Scaler (scaler.pkl)": scaler_path,
            "Thresholds (thresholds_V6.0.json)": thresholds_path,
        }
        
        missing = [f" - {name}: {path.resolve()}" for name, path in required_files.items() if not path.exists()]
        if missing:
            msg = "Missing required V6.0 model artifacts:\n" + "\n".join(missing)
            logger.critical(msg)
            raise FileNotFoundError(msg)

        logger.info(f"Loading V6.0 model from: {model_path}  (device={self._device})")
        t0 = time.perf_counter()

        # ── 2. Load Model Weights ──────────────────────────────────────
        try:
            from app.services.architecture import MedAssistModel
            self._model = MedAssistModel(
                num_meta=settings.num_tabular_features,   # 7
                num_classes=settings.num_diagnostic_classes,  # 6
                img_embed_dim=256,
                meta_embed_dim=64,
                backbone_name="efficientnet_b3",
            )
            checkpoint = torch.load(
                model_path, map_location=self._device, weights_only=False
            )
            state_dict = checkpoint.get("model_state_dict", checkpoint) if isinstance(checkpoint, dict) else checkpoint
            self._model.load_state_dict(state_dict, strict=False)
            self._model.to(self._device)
            self._model.eval()
        except Exception as exc:
            logger.error(f"Failed to load PyTorch model: {exc}")
            raise RuntimeError(f"Cannot load model weights: {exc}") from exc

        # ── 3. Load Diagnostic Encoder ─────────────────────────────────
        try:
            with open(le_diag_path, "rb") as f:
                self._le_diagnostic = pickle.load(f)
            logger.info(f"Diagnostic encoder loaded: {list(self._le_diagnostic.classes_)}")
        except Exception as exc:
            logger.error(f"Failed to load diagnostic encoder: {exc}")
            raise RuntimeError(f"Cannot load diagnostic_encoder.pkl: {exc}") from exc

        # ── 4. Load Imputer ────────────────────────────────────────────
        try:
            with open(imputer_path, "rb") as f:
                self._imputer = pickle.load(f)
            logger.info(f"Imputer loaded: keys={list(self._imputer.keys())}")
        except Exception as exc:
            logger.error(f"Failed to load imputer: {exc}")
            raise RuntimeError(f"Cannot load imputer.pkl: {exc}") from exc

        # ── 5. Load Scaler ─────────────────────────────────────────────
        try:
            with open(scaler_path, "rb") as f:
                self._scaler = pickle.load(f)
            logger.info("StandardScaler loaded.")
        except Exception as exc:
            logger.error(f"Failed to load scaler: {exc}")
            raise RuntimeError(f"Cannot load scaler.pkl: {exc}") from exc

        # ── 6. Load Thresholds ─────────────────────────────────────────
        try:
            with open(thresholds_path, "r") as f:
                self._thresholds = json.load(f)
            logger.info(f"Thresholds loaded: {self._thresholds}")
        except Exception as exc:
            logger.error(f"Failed to load thresholds: {exc}")
            raise RuntimeError(f"Cannot load thresholds_V6.0.json: {exc}") from exc

        elapsed = (time.perf_counter() - t0) * 1000
        self._is_loaded = True
        self._load_time = time.time()

        logger.info(
            f"✅ V6.0 Model loaded securely in {elapsed:.1f} ms | "
            f"device={self._device} | "
            f"classes={list(self._le_diagnostic.classes_)}"
        )

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def is_loaded(self) -> bool:
        return self._is_loaded

    @property
    def device(self) -> torch.device:
        return self._device

    @property
    def diagnostic_classes(self) -> List[str]:
        if self._le_diagnostic is None:
            return [e.value for e in DiagnosticLabel]
        return list(self._le_diagnostic.classes_)

    # ── Tabular Feature Encoding ──────────────────────────────────────────────

    def build_meta_vector(
        self,
        age: Optional[float],
        sex: Optional[str],
        grew: Optional[bool],
        bleed: Optional[bool],
        diameter_1: Optional[float],
        skin_cancer_history: Optional[bool],
        elevation: Optional[bool],
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Build the 7-feature metadata vector and meta_mask.

        Returns:
            features  : np.ndarray of shape (7,) — scaled & imputed values
            meta_mask : np.ndarray of shape (7,) — 1.0 if provided, 0.0 if imputed
        """
        imp = self._imputer or {}
        numeric_medians = imp.get("numeric_medians", {"age": 52.0, "diameter_1": 1.5})
        binary_modes    = imp.get("binary_modes",    {
            "gender": 1.0, "grew": 0.0, "bleed": 0.0,
            "skin_cancer_history": 0.0, "elevation": 0.0,
        })

        # Map sex string → binary gender value
        def sex_to_gender(s: Optional[str]) -> Optional[float]:
            if s is None:
                return None
            mapping = {"male": 1.0, "female": 0.0, "unknown": None}
            return mapping.get(str(s).lower(), None)

        # Raw values for each feature (None if missing/unknown)
        raw = {
            "age":                 float(age) if age is not None else None,
            "gender":              sex_to_gender(sex),
            "grew":                float(grew) if grew is not None else None,
            "bleed":               float(bleed) if bleed is not None else None,
            "diameter_1":          float(diameter_1) if diameter_1 is not None else None,
            "skin_cancer_history": float(skin_cancer_history) if skin_cancer_history is not None else None,
            "elevation":           float(elevation) if elevation is not None else None,
        }

        # Build meta_mask (1.0 = present, 0.0 = missing)
        meta_mask = np.array(
            [0.0 if raw[f] is None else 1.0 for f in SELECTED_FEATURES],
            dtype=np.float32,
        )

        # Impute missing values
        imputed = {}
        for feat in SELECTED_FEATURES:
            val = raw[feat]
            if val is None:
                if feat in NUMERIC_FEATURES:
                    imputed[feat] = numeric_medians.get(feat, 0.0)
                else:
                    imputed[feat] = binary_modes.get(feat, 0.0)
            else:
                imputed[feat] = val

        # Apply StandardScaler to numeric features
        if self._scaler is not None:
            try:
                numeric_vals = np.array(
                    [[imputed["age"], imputed["diameter_1"]]], dtype=np.float32
                )
                scaled_vals = self._scaler.transform(numeric_vals)[0]
                imputed["age"]        = float(scaled_vals[0])
                imputed["diameter_1"] = float(scaled_vals[1])
            except Exception as exc:
                logger.warning(f"Scaler transform failed: {exc}. Using raw values.")
        else:
            # Fallback: simple age normalization if scaler not available
            if imputed["age"] is not None:
                imputed["age"] = imputed["age"] / 120.0

        features = np.array([imputed[f] for f in SELECTED_FEATURES], dtype=np.float32)
        return features, meta_mask

    # ── Inference ─────────────────────────────────────────────────────────────

    @torch.inference_mode()
    def predict(
        self,
        image_tensor: torch.Tensor,    # shape: (1, 3, 256, 256)
        tabular_tensor: torch.Tensor,  # shape: (1, 7)
        meta_mask_tensor: Optional[torch.Tensor] = None,  # shape: (1, 7)
        use_tta: bool = False,         # True → 8-augmentation TTA (more accurate)
    ) -> Tuple[str, float, Dict[str, float]]:
        """
        Run V6.0 forward pass with per-class threshold optimization.

        Args:
            image_tensor:     Preprocessed image tensor.
            tabular_tensor:   Tabular feature tensor (scaled+imputed).
            meta_mask_tensor: Binary mask tensor (1=present, 0=imputed).
            use_tta:          If True, run TTA×8 and average probabilities
                              (matches notebook 05 evaluation — more accurate
                              but ~6–8× slower than single pass).

        Returns:
            Tuple of:
                - predicted_label (str):  e.g. "MEL"
                - confidence (float):     raw softmax probability of predicted class
                - all_probs (dict):       {label: raw_probability} for all 6 classes
        """
        if not self._is_loaded or self._model is None:
            raise RuntimeError(
                "Model not loaded. Ensure model weights exist at startup."
            )

        img  = image_tensor.to(self._device)
        tab  = tabular_tensor.to(self._device)
        mask = meta_mask_tensor.to(self._device) if meta_mask_tensor is not None else None

        t0 = time.perf_counter()

        # ── Forward pass (single or TTA×8) ────────────────────
        if use_tta:
            aug_images = _apply_tta(img)
            accum = torch.zeros(
                (img.size(0), settings.num_diagnostic_classes), device=self._device
            )
            for aug_img in aug_images:
                output  = self._model(aug_img, tab, mask)
                logits  = output[0] if isinstance(output, (tuple, list)) else output
                accum  += F.softmax(logits, dim=1)
            probs = (accum / len(aug_images)).squeeze(0).cpu().numpy()  # avg of 8
        else:
            output = self._model(img, tab, mask)
            logits = output[0] if isinstance(output, (tuple, list)) else output
            probs  = F.softmax(logits, dim=1).squeeze(0).cpu().numpy()

        elapsed_ms = (time.perf_counter() - t0) * 1000
        tta_str = f"TTA×{len(aug_images) if use_tta else 1}"
        logger.debug(f"Forward pass ({tta_str}) completed in {elapsed_ms:.2f} ms")

        # ── Per-class threshold optimization ───────────────────
        classes = self.diagnostic_classes
        thresholds_arr = np.array(
            [self._thresholds.get(c, 1.0) for c in classes], dtype=np.float32
        )
        adjusted_probs = probs / thresholds_arr

        top_idx       = int(np.argmax(adjusted_probs))
        confidence    = float(probs[top_idx])                # raw probability

        # ── Decode label ──────────────────────────────────────
        predicted_label = self._le_diagnostic.inverse_transform([top_idx])[0]

        # ── Build full raw probability dict ───────────────────
        all_probs: Dict[str, float] = {
            classes[i]: float(probs[i]) for i in range(len(classes))
        }

        logger.info(
            f"Prediction: {predicted_label} (conf={confidence:.3f}) | "
            f"inference={elapsed_ms:.1f} ms"
        )

        return predicted_label, confidence, all_probs


# ── Global singleton instance ─────────────────────────────────────────────────
# Instantiated once; .load() is called during FastAPI lifespan startup.
model_service = ModelService()
