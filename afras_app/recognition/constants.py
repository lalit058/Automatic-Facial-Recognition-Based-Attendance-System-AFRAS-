# afras_app/recognition/constants.py
import os
from pathlib import Path

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent

# Model paths
MODEL_DIR = os.path.join(BASE_DIR, 'models')
os.makedirs(MODEL_DIR, exist_ok=True)

# Recognition settings - OPTIMIZED FOR SINGLE SHOT DETECTION
# All algorithm settings remain the same, only performance parameters changed
RECOGNITION_CONFIG = {
    # Model settings - UNCHANGED
    'DETECTION_MODEL': 'cnn',  # UNCHANGED
    'RESIZE_FACTOR': 0.25,     # UNCHANGED
    'ENCODING_MODEL': 'large', # UNCHANGED
    'ENCODING_DIM': 128,       # UNCHANGED
    
    # Thresholds - UNCHANGED (algorithm parameters)
    'DISTANCE_THRESHOLD': 0.45,  # UNCHANGED
    'COSINE_THRESHOLD': 0.55,    # UNCHANGED
    'CONFIDENCE_THRESHOLD': 50,  # UNCHANGED
    
    # Quality checks - UNCHANGED
    'MIN_FACE_SIZE': 60,         # UNCHANGED
    'BLUR_THRESHOLD': 50,        # UNCHANGED
    'MIN_BRIGHTNESS': 30,        # UNCHANGED
    'MAX_BRIGHTNESS': 220,       # UNCHANGED
    
    # Ensemble weights - UNCHANGED
    'ENSEMBLE_WEIGHTS': {
        'distance': 0.4,         # UNCHANGED
        'cosine': 0.3,           # UNCHANGED
        'knn': 0.3               # UNCHANGED
    },
    
    # PERFORMANCE OPTIMIZATIONS - ONLY THESE CHANGED
    'FPS_TARGET': 15,            # CHANGED: 30 → 15 (faster processing)
    'FRAME_SKIP': 2,             # CHANGED: 1 → 2 (process every 2nd frame)
    'SMOOTHING_WINDOW': 1,       # CHANGED: 5 → 1 (NO smoothing delay)
    'USE_FAST_DETECTION': True,  # NEW: Enable faster detection
}

# Confidence levels - UNCHANGED
CONFIDENCE_LEVELS = {
    'HIGH': {'min': 80, 'label': 'High', 'color': (0, 255, 0)},
    'MEDIUM': {'min': 60, 'label': 'Medium', 'color': (0, 255, 255)},
    'LOW': {'min': 40, 'label': 'Low', 'color': (0, 165, 255)},
    'POOR': {'min': 0, 'label': 'Poor', 'color': (0, 0, 255)}
}

# Model file paths - UNCHANGED
MODEL_PATHS = {
    'hybrid': os.path.join(MODEL_DIR, 'hybrid_model.pkl'),
    'knn': os.path.join(MODEL_DIR, 'knn_model.pkl'),
    'svm': os.path.join(MODEL_DIR, 'svm_face_model.pkl'),
}