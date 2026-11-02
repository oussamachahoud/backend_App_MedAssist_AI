"""
tests/test_predict_v2.py
Tests for Phase 3:
- V2.0 Clinical Risk Engine (INCONCLUSIVE risk level, referral suggestions)
- Grad-CAM++ Explainability Service (saliency heatmap overlay, MinIO & DB persistence)
- Telemedicine Integration on POST /api/v1/predict (doctor authentication, DB AnalysisRecord, MinIO storage)
"""

import io
import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.core.database import SessionLocal
from app.core.security import create_access_token
from app.db_models.analysis import AnalysisRecord
from app.db_models.user import DoctorProfile, DoctorType, User, UserRole, UserStatus
from app.main import app
from app.models.schemas import DiagnosticLabel, RiskLevel
from app.services.gradcam_service import generate_and_store_gradcam, generate_gradcam_heatmap
from app.services.risk_engine import evaluate_clinical_risk


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="module")
def sample_image_bytes():
    """Generate in-memory JPEG image bytes."""
    img = Image.new("RGB", (256, 256), color=(200, 140, 120))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture(scope="module")
def active_doctor_user(db_session):
    """Create a verified active doctor for testing."""
    unique_id = uuid.uuid4().hex[:8]
    user = User(
        email=f"active_doc_{unique_id}@medassist.dz",
        password_hash="$2b$12$dummyhashforactiveuserdoctor2026",
        role=UserRole.DOCTOR,
        status=UserStatus.ACTIVE,
    )
    db_session.add(user)
    db_session.flush()

    profile = DoctorProfile(
        user_id=user.id,
        full_name=f"Dr. Active {unique_id}",
        doctor_type=DoctorType.GENERAL_PRACTITIONER,
        license_number=f"LIC-{unique_id}",
    )
    db_session.add(profile)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="module")
def doctor_token(active_doctor_user):
    return create_access_token(user_id=active_doctor_user.id, role="doctor")


@pytest.fixture(scope="module")
def client():
    with patch("app.services.model_service.model_service.load"), \
         patch("app.services.storage_service.storage_service.ensure_bucket_exists"):
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c


# ── 1. V2 Risk Engine Tests ───────────────────────────────────────────────────

class TestRiskEngineV2:
    """Unit tests for V2.0 Clinical Risk Engine."""

    def test_high_confidence_benign_no_referral(self):
        eval_nev = evaluate_clinical_risk(DiagnosticLabel.NEV, confidence=0.92)
        assert eval_nev.risk_level == RiskLevel.LOW
        assert eval_nev.suggest_referral is False
        assert eval_nev.risk_escalated is False

        eval_sek = evaluate_clinical_risk(DiagnosticLabel.SEK, confidence=0.88)
        assert eval_sek.risk_level == RiskLevel.LOW
        assert eval_sek.suggest_referral is False

    def test_high_confidence_malignant_suggests_referral(self):
        eval_bcc = evaluate_clinical_risk(DiagnosticLabel.BCC, confidence=0.85)
        assert eval_bcc.risk_level == RiskLevel.HIGH
        assert eval_bcc.suggest_referral is True

        eval_mel = evaluate_clinical_risk(DiagnosticLabel.MEL, confidence=0.94)
        assert eval_mel.risk_level == RiskLevel.CRITICAL
        assert eval_mel.suggest_referral is True

    def test_low_confidence_triggers_inconclusive_and_referral(self):
        # Confidence < 0.50 triggers INCONCLUSIVE
        eval_low = evaluate_clinical_risk(DiagnosticLabel.NEV, confidence=0.42)
        assert eval_low.risk_level == RiskLevel.INCONCLUSIVE
        assert eval_low.risk_escalated is True
        assert eval_low.suggest_referral is True
        assert eval_low.base_risk == RiskLevel.LOW
        assert "INCONCLUSIVE" in eval_low.explanation
        assert "LOW" in eval_low.explanation


# ── 2. Grad-CAM++ Service Tests ───────────────────────────────────────────────

class TestGradCAMService:
    """Unit and mock tests for Grad-CAM++ generation and MinIO/DB persistence."""

    def test_generate_gradcam_heatmap_bytes(self, sample_image_bytes):
        png_bytes = generate_gradcam_heatmap(sample_image_bytes, target_class_idx=0)
        assert isinstance(png_bytes, bytes)
        assert len(png_bytes) > 0

        # Verify output is a valid PNG image
        img = Image.open(io.BytesIO(png_bytes))
        assert img.format == "PNG"
        assert img.size == (256, 256)

    def test_generate_and_store_gradcam_updates_db(self, db_session, sample_image_bytes, active_doctor_user):
        analysis_id = uuid.uuid4()
        record = AnalysisRecord(
            id=analysis_id,
            doctor_id=active_doctor_user.id,
            image_storage_key="analyses/test.jpg",
            predicted_class="MEL",
            confidence=0.89,
            all_probabilities={"MEL": 0.89, "NEV": 0.11},
            risk_level="CRITICAL",
            risk_escalated=False,
            inference_time_ms=25.0,
            model_version="2.0.0",
        )
        db_session.add(record)
        db_session.commit()

        with patch("app.services.storage_service.storage_service.upload_image") as mock_upload:
            mock_upload.return_value = f"gradcam/{analysis_id}.png"
            key = generate_and_store_gradcam(
                analysis_id=analysis_id,
                image_bytes=sample_image_bytes,
                target_class="MEL",
            )
            assert key == f"gradcam/{analysis_id}.png"

        db_session.refresh(record)
        assert record.gradcam_storage_key == f"gradcam/{analysis_id}.png"


# ── 3. Predict Endpoint V2 Tests ──────────────────────────────────────────────

class TestPredictEndpointV2:
    """Integration tests for POST /api/v1/predict with V2 telemedicine features."""

    def test_unauthenticated_prediction_fails_401(self, client: TestClient, sample_image_bytes):
        response = client.post(
            "/api/v1/predict",
            data={"age": "45", "sex": "male", "localization": "back"},
            files={"file": ("lesion.jpg", sample_image_bytes, "image/jpeg")},
        )
        assert response.status_code == 401
        assert "authenticated" in response.json()["detail"].lower() or "credentials" in response.json()["detail"].lower()

    def test_authenticated_doctor_prediction_persists_to_db_and_storage(
        self,
        client: TestClient,
        doctor_token: str,
        active_doctor_user: User,
        sample_image_bytes: bytes,
        db_session,
    ):
        with patch("app.services.storage_service.storage_service.upload_image") as mock_upload:
            mock_upload.return_value = "analyses/dummy.jpg"

            response = client.post(
                "/api/v1/predict",
                headers={"Authorization": f"Bearer {doctor_token}"},
                data={
                    "age": "52",
                    "sex": "female",
                    "localization": "face",
                    "lesion_tag": "Cheek Lesion",
                },
                files={"file": ("lesion.jpg", sample_image_bytes, "image/jpeg")},
            )

        assert response.status_code == 200
        data = response.json()

        assert data["analysis_id"] is not None
        analysis_id = uuid.UUID(data["analysis_id"])

        # Verify AnalysisRecord in PostgreSQL
        record = db_session.query(AnalysisRecord).filter(AnalysisRecord.id == analysis_id).first()
        assert record is not None
        assert record.doctor_id == active_doctor_user.id
        assert record.lesion_tag == "Cheek Lesion"
        assert record.predicted_class == data["predicted_label"]
        assert record.confidence == pytest.approx(data["confidence"], abs=1e-5)

    def test_predict_large_file_fails_413(self, client: TestClient, doctor_token: str):
        # 11 MB payload
        large_bytes = b"0" * (11 * 1024 * 1024)
        response = client.post(
            "/api/v1/predict",
            headers={"Authorization": f"Bearer {doctor_token}"},
            data={"age": "40"},
            files={"file": ("huge.jpg", large_bytes, "image/jpeg")},
        )
        assert response.status_code == 413
        assert "too large" in response.json()["detail"].lower()

    def test_predict_empty_file_fails_400(self, client: TestClient, doctor_token: str):
        response = client.post(
            "/api/v1/predict",
            headers={"Authorization": f"Bearer {doctor_token}"},
            data={"age": "40"},
            files={"file": ("empty.jpg", b"", "image/jpeg")},
        )
        assert response.status_code == 400
        assert "empty" in response.json()["detail"].lower()

    def test_predict_suspended_doctor_fails_403(self, client: TestClient, db_session, sample_image_bytes):
        suspended_id = uuid.uuid4().hex[:8]
        user = User(
            email=f"susp_doc_{suspended_id}@medassist.dz",
            password_hash="$2b$12$dummyhash",
            role=UserRole.DOCTOR,
            status=UserStatus.SUSPENDED,
        )
        db_session.add(user)
        db_session.commit()

        token = create_access_token(user_id=user.id, role="doctor")
        response = client.post(
            "/api/v1/predict",
            headers={"Authorization": f"Bearer {token}"},
            data={"age": "35"},
            files={"file": ("lesion.jpg", sample_image_bytes, "image/jpeg")},
        )
        assert response.status_code == 403
        assert "suspended" in response.json()["detail"].lower()

