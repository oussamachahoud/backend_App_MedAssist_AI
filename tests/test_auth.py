"""
tests/test_auth.py
Comprehensive test suite for Phase 2 Authentication System:
- Password hashing & verification (Bcrypt)
- JWT token generation, claims validation & expiration
- Auth API endpoints: register, login, refresh, logout, change-password, me
- Role-based and status-based authorization dependencies
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import jwt
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.deps import (
    get_current_active_doctor,
    get_current_specialist,
    get_current_user,
    require_admin,
)
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.security import (
    create_access_token,
    create_qr_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.db_models.audit import AuditLog
from app.db_models.user import DoctorProfile, DoctorType, RefreshToken, User, UserRole, UserStatus
from app.main import app

settings = get_settings()


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def db_session():
    """Yield a database session for test inspections and cleanups."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="module")
def client():
    """
    TestClient with mocked ML loading and storage check for fast startup.
    """
    with patch("app.services.model_service.model_service.load"), \
         patch("app.services.storage_service.storage_service.ensure_bucket_exists"):
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c


# ── 1. Security Unit Tests ───────────────────────────────────────────────────

class TestSecurityCore:
    """Unit tests for Bcrypt hashing and JWT token operations."""

    def test_password_hashing(self):
        password = "SecurePassword2026!"
        hashed = hash_password(password)

        assert hashed != password
        assert hashed.startswith("$2b$") or hashed.startswith("$2a$")
        assert verify_password(password, hashed) is True
        assert verify_password("WrongPassword!", hashed) is False

    def test_access_token_creation_and_decoding(self):
        user_id = uuid.uuid4()
        role = "doctor"
        token = create_access_token(user_id=user_id, role=role)

        payload = decode_token(token)
        assert payload["sub"] == str(user_id)
        assert payload["role"] == role
        assert payload["type"] == "access"
        assert "exp" in payload
        assert "iat" in payload

    def test_refresh_token_creation_and_hash(self):
        user_id = uuid.uuid4()
        raw_token, token_hash = create_refresh_token(user_id=user_id)

        assert isinstance(raw_token, str)
        assert len(token_hash) == 64  # SHA-256 hex digest length
        assert hash_refresh_token(raw_token) == token_hash

        payload = decode_token(raw_token)
        assert payload["sub"] == str(user_id)
        assert payload["type"] == "refresh"
        assert "jti" in payload

    def test_qr_token_creation(self):
        analysis_id = uuid.uuid4()
        token = create_qr_token(analysis_id=analysis_id)

        payload = decode_token(token)
        assert payload["sub"] == str(analysis_id)
        assert payload["type"] == "qr_access"

    def test_decode_token_invalid_signature(self):
        tampered_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIn0.invalid_signature"
        with pytest.raises(HTTPException) as exc_info:
            decode_token(tampered_token)
        assert exc_info.value.status_code == 401

    def test_decode_token_expired(self):
        expired_payload = {
            "sub": str(uuid.uuid4()),
            "type": "access",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        }
        expired_token = jwt.encode(
            expired_payload,
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
        )
        with pytest.raises(HTTPException) as exc_info:
            decode_token(expired_token)
        assert exc_info.value.status_code == 401
        assert "expired" in exc_info.value.detail.lower()


# ── 2. Auth Endpoints Integration Tests ───────────────────────────────────────

class TestAuthEndpoints:
    """Integration tests for all 6 authentication endpoints."""

    def test_register_doctor_gp_success(self, client: TestClient, db_session):
        unique_id = uuid.uuid4().hex[:8]
        email = f"dr_gp_{unique_id}@medassist.dz"
        license_num = f"ORD-GP-{unique_id}"

        payload = {
            "email": email,
            "password": "Password123!",
            "full_name": f"Dr. GP {unique_id}",
            "doctor_type": "general_practitioner",
            "specialization": "General Medicine",
            "license_number": license_num,
            "institution_name": "CHU Mustapha Bacha",
            "phone": "+213555000111",
            "wilaya": "16",
        }

        response = client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 201
        data = response.json()

        assert data["email"] == email
        assert data["role"] == "doctor"
        assert data["status"] == "pending_verification"
        assert data["must_change_password"] is False
        assert "password_hash" not in data

        profile = data["profile"]
        assert profile is not None
        assert profile["full_name"] == payload["full_name"]
        assert profile["doctor_type"] == "general_practitioner"
        assert profile["license_number"] == license_num
        assert profile["wilaya"] == "16"

        # Verify Audit Log created
        audit = (
            db_session.query(AuditLog)
            .filter(AuditLog.user_id == uuid.UUID(data["id"]))
            .filter(AuditLog.action == "DOCTOR_REGISTERED")
            .first()
        )
        assert audit is not None
        assert audit.details["doctor_type"] == "general_practitioner"

    def test_register_doctor_specialist_success(self, client: TestClient):
        unique_id = uuid.uuid4().hex[:8]
        email = f"dr_spec_{unique_id}@medassist.dz"

        payload = {
            "email": email,
            "password": "Password123!",
            "full_name": f"Dr. Specialist {unique_id}",
            "doctor_type": "specialist_dermatologist",
            "specialization": "Dermatology & Venereology",
            "license_number": f"ORD-SPEC-{unique_id}",
            "wilaya": "31",
        }

        response = client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["profile"]["doctor_type"] == "specialist_dermatologist"

    def test_register_duplicate_email_fails(self, client: TestClient):
        unique_id = uuid.uuid4().hex[:8]
        email = f"dup_{unique_id}@medassist.dz"

        payload = {
            "email": email,
            "password": "Password123!",
            "full_name": "Dr. Original",
        }
        res1 = client.post("/api/v1/auth/register", json=payload)
        assert res1.status_code == 201

        # Second registration with identical email
        res2 = client.post("/api/v1/auth/register", json=payload)
        assert res2.status_code == 400
        assert "already registered" in res2.json()["detail"].lower()

    def test_register_duplicate_license_fails(self, client: TestClient):
        unique_id = uuid.uuid4().hex[:8]
        license_num = f"LIC-UNIQUE-{unique_id}"

        p1 = {
            "email": f"doc1_{unique_id}@medassist.dz",
            "password": "Password123!",
            "full_name": "Dr. One",
            "license_number": license_num,
        }
        p2 = {
            "email": f"doc2_{unique_id}@medassist.dz",
            "password": "Password123!",
            "full_name": "Dr. Two",
            "license_number": license_num,
        }
        res1 = client.post("/api/v1/auth/register", json=p1)
        assert res1.status_code == 201

        res2 = client.post("/api/v1/auth/register", json=p2)
        assert res2.status_code == 400
        assert "license number" in res2.json()["detail"].lower()

    def test_register_short_password_fails(self, client: TestClient):
        payload = {
            "email": "short_pwd@medassist.dz",
            "password": "short",
            "full_name": "Dr. Short",
        }
        response = client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 422

    def test_login_success(self, client: TestClient, db_session):
        unique_id = uuid.uuid4().hex[:8]
        email = f"login_user_{unique_id}@medassist.dz"
        password = "ValidPassword2026!"

        # Register
        reg_res = client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": password, "full_name": "Dr. Login"},
        )
        assert reg_res.status_code == 201

        # Login
        login_res = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        assert login_res.status_code == 200
        body = login_res.json()

        assert "access_token" in body
        assert "refresh_token" in body
        assert body["token_type"] == "bearer"
        assert body["expires_in"] == settings.access_token_expire_minutes * 60
        assert body["must_change_password"] is False
        assert body["user"]["email"] == email

        # Verify refresh token in DB
        rf_hash = hash_refresh_token(body["refresh_token"])
        rf_record = (
            db_session.query(RefreshToken)
            .filter(RefreshToken.token_hash == rf_hash)
            .first()
        )
        assert rf_record is not None
        assert rf_record.is_revoked is False

        # Verify Audit Log
        audit = (
            db_session.query(AuditLog)
            .filter(AuditLog.user_id == uuid.UUID(body["user"]["id"]))
            .filter(AuditLog.action == "LOGIN_SUCCESS")
            .first()
        )
        assert audit is not None

    def test_login_invalid_password(self, client: TestClient, db_session):
        unique_id = uuid.uuid4().hex[:8]
        email = f"wrong_pwd_{unique_id}@medassist.dz"
        password = "ValidPassword2026!"

        client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": password, "full_name": "Dr. WrongPwd"},
        )

        response = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "BadPassword123!"},
        )
        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower()

        # Audit log for failed attempt
        audit = (
            db_session.query(AuditLog)
            .filter(AuditLog.action == "LOGIN_FAILED")
            .filter(AuditLog.details["email"].astext == email)
            .first()
        )
        assert audit is not None

    def test_login_nonexistent_email(self, client: TestClient):
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "nonexistent@medassist.dz", "password": "AnyPassword!"},
        )
        assert response.status_code == 401

    def test_login_suspended_account(self, client: TestClient, db_session):
        unique_id = uuid.uuid4().hex[:8]
        email = f"suspended_{unique_id}@medassist.dz"
        password = "Password2026!"

        reg_res = client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": password, "full_name": "Dr. Suspended"},
        )
        user_id = uuid.UUID(reg_res.json()["id"])

        # Manually suspend user in DB
        user = db_session.query(User).filter(User.id == user_id).first()
        user.status = UserStatus.SUSPENDED
        db_session.commit()

        # Attempt login
        login_res = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        assert login_res.status_code == 403
        assert "suspended" in login_res.json()["detail"].lower()

    def test_get_me_authenticated(self, client: TestClient):
        unique_id = uuid.uuid4().hex[:8]
        email = f"me_user_{unique_id}@medassist.dz"
        password = "Password2026!"

        client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": password, "full_name": "Dr. Me"},
        )
        login_res = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        token = login_res.json()["access_token"]

        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == email
        assert data["profile"]["full_name"] == "Dr. Me"

    def test_get_me_unauthenticated(self, client: TestClient):
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 401

    def test_token_refresh_flow(self, client: TestClient):
        unique_id = uuid.uuid4().hex[:8]
        email = f"refresh_{unique_id}@medassist.dz"
        password = "Password2026!"

        client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": password, "full_name": "Dr. Refresher"},
        )
        login_res = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        refresh_token = login_res.json()["refresh_token"]

        # Call refresh endpoint
        ref_res = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert ref_res.status_code == 200
        ref_data = ref_res.json()
        assert "access_token" in ref_data
        assert ref_data["token_type"] == "bearer"

        # Verify new access token works on /me
        me_res = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {ref_data['access_token']}"},
        )
        assert me_res.status_code == 200
        assert me_res.json()["email"] == email

    def test_token_refresh_with_access_token_fails(self, client: TestClient):
        unique_id = uuid.uuid4().hex[:8]
        email = f"ref_fail_{unique_id}@medassist.dz"
        password = "Password2026!"

        client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": password, "full_name": "Dr. RefFail"},
        )
        login_res = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        access_token = login_res.json()["access_token"]

        # Using access token instead of refresh token
        res = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": access_token},
        )
        assert res.status_code == 401
        assert "invalid token type" in res.json()["detail"].lower()

    def test_logout_revokes_refresh_token(self, client: TestClient, db_session):
        unique_id = uuid.uuid4().hex[:8]
        email = f"logout_{unique_id}@medassist.dz"
        password = "Password2026!"

        client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": password, "full_name": "Dr. Logout"},
        )
        login_res = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        refresh_token = login_res.json()["refresh_token"]

        # Logout
        logout_res = client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": refresh_token},
        )
        assert logout_res.status_code == 200
        assert "logged out" in logout_res.json()["message"].lower()

        # Verify is_revoked in DB
        rf_hash = hash_refresh_token(refresh_token)
        rf_db = db_session.query(RefreshToken).filter(RefreshToken.token_hash == rf_hash).first()
        assert rf_db.is_revoked is True

        # Subsequent refresh using this revoked token must fail
        subsequent_res = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert subsequent_res.status_code == 401
        assert "revoked" in subsequent_res.json()["detail"].lower()

    def test_change_password_flow(self, client: TestClient, db_session):
        unique_id = uuid.uuid4().hex[:8]
        email = f"chg_pwd_{unique_id}@medassist.dz"
        old_password = "OldPassword2026!"
        new_password = "NewPassword2026!"

        # Register and login
        client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": old_password, "full_name": "Dr. ChangePwd"},
        )
        login_res = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": old_password},
        )
        token = login_res.json()["access_token"]
        refresh_token = login_res.json()["refresh_token"]

        # 1. Wrong current password fails
        bad_req = client.put(
            "/api/v1/auth/change-password",
            headers={"Authorization": f"Bearer {token}"},
            json={"current_password": "WrongPassword!", "new_password": new_password},
        )
        assert bad_req.status_code == 400
        assert "current password is incorrect" in bad_req.json()["detail"].lower()

        # 2. Same new password fails
        same_req = client.put(
            "/api/v1/auth/change-password",
            headers={"Authorization": f"Bearer {token}"},
            json={"current_password": old_password, "new_password": old_password},
        )
        assert same_req.status_code == 400
        assert "cannot be the same" in same_req.json()["detail"].lower()

        # 3. Successful change password
        ok_req = client.put(
            "/api/v1/auth/change-password",
            headers={"Authorization": f"Bearer {token}"},
            json={"current_password": old_password, "new_password": new_password},
        )
        assert ok_req.status_code == 200

        # Old password can no longer login
        fail_login = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": old_password},
        )
        assert fail_login.status_code == 401

        # New password logs in successfully
        ok_login = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": new_password},
        )
        assert ok_login.status_code == 200

        # Previous refresh token was revoked
        rf_hash = hash_refresh_token(refresh_token)
        rf_db = db_session.query(RefreshToken).filter(RefreshToken.token_hash == rf_hash).first()
        assert rf_db.is_revoked is True


# ── 3. Authorization Dependency Tests ─────────────────────────────────────────

class TestAuthDependencies:
    """Unit and mock tests for RBAC dependency functions."""

    def test_get_current_active_doctor(self):
        # 1. Active Doctor passes
        active_doctor = User(
            id=uuid.uuid4(),
            email="doc@test.dz",
            role=UserRole.DOCTOR,
            status=UserStatus.ACTIVE,
        )
        assert get_current_active_doctor(active_doctor) == active_doctor

        # 2. Pending Doctor raises 403
        pending_doctor = User(
            id=uuid.uuid4(),
            email="pending@test.dz",
            role=UserRole.DOCTOR,
            status=UserStatus.PENDING_VERIFICATION,
        )
        with pytest.raises(HTTPException) as exc:
            get_current_active_doctor(pending_doctor)
        assert exc.value.status_code == 403
        assert "pending verification" in exc.value.detail.lower()

        # 3. Suspended Doctor raises 403
        suspended_doctor = User(
            id=uuid.uuid4(),
            email="suspended@test.dz",
            role=UserRole.DOCTOR,
            status=UserStatus.SUSPENDED,
        )
        with pytest.raises(HTTPException) as exc:
            get_current_active_doctor(suspended_doctor)
        assert exc.value.status_code == 403
        assert "suspended" in exc.value.detail.lower()

        # 4. Admin user attempting doctor-only dependency raises 403
        admin_user = User(
            id=uuid.uuid4(),
            email="admin@test.dz",
            role=UserRole.ADMIN,
            status=UserStatus.ACTIVE,
        )
        with pytest.raises(HTTPException) as exc:
            get_current_active_doctor(admin_user)
        assert exc.value.status_code == 403
        assert "doctor access required" in exc.value.detail.lower()

    def test_get_current_specialist(self):
        # 1. Specialist Dermatologist passes
        specialist = User(
            id=uuid.uuid4(),
            email="spec@test.dz",
            role=UserRole.DOCTOR,
            status=UserStatus.ACTIVE,
        )
        specialist.profile = DoctorProfile(
            user_id=specialist.id,
            full_name="Dr. Specialist",
            doctor_type=DoctorType.SPECIALIST_DERMATOLOGIST,
        )
        assert get_current_specialist(specialist) == specialist

        # 2. General Practitioner raises 403
        gp = User(
            id=uuid.uuid4(),
            email="gp@test.dz",
            role=UserRole.DOCTOR,
            status=UserStatus.ACTIVE,
        )
        gp.profile = DoctorProfile(
            user_id=gp.id,
            full_name="Dr. GP",
            doctor_type=DoctorType.GENERAL_PRACTITIONER,
        )
        with pytest.raises(HTTPException) as exc:
            get_current_specialist(gp)
        assert exc.value.status_code == 403
        assert "specialist" in exc.value.detail.lower()

    def test_require_admin(self):
        # 1. Active Admin passes
        admin = User(
            id=uuid.uuid4(),
            email="admin@test.dz",
            role=UserRole.ADMIN,
            status=UserStatus.ACTIVE,
        )
        assert require_admin(admin) == admin

        # 2. Doctor user raises 403
        doctor = User(
            id=uuid.uuid4(),
            email="doc@test.dz",
            role=UserRole.DOCTOR,
            status=UserStatus.ACTIVE,
        )
        with pytest.raises(HTTPException) as exc:
            require_admin(doctor)
        assert exc.value.status_code == 403
        assert "admin" in exc.value.detail.lower()

