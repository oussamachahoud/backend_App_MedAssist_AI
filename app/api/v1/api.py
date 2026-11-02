"""
app/api/v1/api.py
Central router aggregating all v1 endpoints for MedAssist AI V2.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    admin,
    analyses,
    auth,
    patients,
    profile,
    public,
    referrals,
)

api_router = APIRouter()

# Authentication & authorization endpoints
api_router.include_router(auth.router)

# Clinical analyses CRUD, feedback, and PDF export
api_router.include_router(analyses.router)

# Pseudonymous patient management and lesion timelines
api_router.include_router(patients.router)

# Telemedicine referrals between GP and Specialist
api_router.include_router(referrals.router)

# Doctor profile management and clinical metrics
api_router.include_router(profile.router)

# Public directory and QR follow-up verification
api_router.include_router(public.router)

# Administrative management and system analytics
api_router.include_router(admin.router)
