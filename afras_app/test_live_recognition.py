# test_live_recognition.py - Fixed version
import cv2
import face_recognition
import numpy as np
from recognition import HybridFaceRecognizer

recognizer = HybridFaceRecognizer()
recognizer.load_model()

print("🎥 Testing live recognition...")
print("Press 'q' to quit")

cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

while True:
    ret, frame = cap.read()
    if not ret:
        break
    
    # Process frame
    small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
    rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
    
    face_locations = face_recognition.face_locations(rgb_small_frame)
    face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)
    
    for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
        top, right, bottom, left = top*4, right*4, bottom*4, left*4
        
        # FIXED: recognize returns 4 values
        name, confidence, student_id, method = recognizer.recognize(face_encoding)
        
        # Calculate distance to check quality
        if recognizer.known_encodings:
            distances = np.linalg.norm(recognizer.known_encodings - face_encoding, axis=1)
            best_distance = np.min(distances)
            print(f"   Distance to best match: {best_distance:.4f}")
        
        # Use distance-based decision for display
        if recognizer.known_encodings:
            distances = np.linalg.norm(recognizer.known_encodings - face_encoding, axis=1)
            best_idx = np.argmin(distances)
            best_distance = distances[best_idx]
            
            if best_distance < 0.45:
                display_name = recognizer.known_names[best_idx]
                display_confidence = max(50, (1 - best_distance) * 100)
                color = (0, 255, 0)
            else:
                display_name = "Unknown"
                display_confidence = 0
                color = (0, 0, 255)
        else:
            display_name = name if name != "Unknown" else "Unknown"
            display_confidence = confidence
            color = (0, 255, 0) if name != "Unknown" else (0, 0, 255)
        
        cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
        cv2.putText(frame, f"{display_name} ({display_confidence:.1f}%)", (left, top-10), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
    
    cv2.putText(frame, f"Faces: {len(face_locations)}", 
               (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    
    cv2.imshow('Live Recognition', frame)
    
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
print("👋 Test completed!")