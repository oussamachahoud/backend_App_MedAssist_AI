"""
app/schemas/prediction.py
Pydantic schemas for clinical predictions, risk evaluation, and Grad-CAM++ metadata.
"""

from app.models.response import ClassProbability, PredictResponse

__all__ = ["ClassProbability", "PredictResponse"]

