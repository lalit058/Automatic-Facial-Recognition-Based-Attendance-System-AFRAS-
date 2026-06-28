# afras_app/attendance/management/commands/train_hybrid.py
"""
Django management command to train hybrid face recognition model
"""

from django.core.management.base import BaseCommand
from accounts.models import Student
from recognition import HybridFaceRecognizer, FaceUtils
import numpy as np

class Command(BaseCommand):
    help = 'Train hybrid face recognition model from database'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force retraining even if model exists'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Print detailed output'
        )
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(self.style.SUCCESS("🚀 HYBRID FACE RECOGNITION TRAINING"))
        self.stdout.write(self.style.SUCCESS("=" * 60))
        
        # Get students with face encodings
        students = Student.objects.exclude(face_encoding__isnull=True)
        
        if students.count() == 0:
            self.stdout.write(self.style.ERROR("❌ No students with face encodings found"))
            return
        
        self.stdout.write(f"👥 Found {students.count()} students with face encodings")
        
        # Initialize recognizer
        recognizer = HybridFaceRecognizer()
        
        # Add students
        added_count = 0
        student_list = []
        
        for student in students:
            encoding = FaceUtils.decode_face_encoding(student.face_encoding)
            if encoding is not None:
                recognizer.add_student(encoding, student.full_name, student.id)
                added_count += 1
                student_list.append({
                    'name': student.full_name,
                    'id': student.id,
                    'encoding': encoding
                })
                if options['verbose']:
                    self.stdout.write(f"  ✅ Added: {student.full_name} (ID: {student.id})")
            else:
                self.stdout.write(f"  ⚠️ Invalid encoding: {student.full_name}")
        
        if added_count == 0:
            self.stdout.write(self.style.ERROR("❌ No valid encodings found"))
            return
        
        # Save model
        model_path = recognizer.save_model()
        
        # Show stats
        stats = recognizer.get_stats()
        self.stdout.write(self.style.SUCCESS(f"\n✅ Model trained successfully!"))
        self.stdout.write(f"📊 Stats:")
        self.stdout.write(f"   Total students: {stats['total_students']}")
        self.stdout.write(f"   KNN trained: {stats['knn_trained']}")
        self.stdout.write(f"   Model saved to: {model_path}")
        
        # ============================================
        # TEST ALL STUDENTS (FIXED)
        # ============================================
        self.stdout.write(f"\n🧪 Testing all students:")
        self.stdout.write("-" * 50)
        
        test_results = []
        
        for i, encoding in enumerate(recognizer.known_encodings):
            name = recognizer.known_names[i]
            student_id = recognizer.known_ids[i]
            
            # Test with the student's own encoding
            predicted_name, confidence, predicted_id, method = recognizer.recognize(encoding)
            
            # Check if correct
            is_correct = predicted_name == name
            status = "✅ PASS" if is_correct else "❌ FAIL"
            
            test_results.append({
                'name': name,
                'predicted': predicted_name,
                'confidence': confidence,
                'method': method,
                'status': status,
                'is_correct': is_correct
            })
            
            # Color coding for output
            if is_correct:
                self.stdout.write(f"  {status} | {name} → {predicted_name} ({confidence:.1f}%) using {method}")
            else:
                self.stdout.write(self.style.ERROR(f"  {status} | {name} → {predicted_name} ({confidence:.1f}%) using {method}"))
        
        # Summary
        passed = sum(1 for r in test_results if r['is_correct'])
        total = len(test_results)
        
        self.stdout.write("-" * 50)
        self.stdout.write(f"📊 Summary: {passed}/{total} students passed ({passed/total*100:.1f}%)")
        
        if passed == total:
            self.stdout.write(self.style.SUCCESS("🎉 All students passed the self-test!"))
        else:
            self.stdout.write(self.style.WARNING("⚠️ Some students failed the self-test. Consider re-registering them."))
            
            # Show failed students
            failed = [r for r in test_results if not r['is_correct']]
            if failed:
                self.stdout.write("\n❌ Failed students:")
                for f in failed:
                    self.stdout.write(f"   - {f['name']} → recognized as {f['predicted']} ({f['confidence']:.1f}%)")
        
        # ============================================
        # CROSS-TEST (Check if students are distinct)
        # ============================================
        if total > 1:
            self.stdout.write(f"\n🔄 Cross-testing (checking distinctness):")
            self.stdout.write("-" * 50)
            
            cross_failures = 0
            
            for i, encoding1 in enumerate(recognizer.known_encodings):
                name1 = recognizer.known_names[i]
                
                for j, encoding2 in enumerate(recognizer.known_encodings):
                    if i == j:
                        continue
                    
                    name2 = recognizer.known_names[j]
                    
                    # Test if student i is recognized as student j
                    predicted_name, confidence, _, _ = recognizer.recognize(encoding2)
                    
                    if predicted_name == name1:
                        self.stdout.write(self.style.WARNING(f"  ⚠️ {name1} recognized as {name2} ({confidence:.1f}%)"))
                        cross_failures += 1
            
            if cross_failures == 0:
                self.stdout.write(self.style.SUCCESS("  ✅ All students are distinct!"))
            else:
                self.stdout.write(self.style.WARNING(f"  ⚠️ {cross_failures} cross-matches found. Consider improving face encodings."))
        
        self.stdout.write("\n" + "=" * 60)