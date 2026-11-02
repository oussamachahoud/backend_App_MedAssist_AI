"""
tests/test_platform_resources.py
Unit tests for platform resources configuration & governance endpoints:
- Public read access
- Admin write permissions & audit logging
- Validation & fallback defaults
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db_models.audit import AuditLog
from tests.test_phase4_endpoints import admin_user, client, db_session, gp_doctor


def test_public_get_platform_resources(client: TestClient):
    """Public unauthenticated endpoint can fetch platform resources."""
    resp = client.get("/api/v1/public/platform-resources")
    assert resp.status_code == 200
    data = resp.json()
    assert "video_walkthrough_url" in data
    assert "mobile_apk_url" in data
    assert "landing_page_url" in data


def test_doctor_cannot_update_platform_resources_403(client: TestClient, gp_doctor):
    """Regular doctor cannot modify platform resources."""
    _, token = gp_doctor
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"video_walkthrough_url": "https://malicious.example.com"}
    resp = client.put("/api/v1/admin/platform-resources", json=payload, headers=headers)
    assert resp.status_code == 403


def test_admin_update_platform_resources_and_audit(client: TestClient, admin_user, db_session: Session):
    """Admin can update platform resources and an audit log is registered."""
    _, token = admin_user
    headers = {"Authorization": f"Bearer {token}"}
    new_video = "https://youtube.com/shorts/custom-video-test"
    new_apk = "/dashboard/assets/downloads/custom-release.apk"

    resp = client.put(
        "/api/v1/admin/platform-resources",
        json={"video_walkthrough_url": new_video, "mobile_apk_url": new_apk},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["video_walkthrough_url"] == new_video
    assert data["mobile_apk_url"] == new_apk

    # Verify audit log in DB
    audit = db_session.query(AuditLog).filter(AuditLog.action == "PLATFORM_RESOURCES_UPDATED").order_by(AuditLog.created_at.desc()).first()
    assert audit is not None
    assert audit.resource_type == "system_settings"
    assert audit.details["video_url"] == new_video


def test_admin_upload_apk_success_and_audit(client: TestClient, admin_user, db_session: Session):
    """Admin can upload an APK file which is saved and audited."""
    _, token = admin_user
    headers = {"Authorization": f"Bearer {token}"}
    fake_apk_bytes = b"PK\x03\x04" + b"\x00" * 1024  # Fake zip/apk header

    files = {"file": ("MedAssist-Release-v2.apk", fake_apk_bytes, "application/vnd.android.package-archive")}
    resp = client.post("/api/v1/admin/platform-resources/upload-apk", files=files, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["mobile_apk_url"] == "/dashboard/assets/downloads/MedAssist-AI.apk"
    assert data["apk_original_name"] == "MedAssist-Release-v2.apk"
    assert "MB" in data["apk_file_size"]

    # Verify audit log in DB
    audit = db_session.query(AuditLog).filter(AuditLog.action == "APK_VERSION_UPLOADED").order_by(AuditLog.created_at.desc()).first()
    assert audit is not None
    assert audit.resource_type == "platform_resources"
    assert audit.details["filename"] == "MedAssist-Release-v2.apk"


def test_doctor_cannot_upload_apk_403(client: TestClient, gp_doctor):
    """Doctor cannot upload APK files."""
    _, token = gp_doctor
    headers = {"Authorization": f"Bearer {token}"}
    files = {"file": ("test.apk", b"PK123", "application/octet-stream")}
    resp = client.post("/api/v1/admin/platform-resources/upload-apk", files=files, headers=headers)
    assert resp.status_code == 403


def test_upload_apk_invalid_extension_400(client: TestClient, admin_user):
    """Uploading a non-apk file returns 400 Bad Request."""
    _, token = admin_user
    headers = {"Authorization": f"Bearer {token}"}
    files = {"file": ("malicious.exe", b"MZ...", "application/octet-stream")}
    resp = client.post("/api/v1/admin/platform-resources/upload-apk", files=files, headers=headers)
    assert resp.status_code == 400
    assert "Invalid file format" in resp.json()["detail"]


def test_admin_upload_thesis_en_and_fr_success(client: TestClient, admin_user, db_session: Session):
    """Admin can upload English and French Master thesis PDFs."""
    _, token = admin_user
    headers = {"Authorization": f"Bearer {token}"}
    fake_pdf = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n" + b"X" * 1024

    # Upload English thesis
    resp_en = client.post(
        "/api/v1/admin/platform-resources/upload-thesis?lang=en",
        files={"file": ("My_Master_Thesis_EN.pdf", fake_pdf, "application/pdf")},
        headers=headers,
    )
    assert resp_en.status_code == 200
    data_en = resp_en.json()
    assert data_en["thesis_en_url"] == "/dashboard/assets/docs/Thesis_Master_GLAA_EN.pdf"
    assert "MB" in data_en.get("thesis_en_size", "")

    # Upload French thesis
    resp_fr = client.post(
        "/api/v1/admin/platform-resources/upload-thesis?lang=fr",
        files={"file": ("Mon_Memoire_Master_FR.pdf", fake_pdf, "application/pdf")},
        headers=headers,
    )
    assert resp_fr.status_code == 200
    data_fr = resp_fr.json()
    assert data_fr["thesis_fr_url"] == "/dashboard/assets/docs/Thesis_Master_GLAA_FR.pdf"
    assert "MB" in data_fr.get("thesis_fr_size", "")

    # Verify audit log
    audit = db_session.query(AuditLog).filter(AuditLog.action == "THESIS_DOCUMENT_UPLOADED").order_by(AuditLog.created_at.desc()).first()
    assert audit is not None
    assert audit.resource_type == "platform_resources"
    assert audit.details["language"] == "fr"


def test_doctor_cannot_upload_thesis_403(client: TestClient, gp_doctor):
    """Doctor cannot upload thesis documents."""
    _, token = gp_doctor
    headers = {"Authorization": f"Bearer {token}"}
    files = {"file": ("thesis.pdf", b"%PDF-test", "application/pdf")}
    resp = client.post("/api/v1/admin/platform-resources/upload-thesis?lang=fr", files=files, headers=headers)
    assert resp.status_code == 403


def test_upload_thesis_invalid_extension_400(client: TestClient, admin_user):
    """Uploading non-PDF thesis returns 400."""
    _, token = admin_user
    headers = {"Authorization": f"Bearer {token}"}
    files = {"file": ("thesis.docx", b"DOCX...", "application/octet-stream")}
    resp = client.post("/api/v1/admin/platform-resources/upload-thesis?lang=en", files=files, headers=headers)
    assert resp.status_code == 400
    assert "Invalid file format" in resp.json()["detail"]


def test_admin_upload_qr_code_success(client: TestClient, admin_user, db_session: Session):
    """Admin can upload an SVG QR code which is saved to /dashboard/assets/images/qr-code.svg and audited."""
    _, token = admin_user
    headers = {"Authorization": f"Bearer {token}"}
    fake_svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200"><rect width="200" height="200" fill="#000"/></svg>'

    files = {"file": ("custom_qr.svg", fake_svg, "image/svg+xml")}
    resp = client.post("/api/v1/admin/platform-resources/upload-qr-code", files=files, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["qr_code_url"] == "/dashboard/assets/images/qr-code.svg"

    # Verify audit log in DB
    audit = db_session.query(AuditLog).filter(AuditLog.action == "QR_CODE_UPLOADED").order_by(AuditLog.created_at.desc()).first()
    assert audit is not None
    assert audit.resource_type == "platform_resources"
    assert audit.details["filename"] == "custom_qr.svg"


def test_doctor_cannot_upload_qr_code_403(client: TestClient, gp_doctor):
    """Regular doctor cannot upload QR codes."""
    _, token = gp_doctor
    headers = {"Authorization": f"Bearer {token}"}
    files = {"file": ("qr.svg", b"<svg></svg>", "image/svg+xml")}
    resp = client.post("/api/v1/admin/platform-resources/upload-qr-code", files=files, headers=headers)
    assert resp.status_code == 403


def test_upload_qr_code_invalid_extension_400(client: TestClient, admin_user):
    """Uploading non-SVG format returns 400."""
    _, token = admin_user
    headers = {"Authorization": f"Bearer {token}"}
    files = {"file": ("qr.png", b"FakePNGData", "image/png")}
    resp = client.post("/api/v1/admin/platform-resources/upload-qr-code", files=files, headers=headers)
    assert resp.status_code == 400
    assert "Invalid file format" in resp.json()["detail"]
