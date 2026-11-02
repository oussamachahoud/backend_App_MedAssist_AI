"""
tests/test_phase4_endpoints.py
Comprehensive integration test suite for Phase 4 Telemedicine Endpoints:
- Analyses CRUD, Clinical Feedback, and PDF Export
- Pseudonymous Patients and Lesion Timelines
- Telemedicine Referrals (GP to Specialist workflow)
- Doctor Profile management and Clinical Statistics
- Public Doctors Directory and Patient QR Follow-up
- System Administration (Verification, Suspension, Password Reset, Stats)
"""

import uuid
from datetime import date, datetime, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.security import create_access_token, create_qr_token, hash_password
from app.db_models.analysis import AnalysisRecord
from app.db_models.patient import Patient, PatientSex
from app.db_models.referral import Referral, ReferralStatus
from app.db_models.user import DoctorProfile, DoctorType, User, UserRole, UserStatus
from app.main import app

settings = get_settings()


# ── Shared Fixtures ───────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def db_session():
    """Database session for test data setup and verification."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="module")
def client():
    """Fast TestClient with mocked background startup tasks."""
    with patch("app.services.model_service.model_service.load"), \
         patch("app.services.storage_service.storage_service.ensure_bucket_exists"):
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c


@pytest.fixture(scope="module")
def gp_doctor(db_session) -> tuple[User, str]:
    """Create an active General Practitioner and generate access token."""
    uid = uuid.uuid4().hex[:8]
    user = User(
        email=f"gp_{uid}@clinic.dz",
        password_hash=hash_password("GpSecret2026!"),
        role=UserRole.DOCTOR,
        status=UserStatus.ACTIVE,
    )
    db_session.add(user)
    db_session.flush()

    profile = DoctorProfile(
        user_id=user.id,
        full_name=f"Dr. GP {uid}",
        doctor_type=DoctorType.GENERAL_PRACTITIONER,
        institution_name="Polyclinique El Biar",
        wilaya="16",
    )
    db_session.add(profile)
    db_session.commit()
    db_session.refresh(user)

    token = create_access_token(user.id, role=user.role.value)
    return user, token


@pytest.fixture(scope="module")
def specialist_doctor(db_session) -> tuple[User, str]:
    """Create an active Specialist Dermatologist and generate access token."""
    uid = uuid.uuid4().hex[:8]
    user = User(
        email=f"specialist_{uid}@derma.dz",
        password_hash=hash_password("SpecSecret2026!"),
        role=UserRole.DOCTOR,
        status=UserStatus.ACTIVE,
    )
    db_session.add(user)
    db_session.flush()

    profile = DoctorProfile(
        user_id=user.id,
        full_name=f"Dr. Specialist {uid}",
        doctor_type=DoctorType.SPECIALIST_DERMATOLOGIST,
        institution_name="CHU Mustapha Bacha",
        wilaya="16",
    )
    db_session.add(profile)
    db_session.commit()
    db_session.refresh(user)

    token = create_access_token(user.id, role=user.role.value)
    return user, token


@pytest.fixture(scope="module")
def admin_user(db_session) -> tuple[User, str]:
    """Create an active Administrator and generate access token."""
    uid = uuid.uuid4().hex[:8]
    user = User(
        email=f"admin_{uid}@medassist.dz",
        password_hash=hash_password("AdminSecret2026!"),
        role=UserRole.ADMIN,
        status=UserStatus.ACTIVE,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    token = create_access_token(user.id, role=user.role.value)
    return user, token


# ── 1. Analyses Tests ─────────────────────────────────────────────────────────

class TestAnalysesEndpoints:
    """Tests for listing, inspecting, updating feedback, exporting PDF, and deleting analyses."""

    def test_list_analyses_pagination_and_filtering(self, client: TestClient, gp_doctor, db_session):
        user, token = gp_doctor

        # Seed two analysis records
        a1 = AnalysisRecord(
            doctor_id=user.id,
            image_storage_key="analyses/img1.jpg",
            predicted_class="MEL",
            confidence=0.91,
            all_probabilities={"MEL": 0.91, "NEV": 0.09},
            risk_level="CRITICAL",
            risk_escalated=True,
            inference_time_ms=120.0,
            model_version="V6.0",
        )
        a2 = AnalysisRecord(
            doctor_id=user.id,
            image_storage_key="analyses/img2.jpg",
            predicted_class="NEV",
            confidence=0.95,
            all_probabilities={"MEL": 0.05, "NEV": 0.95},
            risk_level="LOW",
            risk_escalated=False,
            inference_time_ms=110.0,
            model_version="V6.0",
        )
        db_session.add_all([a1, a2])
        db_session.commit()

        # List all for this GP
        resp = client.get("/api/v1/analyses", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 2
        assert len(data["items"]) >= 2

        # Filter by risk_level=CRITICAL
        resp_filtered = client.get(
            "/api/v1/analyses?risk_level=CRITICAL",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp_filtered.status_code == 200
        f_data = resp_filtered.json()
        for item in f_data["items"]:
            assert item["risk_level"] == "CRITICAL"

    def test_get_single_analysis_and_forbidden_access(
        self, client: TestClient, gp_doctor, specialist_doctor, db_session
    ):
        gp_user, gp_token = gp_doctor
        spec_user, spec_token = specialist_doctor

        analysis = AnalysisRecord(
            doctor_id=gp_user.id,
            image_storage_key="analyses/private.jpg",
            predicted_class="BCC",
            confidence=0.88,
            all_probabilities={"BCC": 0.88, "ACK": 0.12},
            risk_level="HIGH",
            risk_escalated=False,
            inference_time_ms=115.0,
            model_version="V6.0",
        )
        db_session.add(analysis)
        db_session.commit()

        # GP can view their own analysis
        resp = client.get(f"/api/v1/analyses/{analysis.id}", headers={"Authorization": f"Bearer {gp_token}"})
        assert resp.status_code == 200
        assert resp.json()["id"] == str(analysis.id)

        # Specialist without referral cannot view this analysis
        resp_forbidden = client.get(
            f"/api/v1/analyses/{analysis.id}",
            headers={"Authorization": f"Bearer {spec_token}"},
        )
        assert resp_forbidden.status_code == 403

    def test_update_analysis_feedback_success(self, client: TestClient, gp_doctor, db_session):
        gp_user, gp_token = gp_doctor

        analysis = AnalysisRecord(
            doctor_id=gp_user.id,
            image_storage_key="analyses/feedback_test.jpg",
            predicted_class="SEK",
            confidence=0.85,
            all_probabilities={"SEK": 0.85, "NEV": 0.15},
            risk_level="LOW",
            inference_time_ms=105.0,
            model_version="V6.0",
        )
        db_session.add(analysis)
        db_session.commit()

        payload = {
            "doctor_confirmed": True,
            "doctor_diagnosis": "Confirmed Seborrheic Keratosis",
            "biopsy_performed": False,
            "next_followup_date": "2027-01-15",
        }
        resp = client.put(
            f"/api/v1/analyses/{analysis.id}/feedback",
            headers={"Authorization": f"Bearer {gp_token}"},
            json=payload,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["doctor_confirmed"] is True
        assert data["doctor_diagnosis"] == "Confirmed Seborrheic Keratosis"
        assert data["biopsy_performed"] is False
        assert data["next_followup_date"] == "2027-01-15"

    def test_export_analysis_pdf_returns_valid_pdf_stream(
        self, client: TestClient, gp_doctor, db_session
    ):
        gp_user, gp_token = gp_doctor

        analysis = AnalysisRecord(
            doctor_id=gp_user.id,
            image_storage_key="analyses/pdf_test.jpg",
            predicted_class="MEL",
            confidence=0.96,
            all_probabilities={"MEL": 0.96, "NEV": 0.04},
            risk_level="CRITICAL",
            risk_escalated=True,
            inference_time_ms=140.0,
            model_version="V6.0",
        )
        db_session.add(analysis)
        db_session.commit()

        resp = client.post(
            f"/api/v1/analyses/{analysis.id}/export-pdf",
            headers={"Authorization": f"Bearer {gp_token}"},
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert resp.content.startswith(b"%PDF")
        assert len(resp.content) > 1000

    def test_delete_analysis_success(self, client: TestClient, gp_doctor, db_session):
        gp_user, gp_token = gp_doctor

        analysis = AnalysisRecord(
            doctor_id=gp_user.id,
            image_storage_key="analyses/to_delete.jpg",
            predicted_class="NEV",
            confidence=0.99,
            all_probabilities={"NEV": 0.99},
            risk_level="LOW",
            inference_time_ms=90.0,
            model_version="V6.0",
        )
        db_session.add(analysis)
        db_session.commit()

        resp = client.delete(
            f"/api/v1/analyses/{analysis.id}",
            headers={"Authorization": f"Bearer {gp_token}"},
        )
        assert resp.status_code == 200

        # Confirm deleted
        check = db_session.query(AnalysisRecord).filter(AnalysisRecord.id == analysis.id).first()
        assert check is None


# ── 2. Patients Tests ─────────────────────────────────────────────────────────

class TestPatientsEndpoints:
    """Tests for creating, listing, timeline inspection, updating, and soft-deleting patients."""

    def test_create_patient_and_duplicate_fails(self, client: TestClient, gp_doctor):
        _, token = gp_doctor
        code = f"DZ-P-{uuid.uuid4().hex[:6].upper()}"

        payload = {
            "patient_code": code,
            "birth_year": 1985,
            "sex": "female",
            "notes": "Follow-up for dysplastic nevus on back",
        }
        resp = client.post(
            "/api/v1/patients",
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["patient_code"] == code
        assert data["birth_year"] == 1985
        assert data["sex"] == "female"

        # Duplicate patient_code must fail with 400
        resp_dup = client.post(
            "/api/v1/patients",
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
        )
        assert resp_dup.status_code == 400
        assert "already exists" in resp_dup.json()["detail"].lower()

    def test_list_and_search_patients(self, client: TestClient, gp_doctor):
        _, token = gp_doctor
        resp = client.get("/api/v1/patients", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert "items" in resp.json()
        assert resp.json()["total"] >= 1

    def test_patient_detail_with_timeline(self, client: TestClient, gp_doctor, db_session):
        gp_user, token = gp_doctor

        # Create patient
        p = Patient(
            created_by_doctor_id=gp_user.id,
            patient_code=f"TL-{uuid.uuid4().hex[:6].upper()}",
            birth_year=1978,
            sex=PatientSex.MALE,
        )
        db_session.add(p)
        db_session.commit()

        # Add 2 analyses for this patient
        a1 = AnalysisRecord(
            doctor_id=gp_user.id,
            patient_id=p.id,
            lesion_tag="Right Forearm",
            image_storage_key="analyses/tl1.jpg",
            predicted_class="NEV",
            confidence=0.92,
            all_probabilities={"NEV": 0.92, "MEL": 0.08},
            risk_level="LOW",
            inference_time_ms=100.0,
            model_version="V6.0",
        )
        a2 = AnalysisRecord(
            doctor_id=gp_user.id,
            patient_id=p.id,
            lesion_tag="Right Forearm Followup",
            image_storage_key="analyses/tl2.jpg",
            predicted_class="ACK",
            confidence=0.87,
            all_probabilities={"ACK": 0.87, "NEV": 0.13},
            risk_level="MODERATE",
            inference_time_ms=105.0,
            model_version="V6.0",
        )
        db_session.add_all([a1, a2])
        db_session.commit()

        resp = client.get(f"/api/v1/patients/{p.id}", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == str(p.id)
        assert len(data["timeline"]) == 2
        assert data["timeline"][0]["lesion_tag"] in ["Right Forearm", "Right Forearm Followup"]

    def test_update_and_soft_delete_patient(self, client: TestClient, gp_doctor, db_session):
        gp_user, token = gp_doctor

        p = Patient(
            created_by_doctor_id=gp_user.id,
            patient_code=f"DEL-{uuid.uuid4().hex[:6].upper()}",
            birth_year=1990,
            sex=PatientSex.FEMALE,
        )
        db_session.add(p)
        db_session.commit()

        # Update
        update_resp = client.put(
            f"/api/v1/patients/{p.id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"birth_year": 1991, "notes": "Corrected birth year"},
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["birth_year"] == 1991

        # Delete (soft delete)
        del_resp = client.delete(
            f"/api/v1/patients/{p.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert del_resp.status_code == 200

        # Now get must return 404
        get_resp = client.get(f"/api/v1/patients/{p.id}", headers={"Authorization": f"Bearer {token}"})
        assert get_resp.status_code == 404

        # Check in DB that deleted_at is set
        db_session.expire_all()
        db_record = db_session.query(Patient).filter(Patient.id == p.id).first()
        assert db_record.deleted_at is not None


# ── 3. Referrals Tests ───────────────────────────────────────────────────────

class TestReferralsEndpoints:
    """Tests for the complete GP-to-Specialist telemedicine referral workflow."""

    def test_referral_full_lifecycle(
        self, client: TestClient, gp_doctor, specialist_doctor, db_session
    ):
        gp_user, gp_token = gp_doctor
        spec_user, spec_token = specialist_doctor

        # 1. Create analysis by GP
        analysis = AnalysisRecord(
            doctor_id=gp_user.id,
            image_storage_key="analyses/referral_case.jpg",
            predicted_class="MEL",
            confidence=0.89,
            all_probabilities={"MEL": 0.89, "BCC": 0.11},
            risk_level="CRITICAL",
            risk_escalated=True,
            inference_time_ms=125.0,
            model_version="V6.0",
        )
        db_session.add(analysis)
        db_session.commit()

        # 2. GP creates referral designated to specialist
        ref_payload = {
            "analysis_id": str(analysis.id),
            "specialist_id": str(spec_user.id),
            "referral_note": "Suspicious pigmented lesion with irregular borders. Requesting specialist review.",
        }
        create_resp = client.post(
            "/api/v1/referrals",
            headers={"Authorization": f"Bearer {gp_token}"},
            json=ref_payload,
        )
        assert create_resp.status_code == 201
        ref_data = create_resp.json()
        assert ref_data["status"] == "pending"
        assert ref_data["analysis_id"] == str(analysis.id)
        referral_id = ref_data["id"]

        # Duplicate referral for same analysis must fail
        dup_resp = client.post(
            "/api/v1/referrals",
            headers={"Authorization": f"Bearer {gp_token}"},
            json=ref_payload,
        )
        assert dup_resp.status_code == 400

        # 3. GP checks sent referrals
        sent_resp = client.get(
            "/api/v1/referrals/sent",
            headers={"Authorization": f"Bearer {gp_token}"},
        )
        assert sent_resp.status_code == 200
        assert any(r["id"] == referral_id for r in sent_resp.json()["items"])

        # 4. Specialist checks received referrals
        recv_resp = client.get(
            "/api/v1/referrals/received",
            headers={"Authorization": f"Bearer {spec_token}"},
        )
        assert recv_resp.status_code == 200
        assert any(r["id"] == referral_id for r in recv_resp.json()["items"])

        # 5. Specialist can view the referral and the referred analysis
        detail_resp = client.get(
            f"/api/v1/referrals/{referral_id}",
            headers={"Authorization": f"Bearer {spec_token}"},
        )
        assert detail_resp.status_code == 200
        assert detail_resp.json()["analysis"]["id"] == str(analysis.id)

        # 6. Specialist responds to referral
        resp_payload = {
            "status": "completed",
            "specialist_response": "Agreed with high suspicion. Urgent surgical excision and biopsy recommended.",
        }
        respond_resp = client.put(
            f"/api/v1/referrals/{referral_id}/respond",
            headers={"Authorization": f"Bearer {spec_token}"},
            json=resp_payload,
        )
        assert respond_resp.status_code == 200
        completed_data = respond_resp.json()
        assert completed_data["status"] == "completed"
        assert completed_data["specialist_response"] == resp_payload["specialist_response"]
        assert completed_data["responded_at"] is not None

    def test_gp_cannot_respond_to_referral_403(
        self, client: TestClient, gp_doctor, db_session
    ):
        _, gp_token = gp_doctor
        dummy_id = uuid.uuid4()
        resp = client.put(
            f"/api/v1/referrals/{dummy_id}/respond",
            headers={"Authorization": f"Bearer {gp_token}"},
            json={"status": "completed", "specialist_response": "Test response"},
        )
        assert resp.status_code == 403


# ── 4. Profile & Statistics Tests ─────────────────────────────────────────────

class TestProfileAndStatsEndpoints:
    """Tests for viewing, updating doctor profiles, and computing metrics."""

    def test_get_and_update_profile(self, client: TestClient, gp_doctor):
        _, token = gp_doctor

        # Get profile
        resp = client.get("/api/v1/profile", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert "full_name" in data

        # Update profile
        update_payload = {
            "institution_name": "Cabinet Médical Central",
            "wilaya": "09",
            "phone": "0550123456",
        }
        up_resp = client.put(
            "/api/v1/profile",
            headers={"Authorization": f"Bearer {token}"},
            json=update_payload,
        )
        assert up_resp.status_code == 200
        assert up_resp.json()["institution_name"] == "Cabinet Médical Central"
        assert up_resp.json()["wilaya"] == "09"
        assert up_resp.json()["phone"] == "0550123456"

    def test_doctor_clinical_stats(self, client: TestClient, gp_doctor):
        _, token = gp_doctor
        resp = client.get("/api/v1/profile/stats", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        stats = resp.json()
        assert "total_analyses" in stats
        assert "diagnoses_distribution" in stats
        assert "risk_distribution" in stats
        assert "feedback_rate_percentage" in stats
        assert "sent_referrals_count" in stats


# ── 5. Public & Follow-up Tests ───────────────────────────────────────────────

class TestPublicEndpoints:
    """Tests for public doctor directory and patient QR token resolution."""

    def test_public_doctors_directory(self, client: TestClient, gp_doctor):
        resp = client.get("/api/v1/public/doctors")
        assert resp.status_code == 200
        doctors = resp.json()
        assert isinstance(doctors, list)
        assert len(doctors) >= 1

        # Check fields do not leak password or email
        first_doc = doctors[0]
        assert "id" in first_doc
        assert "full_name" in first_doc
        assert "doctor_type" in first_doc
        assert "password_hash" not in first_doc
        assert "email" not in first_doc

    def test_patient_qr_follow_up_success_and_invalid(
        self, client: TestClient, gp_doctor, db_session
    ):
        gp_user, _ = gp_doctor

        # Create analysis
        analysis = AnalysisRecord(
            doctor_id=gp_user.id,
            image_storage_key="analyses/qr_test.jpg",
            predicted_class="NEV",
            confidence=0.94,
            all_probabilities={"NEV": 0.94, "MEL": 0.06},
            risk_level="LOW",
            recommendations=["Routine self-check every 6 months."],
            inference_time_ms=102.0,
            model_version="V6.0",
        )
        db_session.add(analysis)
        db_session.commit()

        # Generate QR token
        qr_token = create_qr_token(analysis_id=analysis.id)

        # Public resolution
        resp = client.get(f"/api/v1/public/follow-up/{qr_token}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["analysis_id"] == str(analysis.id)
        assert data["predicted_class"] == "NEV"
        assert data["risk_level"] == "LOW"
        assert "Routine self-check" in data["recommendations"][0]

        # Corrupted token should fail with 401
        bad_resp = client.get("/api/v1/public/follow-up/invalid.token.here")
        assert bad_resp.status_code == 401


# ── 6. Admin Endpoints Tests ──────────────────────────────────────────────────

class TestAdminEndpoints:
    """Tests for admin oversight: listing, verification, suspension, password reset, and stats."""

    def test_admin_list_users(self, client: TestClient, admin_user):
        _, token = admin_user
        resp = client.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert len(data["items"]) >= 1

    def test_admin_verify_doctor_account(self, client: TestClient, admin_user, db_session):
        _, admin_token = admin_user

        # Create a pending doctor
        uid = uuid.uuid4().hex[:8]
        pending_doc = User(
            email=f"pending_{uid}@hospital.dz",
            password_hash=hash_password("Pass123!"),
            role=UserRole.DOCTOR,
            status=UserStatus.PENDING_VERIFICATION,
        )
        db_session.add(pending_doc)
        db_session.commit()

        # Verify
        resp = client.put(
            f"/api/v1/admin/users/{pending_doc.id}/verify",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"

        # Check DB
        db_session.refresh(pending_doc)
        assert pending_doc.status == UserStatus.ACTIVE

    def test_admin_suspend_user(self, client: TestClient, admin_user, db_session):
        _, admin_token = admin_user

        uid = uuid.uuid4().hex[:8]
        user_to_suspend = User(
            email=f"user_{uid}@medassist.dz",
            password_hash=hash_password("Pass123!"),
            role=UserRole.DOCTOR,
            status=UserStatus.ACTIVE,
        )
        db_session.add(user_to_suspend)
        db_session.commit()

        resp = client.put(
            f"/api/v1/admin/users/{user_to_suspend.id}/status",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"status": "suspended"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "suspended"

        db_session.refresh(user_to_suspend)
        assert user_to_suspend.status == UserStatus.SUSPENDED

    def test_admin_reset_user_password(self, client: TestClient, admin_user, db_session):
        _, admin_token = admin_user

        uid = uuid.uuid4().hex[:8]
        target_user = User(
            email=f"pwd_{uid}@medassist.dz",
            password_hash=hash_password("OldPass123!"),
            role=UserRole.DOCTOR,
            status=UserStatus.ACTIVE,
        )
        db_session.add(target_user)
        db_session.commit()

        resp = client.post(
            f"/api/v1/admin/users/{target_user.id}/reset-pwd",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "temporary_password" in data
        assert len(data["temporary_password"]) >= 10

        db_session.refresh(target_user)
        assert target_user.must_change_password is True

    def test_admin_system_stats(self, client: TestClient, admin_user):
        _, token = admin_user
        resp = client.get("/api/v1/admin/stats", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        stats = resp.json()
        assert stats["total_users"] >= 1
        assert stats["active_doctors"] >= 1
        assert "total_analyses" in stats
        assert "total_patients" in stats
        assert "total_referrals" in stats

    def test_regular_doctor_cannot_access_admin_endpoints_403(
        self, client: TestClient, gp_doctor
    ):
        _, gp_token = gp_doctor
        resp = client.get("/api/v1/admin/stats", headers={"Authorization": f"Bearer {gp_token}"})
        assert resp.status_code == 403

    def test_admin_analytics(self, client: TestClient, admin_user):
        _, token = admin_user
        resp = client.get("/api/v1/admin/analytics", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert "geographical_distribution" in data
        assert "diagnostic_class_distribution" in data
        assert "risk_distribution" in data
        assert "model_concordance_rate_percentage" in data
        assert "average_inference_time_ms" in data

    def test_admin_audit_logs(self, client: TestClient, admin_user):
        _, token = admin_user
        resp = client.get("/api/v1/admin/audit-logs", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
