"""
tests/test_api.py
Integration tests for HTTP endpoints using FastAPI TestClient.
Uses a mock ModelService so no real .pth file is needed to run tests.
V6.0: predict endpoint accepts 7 clinical metadata fields.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

# ── Mock model service ────────────────────────────────────────────────────────

MOCK_CLASSES = ["ACK", "BCC", "MEL", "NEV", "SEK", "SCC"]

_mock_service = MagicMock()
_mock_service.is_loaded = True
_mock_service.diagnostic_classes = MOCK_CLASSES
_mock_service.region_classes = ["back", "face", "scalp"]
_mock_service.device = "cpu"
_mock_service.build_meta_vector.return_value = (
    __import__("numpy").zeros(7, dtype="float32"),
    __import__("numpy").ones(7, dtype="float32"),
)
_mock_service.predict.return_value = (
    "NEV",    # predicted label
    0.92,     # confidence
    {
        "ACK": 0.01, "BCC": 0.02, "MEL": 0.01,
        "NEV": 0.92, "SEK": 0.03, "SCC": 0.01,
    },
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    """
    TestClient with mocked ModelService.
    Bypasses the lifespan model loading so tests run without .pth files.
    """
    with patch("app.api.dependencies._model_service", _mock_service):
        with patch("app.api.endpoints.health.model_service", _mock_service):
            with patch("app.api.endpoints.model_info.model_service", _mock_service):
                with TestClient(app, raise_server_exceptions=True) as c:
                    yield c


@pytest.fixture
def sample_image(tmp_path):
    """Create a minimal 256×256 white JPEG image for testing."""
    from PIL import Image
    img_path = tmp_path / "test.jpg"
    img = Image.new("RGB", (256, 256), color=(200, 150, 130))
    img.save(img_path, format="JPEG")
    return img_path


# ── Health tests ──────────────────────────────────────────────────────────────

class TestHealthEndpoint:

    def test_health_returns_200(self, client):
        response = client.get("/api/v1/health")
        assert response.status_code == 200

    def test_health_response_schema(self, client):
        data = client.get("/api/v1/health").json()
        assert "status" in data
        assert "model_loaded" in data
        assert "uptime_seconds" in data
        assert "version" in data

    def test_health_model_loaded_true(self, client):
        data = client.get("/api/v1/health").json()
        assert data["model_loaded"] is True

    def test_health_timestamp_present(self, client):
        data = client.get("/api/v1/health").json()
        assert "timestamp" in data


# ── Model info tests ──────────────────────────────────────────────────────────

class TestModelInfoEndpoint:

    def test_model_info_returns_200(self, client):
        response = client.get("/api/v1/model/info")
        assert response.status_code == 200

    def test_model_info_schema(self, client):
        data = client.get("/api/v1/model/info").json()
        assert "model_name" in data
        assert "diagnostic_classes" in data
        assert "input_image_size" in data
        assert "is_loaded" in data

    def test_model_info_has_all_classes(self, client):
        data = client.get("/api/v1/model/info").json()
        classes = data["diagnostic_classes"]
        for label in ["NEV", "MEL", "BCC", "SCC", "ACK", "SEK"]:
            assert label in classes

    def test_model_info_image_size(self, client):
        data = client.get("/api/v1/model/info").json()
        assert data["input_image_size"] == 256


# ── Predict tests ─────────────────────────────────────────────────────────────

class TestPredictEndpoint:

    def test_predict_returns_200(self, client, sample_image):
        with open(sample_image, "rb") as f:
            response = client.post(
                "/api/v1/predict",
                data={"age": "45", "sex": "male", "localization": "back"},
                files={"file": ("test.jpg", f, "image/jpeg")},
            )
        assert response.status_code == 200

    def test_predict_response_schema(self, client, sample_image):
        with open(sample_image, "rb") as f:
            data = client.post(
                "/api/v1/predict",
                data={"age": "30", "sex": "female", "localization": "face"},
                files={"file": ("test.jpg", f, "image/jpeg")},
            ).json()

        assert "predicted_label" in data
        assert "confidence" in data
        assert "all_probabilities" in data
        assert "risk_level" in data
        assert "risk_color" in data
        assert "risk_explanation" in data
        assert "recommendations" in data
        assert "inference_time_ms" in data

    def test_predict_confidence_range(self, client, sample_image):
        with open(sample_image, "rb") as f:
            data = client.post(
                "/api/v1/predict",
                data={"age": "50"},
                files={"file": ("test.jpg", f, "image/jpeg")},
            ).json()
        assert 0.0 <= data["confidence"] <= 1.0

    def test_predict_six_probabilities(self, client, sample_image):
        with open(sample_image, "rb") as f:
            data = client.post(
                "/api/v1/predict",
                data={"age": "25"},
                files={"file": ("test.jpg", f, "image/jpeg")},
            ).json()
        assert len(data["all_probabilities"]) == 6

    def test_predict_without_file_returns_422(self, client):
        response = client.post("/api/v1/predict", data={"age": "30"})
        assert response.status_code == 422

    def test_predict_with_patient_id(self, client, sample_image):
        with open(sample_image, "rb") as f:
            data = client.post(
                "/api/v1/predict",
                data={"age": "60", "patient_id": "PAT-999"},
                files={"file": ("test.jpg", f, "image/jpeg")},
            ).json()
        assert data["patient_id"] == "PAT-999"

    def test_predict_with_all_v6_fields(self, client, sample_image):
        """All 7 V6.0 clinical fields accepted."""
        with open(sample_image, "rb") as f:
            response = client.post(
                "/api/v1/predict",
                data={
                    "age": "55",
                    "sex": "female",
                    "localization": "back",
                    "grew": "true",
                    "bleed": "false",
                    "diameter_1": "1.5",
                    "skin_cancer_history": "false",
                    "elevation": "true",
                },
                files={"file": ("test.jpg", f, "image/jpeg")},
            )
        assert response.status_code == 200

    def test_response_headers_present(self, client, sample_image):
        with open(sample_image, "rb") as f:
            response = client.post(
                "/api/v1/predict",
                data={"age": "40"},
                files={"file": ("test.jpg", f, "image/jpeg")},
            )
        assert "X-Request-ID" in response.headers
        assert "X-Process-Time-Ms" in response.headers


# ── Root endpoint ─────────────────────────────────────────────────────────────

class TestRootEndpoint:

    def test_root_returns_200(self, client):
        response = client.get("/")
        assert response.status_code == 200

    def test_root_has_docs_link(self, client):
        data = client.get("/").json()
        assert "docs" in data
