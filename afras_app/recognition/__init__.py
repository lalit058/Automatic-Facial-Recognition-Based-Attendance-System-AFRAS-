# afras_app/recognition/__init__.py
"""
Face Recognition Module for Attendance System
"""

from .hybrid_recognizer import HybridFaceRecognizer
from .face_utils import FaceUtils
from .constants import RECOGNITION_CONFIG, CONFIDENCE_LEVELS, MODEL_PATHS

__all__ = [
    'HybridFaceRecognizer',
    'FaceUtils',
    'RECOGNITION_CONFIG',
    'CONFIDENCE_LEVELS',
    'MODEL_PATHS',
]