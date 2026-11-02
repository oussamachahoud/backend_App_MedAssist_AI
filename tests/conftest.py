"""
tests/conftest.py
Shared pytest fixtures and configuration.
"""

import pytest
from unittest.mock import MagicMock

@pytest.fixture(autouse=True)
def isolate_platform_resources(tmp_path, monkeypatch):
    """Ensure tests never mutate production platform_resources.json."""
    import shutil
    import os
    from app.services import platform_resources
    temp_json = tmp_path / "platform_resources.json"
    prod_path = platform_resources.RESOURCES_FILE_PATH
    if os.path.exists(prod_path):
        shutil.copy2(prod_path, str(temp_json))
    else:
        temp_json.write_text("{}", encoding="utf-8")
    monkeypatch.setattr("app.services.platform_resources.RESOURCES_FILE_PATH", str(temp_json))
    # Also isolate admin upload destination so tests never overwrite production PDFs/APKs
    monkeypatch.setattr("app.api.v1.endpoints.admin.PROJECT_ROOT", tmp_path)



@pytest.fixture(scope="session")
def mock_model_service():
    """
    Reusable mock ModelService for the entire test session.
    Override individual attributes per test class as needed.
    """
    svc = MagicMock()
    svc.is_loaded = True
    svc.diagnostic_classes = ["ACK", "BCC", "MEL", "NEV", "SEK", "SCC"]
    svc.region_classes = ["back", "face", "foot", "hand", "scalp", "unknown"]
    svc.device = "cpu"
    svc.encode_sex.return_value = 1.0
    svc.encode_region.return_value = 0.3
    svc.predict.return_value = (
        "NEV",
        0.93,
        {
            "ACK": 0.01,
            "BCC": 0.01,
            "MEL": 0.01,
            "NEV": 0.93,
            "SEK": 0.03,
            "SCC": 0.01,
        },
    )
    return svc


PROTECTED_DEMO_EMAILS = {
    "admin@medassist.dz",
    "dr.benali@chu-oran.dz",
    "doctor.amara@medassist.dz",
    "dr.mansouri@chu-alger.dz",
    "dr.khellaf@clinic-setif.dz",
    "dr.meziani.yasmine@chu-alger.dz",
    "dr.boukhalfa.tarek@epsp-bouira.dz",
    "dr.cherif.amina@chu-oran.dz",
    "dr.belkacemi.karim@eph-skikda.dz",
    "dr.haddad.nadia@chu-constantine.dz",
}


@pytest.fixture(autouse=True, scope="session")
def cleanup_test_db_artifacts():
    """
    Ensure any temporary user or record created during automated tests
    is cleaned up after the entire test session completes, protecting demo data.
    """
    yield
    try:
        from app.core.database import SessionLocal
        from app.db_models.user import User, DoctorProfile, RefreshToken
        from app.db_models.patient import Patient
        from app.db_models.analysis import AnalysisRecord
        from app.db_models.referral import Referral

        db = SessionLocal()
        test_users = db.query(User).filter(~User.email.in_(PROTECTED_DEMO_EMAILS)).all()
        test_ids = [u.id for u in test_users]
        if test_ids:
            db.query(Referral).filter(
                (Referral.referring_doctor_id.in_(test_ids)) | 
                (Referral.specialist_id.in_(test_ids))
            ).delete(synchronize_session=False)
            db.query(AnalysisRecord).filter(AnalysisRecord.doctor_id.in_(test_ids)).delete(synchronize_session=False)
            db.query(Patient).filter(Patient.created_by_doctor_id.in_(test_ids)).delete(synchronize_session=False)
            db.query(RefreshToken).filter(RefreshToken.user_id.in_(test_ids)).delete(synchronize_session=False)
            db.query(DoctorProfile).filter(DoctorProfile.user_id.in_(test_ids)).delete(synchronize_session=False)
            db.query(User).filter(User.id.in_(test_ids)).delete(synchronize_session=False)
            db.commit()
        db.close()
    except Exception:
        pass

