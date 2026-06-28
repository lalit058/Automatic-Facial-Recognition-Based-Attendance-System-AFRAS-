# afras_app/recognition/hybrid_recognizer.py
"""
Hybrid Face Recognition System with Ensemble Methods
"""

import numpy as np
import face_recognition
from sklearn.neighbors import KNeighborsClassifier
from sklearn.metrics.pairwise import cosine_similarity
import pickle
import os
from datetime import datetime
import logging
import cv2

from .constants import RECOGNITION_CONFIG, MODEL_PATHS, CONFIDENCE_LEVELS

logger = logging.getLogger(__name__)

# Define FaceQualityChecker inline to avoid import issues
class FaceQualityChecker:
    """Check face quality for better recognition"""
    
    @staticmethod
    def check_quality(face_image, config=None):
        if face_image is None or face_image.size == 0:
            return False, 0, ["Invalid image"]
        
        issues = []
        scores = []
        
        # Check size
        h, w = face_image.shape[:2]
        min_size = config.get('MIN_FACE_SIZE', 60) if config else 60
        if h < min_size or w < min_size:
            issues.append(f"Face too small ({h}x{w})")
            scores.append(0)
        else:
            size_score = min(1.0, (h / 100) * (w / 100))
            scores.append(size_score)
        
        # Check blur
        gray = cv2.cvtColor(face_image, cv2.COLOR_BGR2GRAY)
        blur = cv2.Laplacian(gray, cv2.CV_64F).var()
        blur_threshold = config.get('BLUR_THRESHOLD', 50) if config else 50
        if blur < blur_threshold:
            issues.append(f"Too blurry ({blur:.1f})")
            scores.append(0.2)
        else:
            blur_score = min(1.0, blur / 100)
            scores.append(blur_score)
        
        # Check brightness
        brightness = np.mean(gray)
        min_bright = config.get('MIN_BRIGHTNESS', 30) if config else 30
        max_bright = config.get('MAX_BRIGHTNESS', 220) if config else 220
        if brightness < min_bright:
            issues.append(f"Too dark ({brightness:.1f})")
            scores.append(0.1)
        elif brightness > max_bright:
            issues.append(f"Too bright ({brightness:.1f})")
            scores.append(0.1)
        else:
            brightness_score = 1 - abs(brightness - 128) / 128
            scores.append(brightness_score)
        
        # Calculate overall quality
        quality_score = np.mean(scores) if scores else 0
        is_good = quality_score > 0.6 and len(issues) == 0
        
        return is_good, quality_score, issues
    
    @staticmethod
    def get_face_region(frame, face_location, padding=20):
        top, right, bottom, left = face_location
        h, w = frame.shape[:2]
        top = max(0, top - padding)
        left = max(0, left - padding)
        bottom = min(h, bottom + padding)
        right = min(w, right + padding)
        return frame[top:bottom, left:right]

class HybridFaceRecognizer:
    """
    Hybrid face recognizer using ensemble of methods
    """
    
    def __init__(self, config=None):
        self.config = config or RECOGNITION_CONFIG
        self.known_encodings = []
        self.known_names = []
        self.known_ids = []
        
        # KNN for backup
        self.knn = KNeighborsClassifier(n_neighbors=3)
        self.knn_trained = False
        
        # Quality checker
        self.quality_checker = FaceQualityChecker()
        
        # Recognition history for smoothing
        self.history = []
        self.smooth_window = self.config.get('SMOOTHING_WINDOW', 5)
        
        logger.info("HybridFaceRecognizer initialized")
    
    def add_student(self, encoding, name, student_id):
        self.known_encodings.append(encoding)
        self.known_names.append(name)
        self.known_ids.append(student_id)
        
        if len(self.known_encodings) >= 3:
            self._train_knn()
        
        logger.info(f"Added student: {name} (ID: {student_id})")
    
    def _train_knn(self):
        if len(self.known_encodings) > 0:
            try:
                self.knn.fit(self.known_encodings, self.known_names)
                self.knn_trained = True
                logger.info("KNN trained successfully")
            except Exception as e:
                logger.error(f"KNN training failed: {e}")
                self.knn_trained = False
    
    def recognize(self, face_encoding, method='ensemble'):
        if not self.known_encodings:
            return "Unknown", 0, None, "none"
        
        results = {}
        
        # Method 1: Euclidean Distance
        distances = np.linalg.norm(self.known_encodings - face_encoding, axis=1)
        best_idx = np.argmin(distances)
        best_distance = distances[best_idx]
        distance_confidence = max(0, (1 - best_distance) * 100)
        
        results['distance'] = {
            'name': self.known_names[best_idx],
            'id': self.known_ids[best_idx],
            'confidence': distance_confidence,
            'score': 1 - best_distance,
            'idx': best_idx
        }
        
        # Method 2: Cosine Similarity
        similarities = cosine_similarity([face_encoding], self.known_encodings)[0]
        best_idx = np.argmax(similarities)
        best_similarity = similarities[best_idx]
        cosine_confidence = best_similarity * 100
        
        results['cosine'] = {
            'name': self.known_names[best_idx],
            'id': self.known_ids[best_idx],
            'confidence': cosine_confidence,
            'score': best_similarity,
            'idx': best_idx
        }
        
        # Method 3: KNN
        if self.knn_trained and len(self.known_encodings) >= 3:
            try:
                probabilities = self.knn.predict_proba([face_encoding])[0]
                best_idx = np.argmax(probabilities)
                best_prob = probabilities[best_idx]
                knn_name = self.knn.classes_[best_idx]
                knn_confidence = best_prob * 100
                
                knn_id = None
                for i, name in enumerate(self.known_names):
                    if name == knn_name:
                        knn_id = self.known_ids[i]
                        break
                
                results['knn'] = {
                    'name': knn_name,
                    'id': knn_id,
                    'confidence': knn_confidence,
                    'score': best_prob,
                    'idx': best_idx
                }
            except Exception as e:
                logger.warning(f"KNN prediction failed: {e}")
        
        # Choose method
        if method == 'ensemble' and len(results) > 1:
            return self._ensemble_vote(results)
        elif method == 'distance':
            return self._get_best_result(results, 'distance')
        elif method == 'cosine':
            return self._get_best_result(results, 'cosine')
        elif method == 'knn' and 'knn' in results:
            return self._get_best_result(results, 'knn')
        else:
            return self._get_best_result(results, list(results.keys())[0])
    
    def _ensemble_vote(self, results):
        weights = self.config.get('ENSEMBLE_WEIGHTS', {
            'distance': 0.4, 'cosine': 0.3, 'knn': 0.3
        })
        
        votes = {}
        method_scores = {}
        
        for method, result in results.items():
            name = result['name']
            score = result['score'] * weights.get(method, 0.33)
            
            if name not in votes:
                votes[name] = 0
                method_scores[name] = []
            
            votes[name] += score
            method_scores[name].append(result['score'])
        
        best_name = max(votes, key=votes.get)
        best_score = votes[best_name] / sum(weights.values())
        
        confidence = best_score * 100
        avg_score = np.mean(method_scores.get(best_name, [0]))
        confidence = max(confidence, avg_score * 100)
        
        best_id = None
        for i, name in enumerate(self.known_names):
            if name == best_name:
                best_id = self.known_ids[i]
                break
        
        distance_threshold = self.config.get('DISTANCE_THRESHOLD', 0.45)
        if best_score >= (1 - distance_threshold):
            return best_name, min(99, confidence), best_id, "ensemble"
        else:
            return "Unknown", confidence, None, "ensemble"
    
    def _get_best_result(self, results, method):
        if method not in results:
            method = list(results.keys())[0]
        
        result = results[method]
        confidence = result['confidence']
        
        if method == 'distance':
            threshold = self.config.get('DISTANCE_THRESHOLD', 0.45)
            if result['score'] >= (1 - threshold):
                return result['name'], confidence, result['id'], method
        elif method == 'cosine':
            threshold = self.config.get('COSINE_THRESHOLD', 0.55)
            if result['score'] >= threshold:
                return result['name'], confidence, result['id'], method
        else:
            threshold = self.config.get('CONFIDENCE_THRESHOLD', 50)
            if confidence >= threshold:
                return result['name'], confidence, result['id'], method
        
        return "Unknown", confidence, None, method
    
    def recognize_with_smoothing(self, face_encoding):
        name, confidence, student_id, method = self.recognize(face_encoding)
        
        self.history.append({
            'name': name,
            'confidence': confidence,
            'student_id': student_id,
            'timestamp': datetime.now()
        })
        
        if len(self.history) > self.smooth_window:
            self.history.pop(0)
        
        if len(self.history) > 1:
            names = [h['name'] for h in self.history]
            most_common = max(set(names), key=names.count)
            
            confidences = [h['confidence'] for h in self.history if h['name'] == most_common]
            avg_confidence = np.mean(confidences)
            
            student_id = None
            for h in self.history:
                if h['name'] == most_common and h['student_id'] is not None:
                    student_id = h['student_id']
                    break
            
            if avg_confidence > 40:
                return most_common, avg_confidence, student_id
        
        return name, confidence, student_id
    
    def process_frame(self, frame, resize_factor=None):
        resize_factor = resize_factor or self.config.get('RESIZE_FACTOR', 0.25)
        
        small_frame = cv2.resize(frame, (0, 0), fx=resize_factor, fy=resize_factor)
        rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
        
        face_locations = face_recognition.face_locations(rgb_small_frame)
        face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)
        
        results = []
        
        for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
            scale = int(1 / resize_factor)
            top, right, bottom, left = top*scale, right*scale, bottom*scale, left*scale
            
            face_region = FaceQualityChecker.get_face_region(frame, (top, right, bottom, left))
            is_good, quality_score, issues = self.quality_checker.check_quality(face_region, self.config)
            
            if not is_good:
                results.append({
                    'location': (top, right, bottom, left),
                    'name': 'Unknown',
                    'confidence': 0,
                    'student_id': None,
                    'quality_score': quality_score,
                    'issues': issues,
                    'is_quality_good': False
                })
                continue
            
            name, confidence, student_id = self.recognize_with_smoothing(face_encoding)
            
            results.append({
                'location': (top, right, bottom, left),
                'name': name,
                'confidence': confidence,
                'student_id': student_id,
                'quality_score': quality_score,
                'issues': issues,
                'is_quality_good': True
            })
        
        return results
    
    def get_confidence_level(self, confidence):
        for level, config in CONFIDENCE_LEVELS.items():
            if confidence >= config['min']:
                return config['label'], config['color']
        return CONFIDENCE_LEVELS['POOR']['label'], CONFIDENCE_LEVELS['POOR']['color']
    
    def save_model(self, filepath=None):
        filepath = filepath or MODEL_PATHS['hybrid']
        
        model_data = {
            'known_encodings': self.known_encodings,
            'known_names': self.known_names,
            'known_ids': self.known_ids,
            'knn': self.knn if self.knn_trained else None,
            'knn_trained': self.knn_trained,
            'config': self.config,
            'timestamp': datetime.now().isoformat(),
            'version': '1.0'
        }
        
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        with open(filepath, 'wb') as f:
            pickle.dump(model_data, f)
        
        logger.info(f"Model saved to {filepath}")
        return filepath
    
    def load_model(self, filepath=None):
        filepath = filepath or MODEL_PATHS['hybrid']
        
        if not os.path.exists(filepath):
            logger.warning(f"Model file not found: {filepath}")
            return False
        
        try:
            with open(filepath, 'rb') as f:
                model_data = pickle.load(f)
            
            self.known_encodings = model_data['known_encodings']
            self.known_names = model_data['known_names']
            self.known_ids = model_data['known_ids']
            self.knn = model_data['knn']
            self.knn_trained = model_data['knn_trained']
            self.config = model_data.get('config', self.config)
            
            logger.info(f"Model loaded from {filepath}")
            logger.info(f"Loaded {len(self.known_encodings)} students")
            return True
            
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            return False
    
    def get_stats(self):
        return {
            'total_students': len(self.known_encodings),
            'student_names': self.known_names,
            'knn_trained': self.knn_trained,
            'history_size': len(self.history),
            'smooth_window': self.smooth_window,
            'config': self.config
        }