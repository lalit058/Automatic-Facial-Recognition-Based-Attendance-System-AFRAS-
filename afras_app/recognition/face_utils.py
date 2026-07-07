# afras_app/recognition/face_utils.py
"""
Face Utilities for Encoding and Processing
"""

import cv2
import numpy as np
import face_recognition
import json
import ast
from PIL import Image
import io
import base64

class FaceUtils:
    """Utility class for face processing operations"""
    
    @staticmethod
    def decode_face_encoding(encoding_data):
        """
        Decode face encoding from various formats
        
        Args:
            encoding_data: Face encoding in list, string, or numpy array format
            
        Returns:
            numpy array: Decoded face encoding
        """
        if encoding_data is None:
            return None
        
        # If already numpy array
        if isinstance(encoding_data, np.ndarray):
            return encoding_data
        
        # If list
        if isinstance(encoding_data, list):
            return np.array(encoding_data, dtype=np.float64)
        
        # If string
        if isinstance(encoding_data, str):
            try:
                # Try JSON first
                return np.array(json.loads(encoding_data), dtype=np.float64)
            except:
                try:
                    # Try ast literal_eval
                    return np.array(ast.literal_eval(encoding_data), dtype=np.float64)
                except:
                    return None
        
        return None
    
    @staticmethod
    def encode_face_for_storage(encoding):
        """
        Encode face encoding for database storage
        
        Args:
            encoding: Numpy array face encoding
            
        Returns:
            list: Face encoding as list for JSON storage
        """
        if isinstance(encoding, np.ndarray):
            return encoding.tolist()
        elif isinstance(encoding, list):
            return encoding
        return None
    
    @staticmethod
    def detect_faces(image, resize_factor=0.25):
        """
        Detect faces in an image
        
        Args:
            image: numpy array image
            resize_factor: Factor to resize image for faster processing
            
        Returns:
            tuple: (face_locations, face_encodings)
        """
        # Resize for faster processing
        small_image = cv2.resize(image, (0, 0), fx=resize_factor, fy=resize_factor)
        rgb_image = cv2.cvtColor(small_image, cv2.COLOR_BGR2RGB)
        
        # Detect faces
        face_locations = face_recognition.face_locations(rgb_image)
        face_encodings = face_recognition.face_encodings(rgb_image, face_locations)
        
        # Scale back locations
        scale = int(1 / resize_factor)
        face_locations = [
            (top * scale, right * scale, bottom * scale, left * scale)
            for (top, right, bottom, left) in face_locations
        ]
        
        return face_locations, face_encodings
    
    @staticmethod
    def draw_face_box(frame, face_location, name, confidence, student_id=None, color=None):
        """
        Draw face bounding box with label
        
        Args:
            frame: Image frame
            face_location: (top, right, bottom, left)
            name: Person's name
            confidence: Confidence percentage
            student_id: Student ID
            color: Box color (BGR)
        """
        top, right, bottom, left = face_location
        
        # Ensure coordinates are within frame
        h, w = frame.shape[:2]
        top = max(0, min(top, h))
        bottom = max(0, min(bottom, h))
        left = max(0, min(left, w))
        right = max(0, min(right, w))
        
        # Determine color
        if color is None:
            if name != "Unknown" and confidence > 50:
                color = (0, 255, 0)  # Green
            elif name != "Unknown" and confidence > 30:
                color = (0, 255, 255)  # Yellow
            else:
                color = (0, 0, 255)  # Red
        
        # Draw rectangle
        cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
        
        # Prepare label
        if name != "Unknown":
            label = f"{name} ({confidence:.1f}%)"
            if student_id:
                label += f" ID:{student_id}"
        else:
            label = "Unknown"
        
        # Draw label background
        label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
        label_y = max(0, top - 10)
        cv2.rectangle(frame, 
                    (left, label_y - label_size[1] - 5), 
                    (left + label_size[0] + 5, label_y + 5), 
                    color, -1)
        
        # Draw label text
        cv2.putText(frame, label, (left + 3, label_y), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
        
        return color
    
    @staticmethod
    def draw_quality_info(frame, face_location, quality_score, issues):
        """
        Draw quality information on frame
        
        Args:
            frame: Image frame
            face_location: (top, right, bottom, left)
            quality_score: Quality score (0-1)
            issues: List of quality issues
        """
        top, right, bottom, left = face_location
        
        # Show quality score
        quality_text = f"Quality: {quality_score:.2f}"
        cv2.putText(frame, quality_text, (left, bottom + 20), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        
        # Show issues if any
        if issues:
            for i, issue in enumerate(issues[:2]):
                cv2.putText(frame, issue, (left, bottom + 40 + i*15), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 0, 255), 1)
    
    @staticmethod
    def image_to_base64(image):
        """Convert image to base64 string"""
        _, buffer = cv2.imencode('.jpg', image)
        return base64.b64encode(buffer).decode('utf-8')
    
    @staticmethod
    def base64_to_image(base64_string):
        """Convert base64 string to image"""
        image_data = base64.b64decode(base64_string)
        image = Image.open(io.BytesIO(image_data))
        return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)