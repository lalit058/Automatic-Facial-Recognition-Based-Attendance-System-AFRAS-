import face_recognition
import cv2
from accounts.models import Student

def recognize_faces():
    students = Student.objects.all()
    known_encodings = [face_recognition.face_encodings(face_recognition.load_image_file(s.photo.path))[0] for s in students]
    known_names = [s.name for s in students]

    cap = cv2.VideoCapture(0)
    recognized_students = []

    ret, frame = cap.read()
    if ret:
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        face_locations = face_recognition.face_locations(rgb_frame)
        face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)
        for face_encoding in face_encodings:
            matches = face_recognition.compare_faces(known_encodings, face_encoding)
            if True in matches:
                match_index = matches.index(True)
                recognized_students.append(students[match_index])
    cap.release()
    return recognized_students
