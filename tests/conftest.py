"""
tests/conftest.py
Shared pytest fixtures and configuration.
"""

import pytest
from unittest.mock import MagicMock


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
