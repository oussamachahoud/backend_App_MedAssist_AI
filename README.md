# MedAssist AI — Skin Lesion Backend API (V6.0)

Production-ready **FastAPI** backend for multimodal skin lesion classification using **MedAssist AI V6.0**.

Combines dermoscopy image analysis with 7 clinical patient metadata features via a
**Gated Cross-Attention Fusion** multimodal deep learning model.

---

## What's New in V6.0

| Component | Change |
|-----------|--------|
| **Architecture** | `MedAssistModel` — EfficientNet-B3 backbone + GeM pooling + GatedCrossAttentionFusion |
| **Metadata** | 7 clinical features with `meta_mask` (missing feature masking) |
| **Image size** | 256×256 (was 224×224) |
| **Preprocessing** | Shades-of-Gray + DullRazor hair removal + CLAHE |
| **Thresholds** | Per-class decision thresholds optimised on validation set |
| **Training** | Stochastic Weight Averaging (SWA) + WeightedFocalLoss (γ=2.5, ε=0.05) |
| **Macro F1** | **0.7315** on held-out test set (654 samples, 6 classes) |

---

## Diagnostic Classes

| Code | Full Name                 | Risk Level  |
|------|---------------------------|-------------|
| NEV  | Nevus                     | 🟢 LOW      |
| SEK  | Seborrheic Keratosis      | 🟢 LOW      |
| ACK  | Actinic Keratosis         | 🟡 MODERATE |
| BCC  | Basal Cell Carcinoma      | 🔴 HIGH     |
| SCC  | Squamous Cell Carcinoma   | 🔴 HIGH     |
| MEL  | Melanoma                  | 🟣 CRITICAL |

---

## Quick Start

### 1. Install dependencies
```bash
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

### 2. Place model artifacts in `app/ml_models/`
Download your trained model files and rename/place them:
```
app/ml_models/
├── multimodal_model.pth     # swa_model_V6.0.pth (from notebook 04b)
├── diagnostic_encoder.pkl   # from notebook 02 (preprocessed/diagnostic_encoder.pkl)
├── imputer.pkl              # from notebook 02 (preprocessed/imputer.pkl)
├── scaler.pkl               # from notebook 02 (preprocessed/scaler.pkl)
└── thresholds_V6.0.json     # from notebook 04b (optimised per-class thresholds)
```

> **Note:** Large binary files (`.pth`, `.pkl`) are git-ignored. `thresholds_V6.0.json` is tracked.

### 3. Configure environment
Edit `.env` or set environment variables:
```env
MODEL_PATH=app/ml_models/multimodal_model.pth
LE_DIAGNOSTIC_PATH=app/ml_models/diagnostic_encoder.pkl
IMPUTER_PATH=app/ml_models/imputer.pkl
SCALER_PATH=app/ml_models/scaler.pkl
THRESHOLDS_PATH=app/ml_models/thresholds_V6.0.json
ALLOWED_ORIGINS=http://localhost:3000
```

### 4. Run
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API:   http://localhost:8000  
Docs:  http://localhost:8000/docs  
Health: http://localhost:8000/api/v1/health

---

## 🐳 Docker Deployment (4GB RAM Constraints)

This project is optimized to run on small VPS instances with strict memory constraints (4GB RAM).
The Docker setup uses a **CPU-only PyTorch build** and strict thread/worker limits to prevent OOM (Out-of-Memory) crashes.

### 1. Build and Run via Docker Compose (Recommended)
Make sure you have placed all 5 model artifacts in `app/ml_models/` before building.
```bash
# Build the CPU-optimized image and start the container
docker-compose up -d --build
```
> The `docker-compose.yml` automatically limits memory to 3.5GB. If the container exceeds this, it restarts cleanly rather than freezing the host server.

### 2. Manual Docker Build
```bash
docker build -t medassist-api:v6 .
docker run -d -p 8000:8000 --name medassist-api -m 3.5g medassist-api:v6
```

---

## API Endpoints

| Method | Endpoint              | Description                    |
|--------|-----------------------|--------------------------------|
| GET    | `/`                   | Root welcome message           |
| GET    | `/api/v1/health`      | Health check + model status    |
| GET    | `/api/v1/model/info`  | Model architecture & classes   |
| POST   | `/api/v1/predict`     | Run skin lesion prediction     |

### POST /api/v1/predict

**Request** — `multipart/form-data`:

| Field                  | Type    | Required | Description                              |
|------------------------|---------|----------|------------------------------------------|
| `file`                 | file    | ✅       | Dermoscopy image (JPEG/PNG, max 10 MB)   |
| `age`                  | float   | ✅       | Patient age (0–120)                      |
| `sex`                  | string  | ❌       | `male` / `female` / `unknown`            |
| `localization`         | string  | ❌       | Anatomical site (e.g. `back`)            |
| `grew`                 | bool    | ❌       | Was the lesion growing?                  |
| `bleed`                | bool    | ❌       | Does the lesion bleed?                   |
| `diameter_1`           | float   | ❌       | Largest diameter in cm                   |
| `skin_cancer_history`  | bool    | ❌       | Prior skin cancer history?               |
| `elevation`            | bool    | ❌       | Is the lesion elevated?                  |
| `patient_id`           | string  | ❌       | Optional patient identifier              |

> Missing optional fields are automatically imputed using training-set medians/modes.

**Response** example:
```json
{
  "predicted_label": "MEL",
  "predicted_label_full": "Melanoma",
  "confidence": 0.872,
  "all_probabilities": [
    {"label": "MEL", "full_name": "Melanoma", "probability": 0.872},
    {"label": "BCC", "full_name": "Basal Cell Carcinoma", "probability": 0.063}
  ],
  "risk_level": "CRITICAL",
  "risk_color": "#7c3aed",
  "risk_explanation": "Melanoma — highly aggressive. URGENT referral recommended.",
  "recommendations": ["URGENT: Seek immediate specialist care..."],
  "inference_time_ms": 34.7
}
```

---

## Docker

```bash
# Build and run
docker-compose up --build

# Run in background
docker-compose up -d

# View logs
docker-compose logs -f api
```

---

## Testing

```bash
pytest tests/ -v
```

---

## Notebooks

The `notebooks/` directory contains all training and evaluation notebooks:

| Notebook | Description |
|----------|-------------|
| `00_setup_environment_V6_0.ipynb`   | Environment setup & dependencies |
| `01_data_exploration_V6.0.ipynb`    | Dataset EDA (PAD-UFES-20, ISIC 2019, MCR-SL) |
| `02_preprocessing_V6.0.ipynb`       | Preprocessing pipeline, splits, class weights |
| `03_architecture_V6.0.ipynb`        | Model architecture definition |
| `03b_ham10000_pretrain_V6.0.ipynb`  | HAM10000 pretraining (optional) |
| `04a_training_phase1_V6.0.ipynb`    | Phase 1 training (frozen backbone) |
| `04b_training_phase2_V6_0_split.ipynb` | Phase 2 training (full fine-tune + SWA) |
| `05_evaluation_V6.0.ipynb`          | Final evaluation with TTA×8 + ensemble |

### V6.0 Evaluation Results (Test Set — 654 samples)

| Class | Precision | Recall | F1    |
|-------|-----------|--------|-------|
| ACK   | 0.7049    | 0.6615 | 0.6825 |
| BCC   | 0.8100    | 0.8804 | 0.8438 |
| MEL   | 0.7547    | 0.6154 | 0.6780 |
| NEV   | 0.7282    | 0.9530 | 0.8256 |
| SCC   | 0.6824    | 0.6444 | 0.6629 |
| SEK   | 0.7980    | 0.6172 | 0.6960 |
| **Macro** | **0.7464** | **0.7287** | **0.7315** |

---

## Project Structure

```
backend_App_MedAssist_AI/
├── app/
│   ├── main.py                         # FastAPI app + lifespan
│   ├── core/
│   │   ├── config.py                   # Settings (pydantic-settings)
│   │   ├── security.py                 # CORS + request-size limit
│   │   └── logging.py                  # Loguru setup
│   ├── models/
│   │   ├── schemas.py                  # Enums: DiagnosticLabel, RiskLevel, etc.
│   │   ├── request.py                  # Pydantic request models (7 features)
│   │   └── response.py                 # Pydantic response models
│   ├── services/
│   │   ├── architecture.py             # V6.0 model classes (MedAssistModel)
│   │   ├── model_service.py            # Model loading + V6.0 inference
│   │   ├── preprocessing_service.py    # Image pipeline + tabular encoder
│   │   └── risk_assessment.py          # Risk level calculation
│   ├── api/
│   │   ├── dependencies.py             # Dependency injection
│   │   └── endpoints/
│   │       ├── health.py
│   │       ├── predict.py              # V6.0 predict endpoint
│   │       └── model_info.py
│   └── ml_models/                      # Model artifacts (gitignored)
├── notebooks/                          # Training & evaluation Jupyter notebooks
├── tests/
│   ├── test_api.py
│   └── test_model_service.py
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env
└── README.md
```

---

## ⚠️ Medical Disclaimer

This API is intended as a **decision support tool** only.
All predictions must be reviewed by a qualified medical professional.
Do not use as a sole diagnostic tool.
