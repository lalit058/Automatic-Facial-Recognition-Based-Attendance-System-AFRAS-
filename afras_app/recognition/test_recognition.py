# test_recognition.py
import os
import sys
import django
import cv2
import face_recognition
import numpy as np

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'afras_backend.settings')
django.setup()

from recognition import HybridFaceRecognizer
from accounts.models import Student
from recognition.face_utils import FaceUtils

print("=" * 60)
print("🧪 TESTING HYBRID FACE RECOGNITION")
print("=" * 60)

# Load the model
recognizer = HybridFaceRecognizer()
if not recognizer.load_model():
    print("❌ Model not loaded! Run: python manage.py train_hybrid")
    exit()

stats = recognizer.get_stats()
print(f"✅ Model loaded: {stats['total_students']} students")
print(f"👥 Students: {stats['student_names']}")

# Get your stored encoding
your_student = Student.objects.get(id=9)
stored_encoding = FaceUtils.decode_face_encoding(your_student.face_encoding)

print("\n📸 Testing with webcam...")
print("Press 'c' to test current frame, 'q' to quit")

cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

while True:
    ret, frame = cap.read()
    if not ret:
        break
    
    # Show live feed
    cv2.imshow('Test Recognition - Press c to test, q to quit', frame)
    
    key = cv2.waitKey(1) & 0xFF
    if key == ord('c'):
        # Process the frame
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        face_locations = face_recognition.face_locations(rgb_frame)
        face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)
        
        if face_encodings:
            print("\n" + "=" * 50)
            print("📊 RECOGNITION RESULTS")
            print("=" * 50)
            
            for i, encoding in enumerate(face_encodings):
                # Get prediction
                name, confidence, student_id, method = recognizer.recognize(encoding)
                
                # Calculate distance to stored encoding
                if stored_encoding is not None:
                    distance = np.linalg.norm(encoding - stored_encoding)
                else:
                    distance = 1.0
                
                print(f"\nFace {i+1}:")
                print(f"  Name: {name}")
                print(f"  Confidence: {confidence:.1f}%")
                print(f"  Method: {method}")
                print(f"  Distance to stored: {distance:.3f}")
                print(f"  Student ID: {student_id}")
                
                # Determine if recognized correctly
                if name == "Lalit Negi" and confidence > 50:
                    print("  ✅ Recognized correctly!")
                elif name != "Unknown" and confidence > 50:
                    print(f"  ⚠️ Recognized as: {name}")
                else:
                    print("  ❌ Not recognized")
            
            print("=" * 50)
        else:
            print("❌ No face detected")
    
    elif key == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
print("👋 Test completed!")