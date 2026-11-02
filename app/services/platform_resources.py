"""
app/services/platform_resources.py
Persistent storage and management of system-wide Platform Resources
(Walkthrough video, Mobile APK download, documentation, announcements).
Only Administrator can modify; publicly readable.
"""

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict

RESOURCES_FILE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "platform_resources.json",
)

DEFAULT_RESOURCES = {
    "video_walkthrough_url": "https://youtube.com/shorts/tRxtxYG6B8c?si=AkQqDnujgsMIfaL2",
    "mobile_apk_url": "/dashboard/assets/downloads/MedAssist-AI.apk",
    "landing_page_url": "/dashboard/landing.html",
    "thesis_en_url": "/dashboard/assets/docs/Thesis_Master_GLAA_EN.pdf",
    "thesis_fr_url": "/dashboard/assets/docs/Thesis_Master_GLAA_FR.pdf",
    "thesis_ar_url": "/dashboard/assets/docs/Thesis_Master_GLAA_AR.pdf",
    "announcement": "MedAssist AI Telemedicine & Multimodal Clinical Decision Support System Active",
    "apk_file_size": "55.57 MB",
    "apk_original_name": "MedAssist-AI.apk",
    "apk_uploaded_at": "2026-10-06T05:59:00Z",
    "thesis_en_size": "4.20 MB",
    "thesis_fr_size": "4.35 MB",
    "qr_code_url": "/dashboard/assets/images/qr-code.svg",
    "updated_at": datetime.now(timezone.utc).isoformat(),
    "updated_by": "system_default",
}


def get_platform_resources() -> Dict[str, Any]:
    """Retrieve current platform resources configuration with fallback to defaults."""
    if not os.path.exists(RESOURCES_FILE_PATH):
        try:
            with open(RESOURCES_FILE_PATH, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_RESOURCES, f, indent=2, ensure_ascii=False)
        except Exception:
            return DEFAULT_RESOURCES.copy()
        return DEFAULT_RESOURCES.copy()

    try:
        with open(RESOURCES_FILE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Ensure all keys exist
            for k, v in DEFAULT_RESOURCES.items():
                if k not in data:
                    data[k] = v
            return data
    except Exception:
        return DEFAULT_RESOURCES.copy()


def update_platform_resources(payload: Dict[str, Any], updated_by: str) -> Dict[str, Any]:
    """Update platform resources configuration (Admin only)."""
    current = get_platform_resources()
    allowed_fields = [
        "video_walkthrough_url",
        "mobile_apk_url",
        "landing_page_url",
        "thesis_en_url",
        "thesis_fr_url",
        "thesis_ar_url",
        "announcement",
        "apk_file_size",
        "apk_original_name",
        "apk_uploaded_at",
        "thesis_en_size",
        "thesis_fr_size",
        "qr_code_url",
    ]

    for field in allowed_fields:
        if field in payload and payload[field] is not None:
            current[field] = str(payload[field]).strip()

    current["updated_at"] = datetime.now(timezone.utc).isoformat()
    current["updated_by"] = updated_by

    with open(RESOURCES_FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=2, ensure_ascii=False)

    return current

