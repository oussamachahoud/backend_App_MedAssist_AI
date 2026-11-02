# 📱 MedAssist AI V2 — Mobile API Integration & Implementation Specification
## Complete Backend-to-Frontend Contract for Flutter (`app_PFE_frontend`)

> **Document Version**: 2.0.0  
> **Target Framework**: Flutter 3.x / Dart (GetX Architecture)  
> **Backend Engine**: FastAPI 0.115 + PyTorch Multimodal EfficientNet-B3 + PostgreSQL 16 + MinIO Storage  
> **Date**: November 1, 2026  
> **Workspace Alignment**: `backend_App_MedAssist_AI` ➔ `app_PFE_frontend`

---

## 1. 🌐 Network Configuration & Base URLs

### 1.1 Development & Testing Environments
| Target Platform | Base URL | Notes |
|---|---|---|
| **Android Emulator** | `http://10.0.2.2:8000/api/v1` | Android loopback alias to host machine `localhost` |
| **iOS Simulator** | `http://127.0.0.1:8000/api/v1` | Mac host localhost |
| **Physical Android Device (LAN)** | `http://<YOUR_LAN_IP>:8000/api/v1` | e.g. `http://192.168.1.15:8000/api/v1` (Must allow port 8000 in Windows Firewall) |
| **Cloud / Cloudflare Tunnel** | `https://api.medassist.dz/api/v1` | When production tunnel is active |

> [!IMPORTANT]
> The Flutter app should configure `baseUrl` dynamically or in `lib/core/values/constants.dart`. In Debug mode, it can fall back to `10.0.2.2:8000/api/v1`. In Release builds, hardcoded internal dev IPs must never be exposed.

---

## 2. 🔐 Authentication & Session Management

### 2.1 Clinician Login
- **Endpoint**: `POST /api/v1/auth/login`
- **Content-Type**: `application/json`
- **Request Body**:
```json
{
  "email": "dr.benali@chu-oran.dz",
  "password": "DoctorPass123!"
}
```
- **Success Response (200 OK)**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": "530aa50c-3789-4557-a7a3-84e175e57c27",
    "email": "dr.benali@chu-oran.dz",
    "role": "doctor",
    "status": "active",
    "must_change_password": false,
    "created_at": "2026-11-01T12:00:00Z",
    "profile": {
      "full_name": "Dr. Benali Fatima Zohra",
      "doctor_type": "specialist_dermatologist",
      "specialization": "Dermatology & Venereology",
      "license_number": "ORD-31-SPEC-9912",
      "institution_name": "EHU 1er Novembre 1954, Oran",
      "phone": "+213 41 42 11 00",
      "wilaya": "31"
    }
  }
}
```
- **Error Responses**:
  - `401 Unauthorized`: Invalid email or password (`{"detail": "Incorrect email or password"}`).
  - `403 Forbidden`: Account is `pending_verification` or `suspended` (`{"detail": "Account is pending verification by admin"}`).

### 2.2 Clinician Self-Registration (Doctor Stepper)
- **Endpoint**: `POST /api/v1/auth/register`
- **Content-Type**: `application/json`
- **Request Body**:
```json
{
  "email": "dr.new@chu-alger.dz",
  "password": "SecurePassword123!",
  "full_name": "Dr. Amine Taleb",
  "doctor_type": "general_practitioner",
  "specialization": "General Medicine",
  "license_number": "ORD-16-GP-5512",
  "institution_name": "Polyclinique Sidi M'Hamed, Alger",
  "phone": "+213 555 12 34 56",
  "wilaya": "16"
}
```
- **Success Response (201 Created)**:
```json
{
  "message": "Account created successfully. Awaiting administrator verification.",
  "user_id": "99f8d123-...",
  "status": "pending_verification"
}
```

### 2.3 Token Auto-Refresh Interceptor (GetConnect / Dio)
- **Endpoint**: `POST /api/v1/auth/refresh`
- **Request Body**: `{"refresh_token": "<SAVED_REFRESH_TOKEN>"}`
- **Response (200 OK)**: Returns new `access_token` and `refresh_token`.
- **Flutter Flow**: If any request fails with `401 Unauthorized`, intercept the response, attempt refresh once. If successful, replay original request. If refresh fails, clear `FlutterSecureStorage` and redirect user to `/login`.

### 2.4 Clinician Session Termination (Logout)
- **Endpoint**: `POST /api/v1/auth/logout`
- **Authorization**: `Bearer <access_token>`
- **Content-Type**: `application/json`
- **Request Body**:
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```
- **Response (200 OK)**: `{"message": "Logged out successfully"}`
- **Flutter Flow**: Clears local storage tokens via `LocalStorageProvider.clearTokens()` and navigates to `/login`.

### 2.5 Force Password Change (Security Policy)
- **Endpoint**: `PUT /api/v1/auth/change-password`
- **Authorization**: `Bearer <access_token>`
- **Content-Type**: `application/json`
- **Request Body**:
```json
{
  "current_password": "TemporaryPassword123!",
  "new_password": "NewStrongPassword2026!"
}
```
- **Response (200 OK)**: `{"message": "Password changed successfully"}`
- **Flutter Flow**: Validates new password length (≥ 8 chars), calls endpoint, updates profile state, and redirects to `/main`.

---

## 3. 🔬 Multimodal Clinical Inference (`/predict`)

### 3.1 Submission Specification
- **Endpoint**: `POST /api/v1/predict` (also available at root `/predict` for legacy compatibility)
- **Authorization**: `Bearer <access_token>` (Optional for guest check, required for database persistence)
- **Content-Type**: `multipart/form-data`
- **Form Fields**:
  - `file`: Binary file (Required — JPEG/PNG dermoscopy or clinical photo, max 10 MB).
  - `age`: Float (Required — patient age, 0 to 120).
  - `sex`: String (`male`, `female`, `unknown`).
  - `localization`: String (`scalp`, `face`, `ear`, `neck`, `chest`, `abdomen`, `back`, `upper extremity`, `lower extremity`, `hand`, `foot`, `acral`, `genital`, `unknown`).
  - `diameter_1`: Float (Optional — largest lesion diameter in mm, 0 to 200).
  - `grew`: Boolean string (`true`, `false`).
  - `bleed`: Boolean string (`true`, `false`).
  - `elevation`: Boolean string (`true`, `false`) — palpable/elevated lesion indicator.
  - `skin_cancer_history`: Boolean string (`true`, `false`) — prior personal skin cancer history.
  - `patient_id`: String (Optional — UUID or patient_code DZ-XX-PXXXX).
  - `lesion_tag`: String (Optional — custom clinical tag, max 100 chars).
  - `use_tta`: Boolean string (`true`, `false` — default `false`, test-time augmentation x8).

### 3.2 Full Response Structure
```json
{
  "predicted_label": "MEL",
  "predicted_label_full": "Melanoma",
  "confidence": 0.892,
  "all_probabilities": [
    {"label": "MEL", "full_name": "Melanoma", "probability": 0.892},
    {"label": "NEV", "full_name": "Nevus", "probability": 0.054},
    {"label": "BCC", "full_name": "Basal Cell Carcinoma", "probability": 0.030},
    {"label": "SCC", "full_name": "Squamous Cell Carcinoma", "probability": 0.012},
    {"label": "ACK", "full_name": "Actinic Keratosis", "probability": 0.008},
    {"label": "SEK", "full_name": "Seborrheic Keratosis", "probability": 0.004}
  ],
  "predicted_region": null,
  "risk_level": "CRITICAL",
  "risk_color": "#7c3aed",
  "risk_explanation": "Melanoma — highly aggressive cutaneous malignancy requiring urgent intervention.",
  "recommendations": [
    "URGENT EMERGENCY: Immediate specialist referral to dermatologist/oncologist."
  ],
  "suggest_referral": true,
  "risk_escalated": false,
  "analysis_id": "f8a12345-6789-4abc-def0-123456789abc",
  "image_url": "/uploads/analyses/f8a12345-6789-4abc-def0-123456789abc.jpg",
  "gradcam_url": null,
  "patient_id": "DZ-16-P0102",
  "lesion_tag": "Upper Back Lesion (11.5mm)",
  "inference_time_ms": 131.5,
  "timestamp": "2026-11-01T14:30:00Z"
}
```

### 3.3 Diagnostic Classes (6-Class Thesis Taxonomy)
| Acronym | Scientific Name | Clinical Category | Thesis Dataset Source |
|---|---|---|---|
| **MEL** | Melanoma | Malignant (High/Critical Risk) | ISIC 2019 / HAM10000 |
| **BCC** | Basal Cell Carcinoma | Malignant (Moderate/High Risk) | ISIC 2019 / PAD-UFES-20 |
| **SCC** | Squamous Cell Carcinoma | Malignant (High Risk) | ISIC 2019 / HAM10000 |
| **ACK** | Actinic Keratosis | Pre-malignant (Moderate Risk) | ISIC 2019 / PAD-UFES-20 |
| **NEV** | Melanocytic Nevus | Benign (Low Risk) | HAM10000 |
| **SEK** | Seborrheic Keratosis | Benign (Low Risk) | ISIC 2019 / HAM10000 |

### 3.4 Risk Levels
1. `LOW` (Green): Reassuring benign lesions (NEV, SEK).
2. `MODERATE` (Amber): Pre-malignant lesions requiring monitoring (ACK).
3. `HIGH` (Red-Orange): Confirmed non-melanoma skin cancers (BCC, SCC).
4. `CRITICAL` (Deep Crimson): Suspected or high-confidence malignant melanoma (MEL).
5. `INCONCLUSIVE` (Slate Grey): Borderline confidence or atypical artifact; mandates physical examination and clinical referral.

### 3.5 Offline MinIO & Local Storage Fallback
When developing or testing locally without a live MinIO service (Port 9000), the backend automatically falls back to storing images and Grad-CAM visualizations on the local filesystem (`/uploads/`).
- The backend serves these directly via FastAPI StaticFiles: `GET /uploads/{object_name}`.
- The Flutter client's image loader should handle both absolute MinIO/S3 URLs (`http://.../bucket/...`) and relative paths (`/uploads/...`), prepending the configured `baseUrl` when receiving relative paths.

### 3.6 Preloaded Benchmark Clinical Samples (PAD-UFES-20)
For offline validation and instant clinical demonstrations without requiring real camera uploads during presentations, 6 authentic benchmark lesion samples from PAD-UFES-20 are bundled directly in the Flutter assets directory:
- Location: `assets/samples/pad_ufes_20/`
- Manifest: `assets/samples/pad_ufes_20/samples_manifest.json`
- Lesion Classes: `MEL`, `BCC`, `SCC`, `NEV`, `SEK`, `ACK` with associated clinical metadata (patient ID, age, sex, lesion site, elevation).
- The mobile UI should provide a "Load Clinical Benchmark Sample" quick picker to populate the form and image instantly.

---

## 4. 👥 Patient Management & Lesion Timelines

### 4.1 Create Patient
- **Endpoint**: `POST /api/v1/patients/`
- **Request Body**:
```json
{
  "patient_code": "DZ-31-P0105",
  "birth_year": 1968,
  "sex": "male",
  "notes": "Patient with previous history of severe sun exposure and fair skin type II."
}
```

### 4.2 List Patients
- **Endpoint**: `GET /api/v1/patients/?search=DZ-31&page=1&page_size=20`
- **Response**: List of patients belonging to the authenticated clinician.

### 4.3 Patient Details & Lesion Evolution Timeline
- **Endpoint**: `GET /api/v1/patients/{patient_id}`
- **Response**: Detailed patient object (`PatientDetailResponse`) including an embedded chronological `timeline` array of scans with date, lesion_tag, predicted_class, confidence, risk_level, and diameter measurements for visual timeline charting.

---

### 4.4 Public Verified Doctor Directory
- **Endpoint**: `GET /api/v1/public/doctors`
- **Query Parameters**:
  - `wilaya`: Optional string filter (e.g. `16`, `31`).
  - `doctor_type`: Optional string filter (`general_practitioner` | `specialist_dermatologist`).
- **Response (200 OK)**: Array of public verified doctors with `full_name`, `specialization`, `institution_name`, `wilaya`.

### 4.5 Public QR Follow-Up Verification
- **Endpoint**: `GET /api/v1/public/follow-up/{token}`
- **Response (200 OK)**:
```json
{
  "analysis_id": "c1f2e3d4-...",
  "predicted_class": "MEL",
  "confidence": 0.895,
  "risk_level": "CRITICAL",
  "created_at": "2026-11-01T12:00:00Z",
  "next_followup_date": "2026-12-01",
  "doctor_confirmed": true,
  "doctor_diagnosis": "Malignant Melanoma (Breslow 1.8mm)",
  "doctor_institution": "CHU Mustapha Bacha, Alger"
}
```

---

## 5. 🔄 Telemedicine Referral System (GP ➔ Specialist)

### 5.1 Create Referral (General Practitioner)
- **Endpoint**: `POST /api/v1/referrals`
- **Request Body**:
```json
{
  "analysis_id": "f8a12345-6789-4abc-def0-123456789abc",
  "specialist_id": "530aa50c-3789-4557-a7a3-84e175e57c27",
  "referral_note": "Suspicious pigmented lesion on upper back showing asymmetry. Suspecting melanoma. Requesting confirmation and biopsy recommendation."
}
```
- Note: `specialist_id` is optional; if omitted, the referral is routed to the available regional pool.

### 5.2 Specialist Referral Response
- **Endpoint**: `PUT /api/v1/referrals/{referral_id}/respond`
- **Request Body**:
```json
{
  "status": "completed",
  "specialist_response": "High clinical suspicion of nodular melanoma. Recommend immediate surgical excision with 2cm safety margins and histological staging."
}
```
- Allowed `status` values: `"completed"`, `"accepted"`, `"cancelled"`.

### 5.3 Doctor Feedback (Concordance Ground Truth)
- **Endpoint**: `PUT /api/v1/analyses/{analysis_id}/feedback`
- **Request Body**:
```json
{
  "doctor_confirmed": true,
  "doctor_diagnosis": "MEL",
  "biopsy_performed": true,
  "biopsy_result": "Breslow 1.8mm, Clark Level IV",
  "next_followup_date": "2026-12-01"
}
```

---

## 6. 📦 Platform Resources & Auto-Update Engine

### 6.1 Check Active Release Binary
- **Endpoint**: `GET /api/v1/public/platform-resources`
- **Auth**: None required (Public)
- **Response Structure**:
```json
{
  "video_walkthrough_url": "https://youtube.com/shorts/tRxtxYG6B8c?si=AkQqDnujgsMIfaL2",
  "mobile_apk_url": "/dashboard/assets/downloads/MedAssist-AI.apk",
  "landing_page_url": "/dashboard/landing.html",
  "thesis_en_url": "/dashboard/assets/docs/Thesis_Master_GLAA_EN.pdf",
  "thesis_fr_url": "/dashboard/assets/docs/Thesis_Master_GLAA_FR.pdf",
  "thesis_ar_url": "/dashboard/assets/docs/Thesis_Master_GLAA_AR.pdf",
  "apk_file_size": "55.57 MB",
  "apk_original_name": "MedAssist-AI.apk",
  "apk_uploaded_at": "2026-11-01T12:00:00Z",
  "announcement": "MedAssist AI V2.0 Telemedicine & Multimodal Clinical Decision Support System Active"
}
```
- **Flutter In-App Updater**:
  - Compare local package version (`package_info_plus`) or build timestamp with `apk_uploaded_at`.
  - If a newer APK release exists on the server, display a non-blocking SnackBar or Banner: *"A new version of MedAssist AI is available. [Download APK]"*.

---

## 7. 🧪 Verified Test & Demo Credentials

| Role | Email | Password | Assigned Clinical Institution |
|---|---|---|---|
| **System Admin** | `admin@medassist.dz` | `Admin@MedAssist2026!` | National Telemedicine Center |
| **Specialist Dermatologist** | `dr.benali@chu-oran.dz` | `DoctorPass123!` | EHU 1er Novembre 1954, Oran |
| **General Practitioner (GP)** | `doctor.amara@medassist.dz` | `DoctorPass123!` | Polyclinique Sidi M'Hamed, Alger |
| **Specialist Dermatologist** | `dr.mansouri@chu-alger.dz` | `DoctorPass123!` | CHU Mustapha Bacha, Alger |
| **General Practitioner (GP)** | `dr.khellaf@clinic-setif.dz` | `DoctorPass123!` | Clinique El Hikma, Sétif |

---

## 8. 📋 Readiness Checklist for Mobile Transition

- [x] All 119 backend & dashboard tests passing (`pytest tests/`).
- [x] Database sanitized: 0 pytest junk accounts, 10 authentic Algerian records preserved.
- [x] Multimodal inference pipeline returns Grad-CAM base64 + 6-class probabilities + risk assessment.
- [x] Telemedicine referrals fully bidirectional (GP sent ➔ Specialist received ➔ Specialist response).
- [x] Public Platform Resources endpoint provides direct APK download, video demo, and thesis PDF links.
- [x] Default language configured to English (`en`) with seamless French and Arabic localization.

