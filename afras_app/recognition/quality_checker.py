# afras_app/recognition/quality_checker.py
"""
Face Quality Assessment Module
"""

import cv2
import numpy as np

class FaceQualityChecker:
    """Check face quality for better recognition"""
    
    @staticmethod
    def check_quality(face_image, config=None):
        """
        Check if face image is good quality
        
        Args:
            face_image: numpy array of face region
            config: Configuration dict
            
        Returns:
            tuple: (is_good, quality_score, issues)
        """
        if face_image is None or face_image.size == 0:
            return False, 0, ["Invalid image"]
        
        issues = []
        scores = []
        
        # 1. Check face size
        h, w = face_image.shape[:2]
        min_size = config.get('MIN_FACE_SIZE', 60) if config else 60
        
        if h < min_size or w < min_size:
            issues.append(f"Face too small ({h}x{w})")
            scores.append(0)
        else:
            size_score = min(1.0, (h / 100) * (w / 100))
            scores.append(size_score)
        
        # 2. Check blur
        gray = cv2.cvtColor(face_image, cv2.COLOR_BGR2GRAY)
        blur = cv2.Laplacian(gray, cv2.CV_64F).var()
        blur_threshold = config.get('BLUR_THRESHOLD', 50) if config else 50
        
        if blur < blur_threshold:
            issues.append(f"Too blurry ({blur:.1f})")
            scores.append(0.2)
        else:
            blur_score = min(1.0, blur / 100)
            scores.append(blur_score)
        
        # 3. Check brightness
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
        
        # 4. Check contrast
        contrast = np.std(gray)
        if contrast < 20:
            issues.append(f"Low contrast ({contrast:.1f})")
            scores.append(0.3)
        else:
            contrast_score = min(1.0, contrast / 50)
            scores.append(contrast_score)
        
        # Calculate overall quality score
        quality_score = np.mean(scores) if scores else 0
        is_good = quality_score > 0.6 and len(issues) == 0
        
        return is_good, quality_score, issues
    
    @staticmethod
    def get_face_region(frame, face_location, padding=20):
        """
        Extract face region from frame
        
        Args:
            frame: Full image frame
            face_location: (top, right, bottom, left)
            padding: Extra padding around face
            
        Returns:
            numpy array: Face region
        """
        top, right, bottom, left = face_location
        
        # Add padding
        h, w = frame.shape[:2]
        top = max(0, top - padding)
        left = max(0, left - padding)
        bottom = min(h, bottom + padding)
        right = min(w, right + padding)
        
        return frame[top:bottom, left:right]