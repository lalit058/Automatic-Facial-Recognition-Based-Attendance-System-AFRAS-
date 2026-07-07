# afras_app/recognition/constants.py
import os
from pathlib import Path

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent

# Model paths
MODEL_DIR = os.path.join(BASE_DIR, 'models')
os.makedirs(MODEL_DIR, exist_ok=True)

# Recognition settings
RECOGNITION_CONFIG = {
    'DETECTION_MODEL': 'cnn',
    'RESIZE_FACTOR': 0.25,
    'ENCODING_MODEL': 'large',
    'ENCODING_DIM': 128,
    'DISTANCE_THRESHOLD': 0.45,
    'COSINE_THRESHOLD': 0.55,
    'CONFIDENCE_THRESHOLD': 50,
    'MIN_FACE_SIZE': 60,
    'BLUR_THRESHOLD': 50,
    'MIN_BRIGHTNESS': 30,
    'MAX_BRIGHTNESS': 220,
    'FPS_TARGET': 30,
    'FRAME_SKIP': 1,
    'SMOOTHING_WINDOW': 5,
    'ENSEMBLE_WEIGHTS': {
        'distance': 0.4,
        'cosine': 0.3,
        'knn': 0.3
    }
}

# Confidence levels
CONFIDENCE_LEVELS = {
    'HIGH': {'min': 80, 'label': 'High', 'color': (0, 255, 0)},
    'MEDIUM': {'min': 60, 'label': 'Medium', 'color': (0, 255, 255)},
    'LOW': {'min': 40, 'label': 'Low', 'color': (0, 165, 255)},
    'POOR': {'min': 0, 'label': 'Poor', 'color': (0, 0, 255)}
}

# Model file paths
MODEL_PATHS = {
    'hybrid': os.path.join(MODEL_DIR, 'hybrid_model.pkl'),
    'knn': os.path.join(MODEL_DIR, 'knn_model.pkl'),
    'svm': os.path.join(MODEL_DIR, 'svm_face_model.pkl'),
}