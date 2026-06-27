# Skin Lesion AI API

Production-ready **FastAPI** backend for multimodal skin lesion classification.

Combines dermoscopy image analysis with patient metadata (age, sex, anatomical site)
to classify skin lesions into 6 diagnostic categories with clinical risk assessment.

---

## Diagnostic Classes

| Code | Full Name                 | Risk Level |
|------|---------------------------|------------|
| NEV  | Nevus                     | 🟢 LOW     |
| SEK  | Seborrheic Keratosis      | 🟢 LOW     |
| ACK  | Actinic Keratosis         | 🟡 MODERATE|
| BCC  | Basal Cell Carcinoma      | 🔴 HIGH    |
| SCC  | Squamous Cell Carcinoma   | 🔴 HIGH    |
| MEL  | Melanoma                  | 🟣 CRITICAL|

---

## Quick Start

### 1. Install dependencies
```bash
cd 02_Backend_API
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

### 2. Add model files
Place the trained model artifacts in `app/ml_models/`:
```
app/ml_models/
├── multimodal_model.pth    # PyTorch model weights
├── le_diagnostic.pkl       # LabelEncoder for diagnostic classes
└── le_region.pkl           # LabelEncoder for body region classes
```

### 3. Configure environment
Edit `.env` or set environment variables:
```env
MODEL_PATH=app/ml_models/multimodal_model.pth
LE_DIAGNOSTIC_PATH=app/ml_models/le_diagnostic.pkl
LE_REGION_PATH=app/ml_models/le_region.pkl
ALLOWED_ORIGINS=http://localhost:3000
```

### 4. Run
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API available at: http://localhost:8000
Swagger docs at:  http://localhost:8000/docs

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

| Field        | Type    | Required | Description                      |
|--------------|---------|----------|----------------------------------|
| file         | file    | ✅       | Dermoscopy image (JPEG/PNG)      |
| age          | float   | ✅       | Patient age (0–120)              |
| sex          | string  | ❌       | `male` / `female` / `unknown`    |
| localization | string  | ❌       | Anatomical site (e.g. `back`)    |
| patient_id   | string  | ❌       | Optional patient identifier      |

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

## Project Structure

```
02_Backend_API/
├── app/
│   ├── main.py                    # FastAPI app + lifespan
│   ├── core/
│   │   ├── config.py              # Settings (pydantic-settings)
│   │   ├── security.py            # CORS + request-size limit
│   │   └── logging.py             # Loguru setup
│   ├── models/
│   │   ├── schemas.py             # Enums: DiagnosticLabel, RiskLevel, etc.
│   │   ├── request.py             # Pydantic request models
│   │   └── response.py            # Pydantic response models
│   ├── services/
│   │   ├── model_service.py       # Model loading + inference
│   │   ├── preprocessing_service.py  # Image pipeline + tabular encoder
│   │   └── risk_assessment.py     # Risk level calculation
│   ├── api/
│   │   ├── dependencies.py        # Dependency injection
│   │   └── endpoints/
│   │       ├── health.py
│   │       ├── predict.py
│   │       └── model_info.py
│   └── ml_models/                 # Model artifacts (gitignored)
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
