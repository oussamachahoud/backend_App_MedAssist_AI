# MedAssist AI — Clinical Skin Lesion Diagnostic & Telemedicine Platform (V2.0)

[![FastAPI](https://img.shields.io/badge/FastAPI-0.111+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.2+-EE4C2C.svg?logo=pytorch&logoColor=white)](https://pytorch.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1.svg?logo=postgresql&logoColor=white)](https://www.postgresql.org)
[![MinIO](https://img.shields.io/badge/MinIO-S3_Storage-C72C48.svg?logo=minio&logoColor=white)](https://min.io)
[![Docker](https://img.shields.io/badge/Docker-Compose_Ready-2496ED.svg?logo=docker&logoColor=white)](https://www.docker.com)
[![Tests](https://img.shields.io/badge/pytest-119_passed_(100%25)-brightgreen.svg)](https://docs.pytest.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An enterprise-grade, multimodal deep learning decision support and tele-dermatology platform for automated skin lesion categorization, clinical risk triage, patient record management, and secure second-opinion workflows.

> **Academic & Innovation Context**: Developed within the framework of Master 2 Software Engineering (GLAA) and the Algerian Ministerial Decree 1275 (*Un diplôme... une startup / un brevet*).

---

## 🌟 Core Architectural Features

* **Multimodal Deep Learning (V6.0)**: Integrates dermoscopy imaging with 7 patient clinical metadata features via a **Gated Cross-Attention Fusion** network.
* **Explainable AI (XAI)**: Generates high-resolution **Grad-CAM** visual saliency heatmaps overlaid on the original lesion images.
* **Role-Based Access Control (RBAC)**: Fine-grained permissions for `SUPER_ADMIN`, `DOCTOR` (clinicians/radiologists), and `PATIENT` roles with JWT access and refresh token lifecycle management.
* **Telemedicine & Second-Opinion Workflow**: Asynchronous referral management enabling primary physicians to transfer complex cases to specialized dermatologists.
* **Clinical Report Export**: Compiles high-fidelity, printable PDF clinical reports with QR verification tokens using ReportLab.
* **Embedded Web Dashboard**: Modern, lightweight, zero-dependency SPA (Vanilla JS + Modern CSS + Chart.js) served directly via FastAPI StaticFiles.
* **Offline-First & Resilience**: Zero-timeout polling fallback, structured HTTP error handling, and robust database transactions.

---

## 🧠 Diagnostic Classes & 5-Tier Risk Stratification

The deep learning engine classifies dermoscopy inputs into 6 pathological classes and stratifies clinical urgency:

| Code | Pathology | Risk Category | Indicator Color | Recommended Action |
|:---:|:---|:---:|:---:|:---|
| **NEV** | Nevus (Mole) | 🟢 `LOW` | `#10b981` | Routine annual skin examination |
| **SEK** | Seborrheic Keratosis | 🟢 `LOW` | `#10b981` | Benign lesion — reassure patient |
| **ACK** | Actinic Keratosis | 🟡 `MODERATE` | `#f59e0b` | Pre-malignant — cryotherapy or topical therapy |
| **BCC** | Basal Cell Carcinoma | 🔴 `HIGH` | `#ef4444` | Malignant — dermatologic surgery consultation |
| **SCC** | Squamous Cell Carcinoma | 🔴 `HIGH` | `#ef4444` | Malignant — biopsy and complete surgical excision |
| **MEL** | Melanoma | 🟣 `CRITICAL` | `#7c3aed` | Highly aggressive — URGENT oncology & surgical triage |

---

## 🏗️ Neural Network Architecture (V6.0)

```
[Dermoscopy Image (256x256)] ──► [EfficientNet-B3 Backbone + GeM Pooling] ──► Image Tokens (49x256) ──┐
                                                                                                       ▼
                                                                                           [Gated Cross-Attention] ──► [Classifier] ──► Logits
                                                                                                       ▲
[7 Clinical Features + Mask] ──► [Mask-Aware Tabular MLP Branch]          ──► Metadata Token (1x64) ───┘
```

* **Preprocessing Pipeline**: Shades-of-Gray illumination constancy ($p=6$), DullRazor hair removal, and Contrast Limited Adaptive Histogram Equalization (CLAHE).
* **Missing Feature Handling**: Binary missingness mask ($\mathbf{M} \in \{0, 1\}^7$) ensures imputed missing metadata features do not corrupt model predictions.
* **Training & Optimization**: Stochastic Weight Averaging (SWA), Weighted Focal Loss ($\gamma=2.5, \epsilon=0.05$), and per-class decision thresholds.
* **Test Evaluation**: Macro F1 score of **0.7315** across 6 diagnostic classes on the held-out test dataset (654 samples).

---

## 🚀 Quick Start (Local Setup)

### 1. Clone the repository & create environment
```bash
git clone https://github.com/Abderrahmane-Laidisista/backend_App_MedAssist_AI.git
cd backend_App_MedAssist_AI

python -m venv venv
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate
```

### 2. Install dependencies
```bash
# Install PyTorch CPU wheel:
pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch torchvision

# Install remaining dependencies:
pip install -r requirements.txt
```

### 3. Configure environment variables
Copy the template configuration file:
```bash
cp .env.example .env
```
Edit `.env` to configure your PostgreSQL and MinIO connection strings, or keep local defaults.

### 4. Apply Database Migrations (Alembic)
```bash
alembic upgrade head
```

### 5. Launch the Server
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

* **Interactive Swagger Documentation**: `http://localhost:8000/docs`
* **Alternative ReDoc UI**: `http://localhost:8000/redoc`
* **Embedded Web Dashboard**: `http://localhost:8000/dashboard/`
* **System Health Check**: `http://localhost:8000/api/v1/health`

---

## 🐳 Docker Deployment (Micro-VPS & 4GB+ RAM)

The container configuration is tuned for memory-constrained production VPS environments (CPU-only PyTorch, OpenMP thread limits, and automatic database migration).

### 1. Launch with Docker Compose
```bash
docker compose up -d --build
```

### 2. Check service status & logs
```bash
docker compose ps
docker compose logs -f backend
```

> **Note on Model Weights**: Ensure your model checkpoint (`multimodal_model.pth`) and encoder artifacts are placed in `app/ml_models/`. They are mounted read-only into the container via the `./app/ml_models:/app/app/ml_models:ro` volume.

---

## 📡 API Endpoints Overview

| Category | Method | Endpoint | Description |
|---|:---:|---|---|
| **Auth** | `POST` | `/api/v1/auth/login` | Clinician login & JWT token pair issuance |
| | `POST` | `/api/v1/auth/register` | Super Admin doctor onboarding |
| | `POST` | `/api/v1/auth/refresh` | Rotate access token via refresh token |
| | `POST` | `/api/v1/auth/logout` | Revoke active refresh token |
| | `PUT` | `/api/v1/auth/change-password` | Force password update on first login |
| | `GET` | `/api/v1/auth/me` | Fetch active user profile and roles |
| **Inference** | `POST` | `/api/v1/analyses/predict` | Multimodal prediction (Image + 7 Clinical Features) |
| | `GET` | `/api/v1/analyses/{id}` | Retrieve diagnosis details & Grad-CAM URI |
| | `PUT` | `/api/v1/analyses/{id}/feedback` | Doctor confirmation, ground truth & follow-up date |
| | `GET` | `/api/v1/analyses/{id}/export-pdf` | Download official medical PDF report |
| **Telemedicine** | `POST` | `/api/v1/telemedicine/referrals` | Submit case for second-opinion consultation |
| | `GET` | `/api/v1/telemedicine/referrals/received`| Review pending consultation requests |
| | `PUT` | `/api/v1/telemedicine/referrals/{id}/respond` | Submit specialist second opinion |
| **Patients** | `GET` | `/api/v1/patients/{id}` | Patient clinical profile and diagnostic history |
| **Public** | `GET` | `/api/v1/public/doctors` | Verified clinician directory |
| | `GET` | `/api/v1/public/follow-up/{token}` | QR code public scan validation |
| **System** | `GET` | `/api/v1/health` | Service health, MinIO status & model readiness |
| | `GET` | `/api/v1/model/info` | V6.0 neural architecture details |

---

## 🧪 Automated Testing Suite

The backend includes a comprehensive pytest suite covering model inference, preprocessing, database models, RBAC authentication, and API endpoints:

```bash
pytest tests/ -v
```

**Results: 119 passed in ~22 seconds (100% pass rate).**

---

## 📂 Repository Layout

```
backend_App_MedAssist_AI/
├── .github/workflows/          # Automated GitHub Actions CI/CD pipeline
├── alembic/                    # Database migration version scripts
├── app/
│   ├── api/v1/endpoints/       # FastAPI route handlers (auth, analyses, telemedicine, etc.)
│   ├── core/                   # Security, JWT, DB engine, and configuration
│   ├── db_models/              # SQLAlchemy relational models (User, Analysis, Patient, Referral)
│   ├── ml_models/              # Model weights (.pth, .pkl, thresholds_V6.0.json)
│   ├── models/                 # Request/response DTO schemas
│   ├── schemas/                # Telemedicine, auth, and feedback validation schemas
│   ├── services/               # Deep learning inference, Grad-CAM, PDF, and MinIO storage
│   └── main.py                 # Application factory & lifespan events
├── dashboard/                  # Embedded Web Dashboard (HTML5, Vanilla JS, Tailwind CDN)
├── docs_v2/                    # Comprehensive Software Engineering & UML Thesis Documents
├── notebooks/                  # Model training, ablation, and evaluation Jupyter notebooks
├── tests/                      # Automated pytest test cases (119 tests)
├── .dockerignore
├── .env.example                # Environment variable configuration template
├── docker-compose.yml          # Multi-container orchestration (Backend + Postgres + MinIO)
├── docker-entrypoint.sh        # Container startup migration runner
├── Dockerfile                  # CPU-optimized multi-layer container definition
├── requirements.txt            # Python dependencies
└── README.md                   # Platform documentation
```

---

## ⚖️ License & Medical Disclaimer

This software is released under the [MIT License](LICENSE).

> **⚠️ Medical Decision Support Disclaimer**:  
> MedAssist AI is engineered as an **adjunctive clinical decision support system** intended for use by qualified healthcare practitioners. It does **not** replace standard histopathological biopsy, clinical dermatoscopy, or independent medical judgment.
