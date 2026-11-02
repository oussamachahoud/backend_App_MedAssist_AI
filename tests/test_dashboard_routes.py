"""
tests/test_dashboard_routes.py
Verification tests for Web Dashboard static assets and frontend routing.
"""

from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    with patch("app.services.model_service.model_service.load"), \
         patch("app.services.storage_service.storage_service.ensure_bucket_exists"):
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c


class TestDashboardRoutes:
    def test_dashboard_index_returns_200(self, client: TestClient):
        resp = client.get("/dashboard/")
        assert resp.status_code == 200
        assert "MedAssist AI" in resp.text

    def test_dashboard_login_page_loads(self, client: TestClient):
        resp = client.get("/dashboard/login.html")
        assert resp.status_code == 200
        assert "Sign In to Portal" in resp.text

    def test_dashboard_join_page_loads(self, client: TestClient):
        resp = client.get("/dashboard/join.html")
        assert resp.status_code == 200
        assert "Clinician Network Registration" in resp.text

    def test_dashboard_doctor_page_loads(self, client: TestClient):
        resp = client.get("/dashboard/doctor.html")
        assert resp.status_code == 200
        assert "Clinician Telemedicine Dashboard" in resp.text
        assert "Grad-CAM++" in resp.text

    def test_dashboard_admin_page_loads(self, client: TestClient):
        resp = client.get("/dashboard/admin.html")
        assert resp.status_code == 200
        assert "System Administration & Governance" in resp.text

    def test_dashboard_follow_up_page_loads(self, client: TestClient):
        resp = client.get("/dashboard/follow-up.html")
        assert resp.status_code == 200
        assert "Patient Medical Follow-Up" in resp.text

    def test_dashboard_css_asset(self, client: TestClient):
        resp = client.get("/dashboard/assets/css/dashboard.css")
        assert resp.status_code == 200
        assert "--navy-950" in resp.text

    def test_dashboard_js_api_asset(self, client: TestClient):
        resp = client.get("/dashboard/assets/js/api.js")
        assert resp.status_code == 200
        assert "ApiClient" in resp.text

    def test_dashboard_vendor_chart_asset(self, client: TestClient):
        resp = client.get("/dashboard/assets/vendor/chart.min.js")
        assert resp.status_code == 200
        assert len(resp.content) > 100000

    def test_dashboard_landing_page_loads(self, client: TestClient):
        resp = client.get("/dashboard/landing.html")
        assert resp.status_code == 200
        assert "Smarter Healthcare" in resp.text
        assert "Clinician Portal" in resp.text

    def test_root_endpoint_includes_dashboard(self, client: TestClient):
        resp = client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert "dashboard" in data

    def test_dashboard_thesis_and_video_assets_accessible(self, client: TestClient):
        resp_thesis = client.get("/dashboard/assets/docs/Thesis_Master_GLAA_EN.pdf")
        assert resp_thesis.status_code == 200
        assert len(resp_thesis.content) > 1000000  # > 1MB

        resp_video = client.get("/dashboard/assets/videos/demo-video.mp4")
        assert resp_video.status_code == 200
        assert len(resp_video.content) > 1000000  # > 1MB

