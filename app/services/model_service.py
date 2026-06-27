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
        Called once at app startup. Gracefully falls back to mock mode if
        model weights are absent.
        """
        model_path      = Path(settings.model_path)
        le_diag_path    = Path(settings.le_diagnostic_path)
        imputer_path    = Path(settings.imputer_path)
        scaler_path     = Path(settings.scaler_path)
        thresholds_path = Path(settings.thresholds_path)

        # ── Validate model checkpoint ──────────────────────────────────
        if not model_path.exists():
            logger.warning(
                f"Model file not found: {model_path}. "
                "API will start in degraded (mock) mode — predictions unavailable."
            )
            self._is_loaded = False
            return

        # ── Load PyTorch checkpoint ────────────────────────────────────
        logger.info(f"Loading V6.0 model from: {model_path}  (device={self._device})")
        t0 = time.perf_counter()

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
            # Support both raw state_dict and checkpoint dicts
            state_dict = (
                checkpoint.get("model_state_dict", checkpoint)
                if isinstance(checkpoint, dict)
                else checkpoint
            )
            self._model.load_state_dict(state_dict, strict=False)
            self._model.to(self._device)
            self._model.eval()
        except Exception as exc:
            logger.error(f"Failed to load PyTorch model: {exc}")
            raise

        # ── Load Diagnostic LabelEncoder ───────────────────────────────
        try:
            with open(le_diag_path, "rb") as f:
                self._le_diagnostic = pickle.load(f)
            logger.info(f"Diagnostic encoder loaded: {list(self._le_diagnostic.classes_)}")
        except Exception:
            logger.warning("Diagnostic encoder not found. Auto-generating default.")
            from sklearn.preprocessing import LabelEncoder
            self._le_diagnostic = LabelEncoder()
            self._le_diagnostic.fit(["ACK", "BCC", "MEL", "NEV", "SCC", "SEK"])

        # ── Load Imputer ───────────────────────────────────────────────
        try:
            with open(imputer_path, "rb") as f:
                self._imputer = pickle.load(f)
            logger.info(f"Imputer loaded: keys={list(self._imputer.keys())}")
        except Exception:
            logger.warning("Imputer not found. Using built-in defaults.")
            self._imputer = {
                "numeric_medians": {"age": 52.0, "diameter_1": 1.5},
                "binary_modes":    {"gender": 1.0, "grew": 0.0, "bleed": 0.0,
                                    "skin_cancer_history": 0.0, "elevation": 0.0},
            }

        # ── Load StandardScaler ────────────────────────────────────────
        try:
            with open(scaler_path, "rb") as f:
                self._scaler = pickle.load(f)
            logger.info("StandardScaler loaded.")
        except Exception:
            logger.warning("StandardScaler not found. Numeric features will NOT be scaled.")
            self._scaler = None

        # ── Load Per-Class Thresholds ──────────────────────────────────
        try:
            with open(thresholds_path, "r") as f:
                self._thresholds = json.load(f)
            logger.info(f"Thresholds loaded: {self._thresholds}")
        except Exception:
            logger.warning(
                "Thresholds file not found. Defaulting to 1.0 for all classes "
                "(equivalent to raw argmax)."
            )
            self._thresholds = {c: 1.0 for c in ["ACK", "BCC", "MEL", "NEV", "SCC", "SEK"]}

        elapsed = (time.perf_counter() - t0) * 1000
        self._is_loaded = True
        self._load_time = time.time()

        logger.info(
            f"✅ V6.0 Model loaded in {elapsed:.1f} ms | "
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
    ) -> Tuple[str, float, Dict[str, float]]:
        """
        Run V6.0 forward pass with per-class threshold optimization.

        Args:
            image_tensor:     Preprocessed image tensor.
            tabular_tensor:   Tabular feature tensor (scaled+imputed).
            meta_mask_tensor: Binary mask tensor (1=present, 0=imputed).

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

        # ── Forward pass ──────────────────────────────────────
        output = self._model(img, tab, mask)
        # MedAssistModel returns (main_logits, aux_logits, gate)
        logits = output[0] if isinstance(output, (tuple, list)) else output

        elapsed_ms = (time.perf_counter() - t0) * 1000
        logger.debug(f"Forward pass completed in {elapsed_ms:.2f} ms")

        # ── Softmax → raw probabilities ────────────────────────
        probs = F.softmax(logits, dim=1).squeeze(0).cpu().numpy()  # (num_classes,)

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
