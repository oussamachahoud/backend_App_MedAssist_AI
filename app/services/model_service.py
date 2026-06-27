"""
app/services/model_service.py
Singleton service that loads the multimodal PyTorch model and label encoders,
then runs inference combining image tensors + tabular features.

Model Architecture (expected):
    - CNN branch     : processes image tensor (B, 3, 224, 224) → feature vector
    - Tabular branch : processes tabular tensor (B, 3) → feature vector
    - Fusion head    : concatenates both vectors → 6-class diagnostic logits

Label Encoders:
    - le_diagnostic.pkl : transforms integer index ↔ label string (e.g. "MEL")
    - le_region.pkl     : transforms region string ↔ integer for tabular input
"""

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


class ModelService:
    """
    Thread-safe singleton for model loading and inference.

    Lifecycle:
        1. Instantiated once at application startup (via lifespan).
        2. Injected into endpoints via FastAPI dependency injection.
        3. Raises RuntimeError if models are not found (graceful failure at startup).
    """

    def __init__(self) -> None:
        self._model: Optional[torch.nn.Module] = None
        self._le_diagnostic = None   # sklearn LabelEncoder
        self._le_region = None       # sklearn LabelEncoder
        self._device: torch.device = torch.device(
            "cuda" if torch.cuda.is_available() else "cpu"
        )
        self._is_loaded: bool = False
        self._load_time: Optional[float] = None

    # ── Loading ───────────────────────────────────────────────────────────────

    def load(self) -> None:
        """
        Load the PyTorch model and both label encoders from disk.
        Called once at app startup. Raises FileNotFoundError if files are missing.
        """
        model_path = Path(settings.model_path)
        le_diag_path = Path(settings.le_diagnostic_path)
        le_region_path = Path(settings.le_region_path)

        # ── Validate PyTorch Model exists ──────────────────────────
        if not model_path.exists():
            logger.warning(f"Model file not found: {model_path}. API will stay in mock mode.")
            self._is_loaded = False
            return

        # ── Load PyTorch model ────────────────────────────
        logger.info(f"Loading model from: {model_path} (device={self._device})")
        t0 = time.perf_counter()

        try:
            checkpoint = torch.load(model_path, map_location=self._device, weights_only=False)
            
            # Use our architecture definition
            from app.services.architecture import MultimodalModel_v4
            
            # Since the user used 10 metadata features in the notebook, we instantiate matching that shape
            # Our frontend sends 3 features right now (age, sex, localization). 
            # Preprocessing will pad the rest to 0.
            self._model = MultimodalModel_v4(
                num_metadata_features=10, 
                num_classes=6,
                img_embedding_dim=256,
                meta_embedding_dim=64,
                pretrained=False
            )
            
            if "model_state_dict" in checkpoint:
                self._model.load_state_dict(checkpoint["model_state_dict"], strict=False)
            else:
                self._model.load_state_dict(checkpoint, strict=False)
            
            self._model.to(self._device)
            self._model.eval()
        except Exception as exc:
            logger.error(f"Failed to load PyTorch model: {exc}")
            raise

        # ── Load or Create Label Encoders ───────────────────────────
        logger.info(f"Loading or generating label encoders...")
        
        try:
            with open(le_diag_path, "rb") as f:
                self._le_diagnostic = pickle.load(f)
        except Exception:
            logger.warning("Diagnostic encoder not found. Auto-generating default...")
            from sklearn.preprocessing import LabelEncoder
            self._le_diagnostic = LabelEncoder()
            # Default classes we assumed earlier
            self._le_diagnostic.fit(["ACK", "BCC", "MEL", "NEV", "SCC", "SEK"])

        try:
            with open(le_region_path, "rb") as f:
                self._le_region = pickle.load(f)
        except Exception:
            logger.warning("Region encoder not found. Auto-generating default...")
            from sklearn.preprocessing import LabelEncoder
            self._le_region = LabelEncoder()
            # Default regions from schemas
            self._le_region.fit([
                'abdomen', 'acral', 'back', 'chest', 'ear', 'face', 'foot', 
                'genital', 'hand', 'lower extremity', 'neck', 'scalp', 'unknown', 'upper extremity'
            ])

        elapsed = (time.perf_counter() - t0) * 1000
        self._is_loaded = True
        self._load_time = time.time()

        logger.info(
            f"✅ Model loaded in {elapsed:.1f} ms | "
            f"device={self._device} | "
            f"diagnostic classes={list(self._le_diagnostic.classes_)} | "
            f"region classes={list(self._le_region.classes_)}"
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

    @property
    def region_classes(self) -> List[str]:
        if self._le_region is None:
            return []
        return list(self._le_region.classes_)

    # ── Encoding Helpers ──────────────────────────────────────────────────────

    def encode_sex(self, sex: str) -> float:
        """Encode sex string to numeric (simple binary mapping)."""
        mapping = {"male": 1.0, "female": 0.0, "unknown": 0.5}
        return mapping.get(sex.lower(), 0.5)

    def encode_region(self, region: str) -> float:
        """
        Encode body region using le_region LabelEncoder.
        Falls back to 0.0 if region is unknown or encoder not loaded.
        """
        if self._le_region is None:
            return 0.0
        try:
            encoded = self._le_region.transform([region])[0]
            # Normalise to [0, 1] by dividing by number of classes
            n_classes = len(self._le_region.classes_)
            return float(encoded) / max(n_classes - 1, 1)
        except Exception:
            logger.warning(f"Unknown region '{region}', defaulting to 0.0")
            return 0.0

    # ── Inference ─────────────────────────────────────────────────────────────

    @torch.inference_mode()
    def predict(
        self,
        image_tensor: torch.Tensor,   # shape: (1, 3, 224, 224)
        tabular_tensor: torch.Tensor, # shape: (1, 3)
    ) -> Tuple[str, float, Dict[str, float]]:
        """
        Run forward pass and decode predictions.

        Args:
            image_tensor:   Preprocessed image tensor on CPU (moved to device internally).
            tabular_tensor: Tabular features tensor on CPU (moved to device internally).

        Returns:
            Tuple of:
                - predicted_label (str): e.g. "MEL"
                - confidence (float):    softmax probability of top class
                - all_probs (dict):      {label: probability} for all 6 classes
        """
        if not self._is_loaded or self._model is None:
            raise RuntimeError(
                "Model not loaded. Please ensure model files exist at startup."
            )

        # Move tensors to the correct device
        img = image_tensor.to(self._device)
        tab = tabular_tensor.to(self._device)

        t0 = time.perf_counter()

        # ── Forward pass ──────────────────────────────────
        # The model returns (logits, gate)
        output = self._model(img, tab)
        
        # Safely handle models returning tuple or just logits
        if isinstance(output, tuple) or isinstance(output, list):
            logits = output[0]  # First element is logits
        else:
            logits = output

        elapsed_ms = (time.perf_counter() - t0) * 1000
        logger.debug(f"Forward pass completed in {elapsed_ms:.2f} ms")

        # ── Softmax → probabilities ───────────────────────
        probs = F.softmax(logits, dim=1).squeeze(0).cpu().numpy()  # shape: (num_classes,)

        top_idx = int(np.argmax(probs))
        confidence = float(probs[top_idx])

        # ── Decode label ──────────────────────────────────
        predicted_label = self._le_diagnostic.inverse_transform([top_idx])[0]

        # ── Build full probability dict ───────────────────
        classes = self.diagnostic_classes
        all_probs: Dict[str, float] = {
            classes[i]: float(probs[i]) for i in range(len(classes))
        }

        logger.info(
            f"Prediction: {predicted_label} (confidence={confidence:.3f}) | "
            f"inference={elapsed_ms:.1f} ms"
        )

        return predicted_label, confidence, all_probs

# ── Global singleton instance ─────────────────────────────────────────────────
# Instantiated once; .load() is called during FastAPI lifespan startup.
model_service = ModelService()
