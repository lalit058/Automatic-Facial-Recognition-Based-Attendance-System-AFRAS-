# AFRAS - Automatic Facial Recognition Attendance System

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://python.org)
[![Django](https://img.shields.io/badge/Django-4.2-green.svg)](https://djangoproject.com)
[![OpenCV](https://img.shields.io/badge/OpenCV-4.8-red.svg)](https://opencv.org)
[![scikit-learn](https://img.shields.io/badge/scikit--learn-1.2-orange.svg)](https://scikit-learn.org)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](http://makeapullrequest.com)
[![GitHub Stars](https://img.shields.io/github/stars/lalit058/Automatic-Facial-Recognition-Based-Attendance-System-AFRAS-.svg)](https://github.com/lalit058/Automatic-Facial-Recognition-Based-Attendance-System-AFRAS-/stargazers)
[![GitHub Forks](https://img.shields.io/github/forks/lalit058/Automatic-Facial-Recognition-Based-Attendance-System-AFRAS-.svg)](https://github.com/lalit058/Automatic-Facial-Recognition-Based-Attendance-System-AFRAS-/network)

> **Automatic Facial Recognition Based Attendance System** - A modern, intelligent, and contactless solution that automates institutional logging using ResNet-101 and computer vision. Eliminate manual entry and proxy attendance with our biometric intelligence system.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Technology Stack](#technology-stack)
- [System Architecture](#system-architecture)
- [Project Structure](#project-structure)
- [Installation Guide](#installation-guide)
- [Configuration](#configuration)
- [Usage Guide](#usage-guide)
- [API Documentation](#api-documentation)
- [Troubleshooting](#troubleshooting)
- [Screenshots](#screenshots)
- [Contributing](#contributing)
- [Team](#team)
- [License](#license)
- [Acknowledgments](#acknowledgments)

---

## 🎯 Overview

**AFRAS** (Automatic Facial Recognition Attendance System) is a web-based application that automates attendance tracking using facial recognition technology. It eliminates traditional manual roll calls, proxy attendance, and administrative overhead by providing a contactless, accurate, and real-time attendance solution.

### Problem Statement
- Traditional roll calls waste **5-10 minutes** per lecture
- Proxy attendance through RFID card sharing
- Human errors in manual entry
- Lack of real-time monitoring
- Hygiene concerns with fingerprint scanners

### Our Solution
- **Contactless** facial recognition
- **Real-time** attendance marking (<3 seconds)
- **86%+** recognition accuracy
- **Automatic** session scheduling
- **Comprehensive** reporting and analytics
- **Zero** proxy attendance
---

## ✨ Features

### Core Features

| Feature | Description |
|---------|-------------|
| **Hybrid Face Recognition** | Ensemble of Euclidean Distance, Cosine Similarity, and KNN |
| **Real-time Detection** | 15+ FPS processing with 0.1s recognition time |
| **Single-Shot Marking** | Instant attendance on first detection (no delay) |
| **Quality Validation** | Blur, brightness, and size checks (40% fewer false positives) |
| **Auto Scheduling** | Automatic session generation from routines (except Saturday) |
| **Session Management** | Auto-start/end with background job (30s interval) |
| **Live Monitoring** | Real-time dashboard with video feed |
| **Validation System** | Section/semester verification (no proxy attendance) |
| **Reporting** | Minute-by-minute tracking, retention analytics, CSV export |
| **Manual Override** | Edit attendance for leaves, late entries, etc. |

### User Roles

| Role | Permissions |
|------|-------------|
| **Admin** | Full system control, user management, reports |
| **Staff** | Start sessions, monitor attendance, generate reports |

### Recognition Methods

| Method | Weight | Description |
|--------|--------|-------------|
| **Euclidean Distance** | 40% | Measures straight-line distance between face encodings |
| **Cosine Similarity** | 30% | Measures cosine angle between face vectors |
| **KNN Classifier** | 30% | Backup recognition using k-nearest neighbors |

---

## 🛠️ Technology Stack

### Backend
| Technology | Purpose |
|------------|---------|
| **Python 3.9+** | Core programming language |
| **Django 4.2** | Web framework |
| **OpenCV 4.8** | Image processing |
| **face_recognition** | Face detection & encoding |
| **scikit-learn** | KNN classifier, ensemble methods |
| **NumPy** | Numerical operations |
| **SQLite/MySQL** | Database |

### Frontend
| Technology | Purpose |
|------------|---------|
| **HTML5** | Structure |
| **CSS3** | Styling, responsive design |
| **JavaScript** | Dynamic interactions, AJAX |
| **Font Awesome** | Icons |
| **Google Fonts** | Typography |

### Development Tools
| Tool | Purpose |
|------|---------|
| **Git** | Version control |
| **GitHub** | Repository hosting |
| **VS Code** | IDE |
| **pip** | Package management |
| **virtualenv** | Virtual environment |

---

## 🏗️ System Architecture

### Architecture Diagram
```
┌─────────────────────────────────────────────────────────────────┐
│                         WEB BROWSER                            │
│                    (Dashboard / Monitoring)                     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         DJANGO BACKEND                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │   Views     │  │   Models    │  │     Scheduler            │ │
│  │  (HTTP API) │  │  (Database) │  │ (Background Job - 30s)   │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
          │                    │                    │
          ▼                    ▼                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                    RECOGNITION ENGINE                           │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │              HYBRID FACE RECOGNIZER                         ││
│  │  ┌──────────┐  ┌──────────┐  ┌──────────────────────────┐ ││
│  │  │  HOG     │  │  CNN     │  │   Ensemble Voting         │ ││
│  │  │Detection │  │Detection │  │  (Euclidean + Cosine +KNN)│ ││
│  │  └──────────┘  └──────────┘  └──────────────────────────┘ ││
│  │  ┌─────────────────────────────────────────────────────────┐││
│  │  │           Quality Checker                              │││
│  │  │  (Blur, Brightness, Size, Validation)                  │││
│  │  └─────────────────────────────────────────────────────────┘││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
          │                    │                    │
          ▼                    ▼                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                         DATA LAYER                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │  SQLite/    │  │  Face       │  │  Attendance             │ │
│  │  MySQL DB   │  │  Encodings  │  │  Logs                   │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Recognition Pipeline
```
Camera Input
    ↓
Frame Resize (25%)
    ↓
Face Detection (HOG/CNN)
    ↓
Quality Check
    ├── Size (≥60px)
    ├── Blur (Laplacian ≥50)
    └── Brightness (30-220)
    ↓
Face Encoding (128-d vector)
    ↓
Ensemble Recognition
    ├── Euclidean Distance (40%)
    ├── Cosine Similarity (30%)
    └── KNN Classifier (30%)
    ↓
Confidence Calculation
    ↓
Database Update (Single-Shot)
```

---

## 📁 Project Structure

```
AFRAS/
├── afras_app/                          # Main application directory
│   ├── accounts/                       # User authentication module
│   │   ├── migrations/                 # Database migrations
│   │   ├── init.py
│   │   ├── admin.py # Admin configuration
│   │   ├── apps.py # App configuration
│   │   ├── models.py # Student, StaffProfile models
│   │   ├── tests.py # Test cases
│   │   ├── urls.py # Authentication URLs
│   │   └── views.py # Login, registration views
│   │
│   ├── afras_backend/                  # Project settings
│   │   ├── init.py
│   │   ├── asgi.py # ASGI configuration
│   │   ├── settings.py # Django configuration
│   │   ├── urls.py # Main URL routing
│   │   ├── views.py # Project views
│   │   └── wsgi.py # WSGI configuration
│   │
│   ├── attendance/                     # Core attendance module
│   │   ├── management/                 # Database migrations
│   │   │  ├── commands/
│   │   │  │  ├── run_scheduler.py                   
│   │   │  │  ├── setup_weekly_routines.py                   
│   │   │  │  ├── train_hybrid.py                   
│   │   ├── migrations/                    
│   │   ├── init.py
│   │   ├── apps.py                     # App configuration
│   │   ├── models.py                   # Session, AttendanceLog models
│   │   ├── scheduler.py                # Auto-scheduling logic
│   │   ├── services.py                 # Business logic services
│   │   ├── test_scheduler_order.py     # Scheduler order tests
│   │   ├── test_weekly_logic.py        # Weekly logic tests
│   │   ├── tests.py                    # Test cases
│   │   ├── urls.py                     # Attendance URLs
│   │   ├── utils.py                    # Helper functions
│   │   └── views.py                    # All attendance views
│   │
│   ├── dashboard/                      # Dashboard module
│   │   ├── commands/                   # Management commands
│   │   ├── migrations/                 # Database migrations
│   │   ├── init.py
│   │   ├── admin.py                    # Admin configuration
│   │   ├── apps.py                     # App configuration
│   │   ├── automation_engine.py        # Automation engine
│   │   ├── forms.py                    # Dashboard forms
│   │   ├── models.py                   # Routine model
│   │   ├── tests.py                    # Test cases
│   │   ├── urls.py                     # Dashboard URLs
│   │   └── views.py                    # Dashboard views
│   │
│   ├── media/                          # User-uploaded files
│   │   ├── staff_photos/               # Student face images
│   │   ├── student_docs/               # Student face images
│   │   ├── student_photos/             # Student face images
│   │   └── team_member/                # Team member photos
│   │
│   ├── recognition/                    # Face recognition engine
│   │   ├── migrations/
│   │   ├── init.py
│   │   ├── constants.py                # Configuration constants
│   │   ├── face_utils.py               # Face utilities
│   │   ├── hybrid_recognizer.py        # Ensemble recognition
│   │   ├── quality_checker.py          # Face quality validation
│   │   ├── test_recognition.py         # Recognition tests
│   │   ├── tests.py                    # Test cases
│   │   ├── urls.py                     # Recognition URLs
│   │   └── views.py                    # Recognition views
│   │
│   ├── static/                         # Static files
│   │   ├── css/
│   │   │   ├── configuration.css
│   │   │   ├── footer.css 
│   │   │   ├── photo-modal.css
│   │   │   └── sidebar.css
│   │   ├── js/
│   │   │   ├── photo-model.js
│   │   │   └── sidebar.js
│   │   └── images/
│   │
│   ├── templates/                      # HTML templates
│   │   ├── accounts/                   # Auth templates
│   │   │   ├── login.html
│   │   │   ├── password_reset_email.html
│   │   │   ├── register_staff.html
│   │   │   └── register.html
│   │   ├── attendance/                 # Attendance templates
│   │   │   ├── unified_sessions.html
│   │   │   ├── attendance_pattern.html
│   │   │   ├── attendance_report.html
│   │   │   ├── edit_session.html
│   │   │   ├── mark_attendance.html
│   │   │   ├── session_details.html
│   │   │   ├── session_summary.html
│   │   │   ├── start_session.html
│   │   │   ├── student_attendance_record.html
│   │   │   └── session_details.html
│   │   └── dashboard/                  # Dashboard templates
│   │   │   ├── activity_logs.html
│   │   │   ├── base.html
│   │   │   ├── configuration.html
│   │   │   ├── edit_staff.html
│   │   │   ├── edit_student.html
│   │   │   ├── footer.html
│   │   │   ├── home.html
│   │   │   ├── notificatons_list.html
│   │   │   ├── sidebar.html
│   │   │   ├── staff_directory.html
│   │   │   ├── staff_profile.html
│   │   │   ├── student_directory.html
│   │   │   ├── student_profile.html
│   │   │   └── system_logs.html
│   │   └── registration/
│   │   │   ├── password_reset_complete.html
│   │   │   ├── password_reset_confirm.html
│   │   │   ├── password_reset_email.html
│   │   │   └── password_reset_form.html
│   │   └── home.html
│   │
│   ├── build.sh                        # Build/Deployment script
│   ├── manage.py                       # Django management script
│   ├── requirements.txt                # Python dependencies
│   └── test_live_recognition.py        # Live recognition test script
│
├── venv/                               # Virtual environment
├── .gitignore                          # Git ignore file
├── .hintrc                             # Hint configuration
├── db.sqlite3                          # SQLite database
├── db.sqlite3.backup                   # Database backup
├── debug_detected_Adam_Scott_0001.jpg  # Debug image
└── debug_face_20260318_234759.jpg      # Debug face image
```

---

## 📥 Installation Guide

### Prerequisites

| Requirement | Version |
|-------------|---------|
| Python | 3.9+ |
| pip | Latest |
| Git | Latest |
| Webcam | 720p+ (for face capture) |
| RAM | 4GB+ |
| Storage | 1GB+ |

### Step 1: Clone the Repository
```bash
git clone https://github.com/lalit058/Automatic-Facial-Recognition-Based-Attendance-System-AFRAS-.git
cd Automatic-Facial-Recognition-Based-Attendance-System-AFRAS-
```

### Step 2: Create Virtual Environment
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies
```bash
cd afras_app
pip install -r requirements.txt
```

### Step 4: Database Setup
```bash
python manage.py makemigrations
python manage.py migrate
```

### Step 5: Create Superuser (Admin)
```bash
python manage.py createsuperuser
# Follow the prompts to create admin account
```

### Step 6: Train Face Recognition Model
```bash
# First, add student faces through admin panel
# Then train the model
python manage.py train_hybrid --verbose
```

**Training Options:**
| Option | Description |
|--------|-------------|
| `--verbose` | Show detailed training logs |
| `--force` | Force retraining even if model exists |
| `--validate` | Validate model performance after training |

**Example Output:**
```
🚀 Training Hybrid Face Recognition Model
==================================================
📊 Loading student data...
✅ Loaded 45 students with face encodings
📊 Training KNN classifier...
✅ KNN trained with 45 samples
📊 Saving model to models/hybrid_face_model.pkl
✅ Model saved successfully
📊 Model Statistics:
   - Total Students: 45
   - KNN Trained: Yes
   - Smooth Window: 1
==================================================
✅ Training complete! Accuracy: 86.7%
```

### Step 7: Test Recognition (Optional)
```bash
python test_recognition.py
# This will test the live recognition with your webcam
```

### Step 8: Run Development Server
```bash
python manage.py runserver
```

### Step 9: Access the Application
- **Home Page:** `http://127.0.0.1:8000/`
- **Admin Panel:** `http://127.0.0.1:8000/admin/`
- **Session Management:** `http://127.0.0.1:8000/attendance/sessions/`
- **Attendance Report:** `http://127.0.0.1:8000/attendance/attendance-report/`

---

## ⚙️ Configuration

### Environment Variables
Create a `.env` file in the `afras_app/` directory:

```env
# Django Settings
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-local-fallback-key')
DEBUG = os.environ.get('DEBUG', 'True') == 'True
ALLOWED_HOSTS = localhost,127.0.0.1, localhost

# Database
IS_RENDER = 'RENDER' in os.environ

if os.environ.get('DATABASE_URL'):
    DATABASES = {
        'default': dj_database_url.config(conn_max_age=600)
    }
elif IS_RENDER:
    # Safe fallback during Render build/deploy
    DATABASES = {
        'default': dj_database_url.config(
            default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
            conn_max_age=600,
        )
    }
else:
    # Local development fallback (MySQL)
    DATABASES = {
        'default': dj_database_url.config(
            default='mysql://root:Lalit%4098@127.0.0.1:3306/afras_db',
            conn_max_age=600,
        )
    }

# Camera Settings
CAMERA_SOURCE=0  # 0 for local webcam, or URL for IP camera
```

### Recognition Configuration
In `afras_app/recognition/constants.py`:

```python
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

CONFIDENCE_LEVELS = {
    'HIGH': {'min': 80, 'label': 'High', 'color': (0, 255, 0)},
    'MEDIUM': {'min': 60, 'label': 'Medium', 'color': (0, 255, 255)},
    'LOW': {'min': 40, 'label': 'Low', 'color': (0, 165, 255)},
    'POOR': {'min': 0, 'label': 'Poor', 'color': (0, 0, 255)}
}
```

### Camera Setup
```python
# In attendance/views.py - Update camera source

# IP Camera (DroidCam, IP Webcam)
camera = cv2.VideoCapture('http://192.168.100.14:8080/video')

# Local Webcam
camera = cv2.VideoCapture(0)

# USB Camera
camera = cv2.VideoCapture(1)
```

### Database Configuration
```python
# settings.py

# SQLite (Default - Development)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# MySQL (Production)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'afras_db',
        'USER': 'afras_user',
        'PASSWORD': 'your_password',
        'HOST': 'localhost',
        'PORT': '3306',
    }
}
```

---

## 📖 Usage Guide

### 1. Admin Dashboard
1. Navigate to `/admin/`
2. Login with superuser credentials
3. Manage students, staff, and routines
4. View system analytics

### 2. Add Students
1. Go to Admin Panel → Students
2. Click "Add Student"
3. Fill in: Name, Roll Number, Department, Year, Semester, Section
4. Upload face image
5. Save

### 3. Start a Session
1. Navigate to Session Management
2. Click "Start New Session"
3. Fill session details:
   - Subject name
   - Department
   - Year, Semester, Section
   - Date & Time
   - Duration (minutes)
4. Click "Start Session"

### 4. Live Monitoring
1. Access `/attendance/live/{session_id}/`
2. Real-time video feed with face detection
3. See marked attendance in real-time
4. Automatic session end after duration

### 5. View Attendance Reports
1. Navigate to `/attendance/attendance-report/`
2. Filter by Year, Semester, Subject
3. Export as CSV
4. View individual student attendance patterns

### 6. Manual Override
1. Click on any status icon in the report
2. Change status to: Present, Absent, Leave, Late
3. Add reason for manual change
4. Save changes

### 7. Auto-Schedule from Routine
1. Go to Session Management
2. Upload PDF/Excel routine
3. Click "Extract & Schedule"
4. Sessions auto-generate for all days

---

## 📡 API Documentation

### Authentication
All API endpoints (except login) require authentication. Use Django's session authentication or JWT tokens.

### Session APIs

| Endpoint | Method | Description | Request Body |
|----------|--------|-------------|--------------|
| `/attendance/api/recent/` | GET | Get all sessions | - |
| `/attendance/api/stats/` | GET | Get session statistics | - |
| `/attendance/check-session/` | POST | Check duplicate session | `{subject, department, year, semester, section, session_datetime}` |
| `/attendance/delete-session/{id}/` | DELETE | Delete a session | - |
| `/attendance/sync-sessions/` | POST | Sync sessions from routines | - |

### Recognition APIs

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/attendance/hybrid-status/` | GET | Check model status |
| `/attendance/hybrid-video-feed/{session_id}/` | GET | Video streaming endpoint |
| `/attendance/get-logs/{session_id}/` | GET | Get attendance logs |

### Update APIs

| Endpoint | Method | Description | Request Body |
|----------|--------|-------------|--------------|
| `/attendance/api/update-attendance/` | POST | Manual attendance update | `{student_id, date, status, subject, reason}` |
| `/attendance/end-session/{session_id}/` | POST | End active session | - |

### API Response Examples

#### GET /attendance/api/recent/
```json
{
  "sessions": [
    {
      "id": 1,
      "subject": "Computer Architecture",
      "department": "Engineering",
      "year": 1,
      "semester": 2,
      "section": "A",
      "date": "2026-07-09",
      "start_time": "11:48 AM",
      "end_time": "11:53 AM",
      "time_range": "11:48 AM - 11:53 AM",
      "is_active": false,
      "duration": 5,
      "status": "Ended",
      "is_manual": true,
      "is_auto_scheduled": false
    }
  ],
  "total": 1,
  "message": "Showing manual sessions only"
}
```

#### POST /attendance/api/update-attendance/
**Request:**
```json
{
  "student_id": 42,
  "date": "2026-07-09",
  "status": "LEAVE",
  "subject": "Computer Architecture",
  "reason": "Approved leave"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Attendance updated to LEAVE for Amit Bist",
  "log_id": 42,
  "status": "LEAVE",
  "student": "Amit Bist",
  "date": "2026-07-09",
  "reason": "Approved leave"
}
```

---

## 🔧 Troubleshooting

### Common Issues and Solutions

| Issue | Solution |
|-------|----------|
| **Camera not detected** | Check `CAMERA_SOURCE` in settings. Try `0`, `1`, or IP camera URL |
| **Model not loading** | Run `python manage.py train_hybrid --verbose` to train the model |
| **Database errors** | Run `python manage.py migrate` to sync database |
| **Face not recognized** | Ensure good lighting and clear face image. Check student face quality |
| **Slow performance** | Reduce `RESIZE_FACTOR` or increase `FRAME_SKIP` in config |
| **High CPU usage** | Switch to HOG detection (`USE_FAST_DETECTION: True`) |
| **Session not starting** | Check date/time settings and ensure session is in future |
| **Attendance not marking** | Verify student is enrolled in correct section/semester |

### Debug Mode
Enable debug mode in settings:
```python
DEBUG = True
```
This will show detailed error pages and log information.

### Database Backup
```bash
# Backup database
cp db.sqlite3 db.sqlite3.backup

# Restore from backup
cp db.sqlite3.backup db.sqlite3
```

---

## 📸 Screenshots

*Screenshots coming soon*

---

## 🤝 Contributing

We welcome contributions! Please follow these steps:

### How to Contribute

1. **Fork** the repository
2. **Create** a feature branch:
   ```bash
   git checkout -b feature/amazing-feature
   ```
3. **Commit** changes:
   ```bash
   git commit -m 'Add amazing feature'
   ```
4. **Push** to branch:
   ```bash
   git push origin feature/amazing-feature
   ```
5. **Open** a Pull Request

### Coding Standards

| Language | Standard |
|----------|----------|
| **Python** | PEP 8 |
| **JavaScript** | ESLint |
| **HTML/CSS** | W3C Validator |

### Testing
```bash
# Run tests
python manage.py test

# Run with coverage
coverage run manage.py test
coverage report
```

### Reporting Issues
- Use the [GitHub Issues](https://github.com/lalit058/Automatic-Facial-Recognition-Based-Attendance-System-AFRAS-/issues) tracker
- Include steps to reproduce
- Describe expected vs actual behavior
- Add screenshots if applicable

---

## 👥 Team

| Name | Role | GitHub | LinkedIn |
|------|------|--------|----------|
| **Dammara Thagunna** | Lead Researcher | - | - |
| **Dhanesh Badal** | Frontend and Backend Developer | [@Dhaneshbadal] | (https://github.com/Dhaneshbadal) | [Profile] (https://www.linkedin.com/in/dhanesh-badal-6001a8286/)
| **Lalit Negi** | Frontend and Backend Developer | [@lalit058](https://github.com/lalit058) | [Profile](https://www.linkedin.com/in/lalit-negi-73571b338/) |
| **Manish Chataut** | CV Engineer | - | - |
| **Mukul Bhatt** | QA Engineer | - | - |

### Supervisor
**Department of Computer Engineering** | Far Western University, Nepal

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

```
MIT License

Copyright (c) 2026 AFRAS Team

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## 📊 Project Status

| Metric | Status |
|--------|--------|
| **Version** | v2.5.0 |
| **Release Date** | July 2026 |
| **Accuracy** | 86%+ |
| **FPS** | 15+ |
| **Platform** | Web-based |
| **Status** | ✅ Production Ready |

### Roadmap

| Phase | Feature | Status |
|-------|---------|--------|
| **Phase 1** | Core face recognition | ✅ Completed |
| **Phase 2** | Session management | ✅ Completed |
| **Phase 3** | Reporting dashboard | ✅ Completed |
| **Phase 4** | Auto-scheduling | ✅ Completed |
| **Phase 6** | Cloud deployment | 📋 Planned |

---

## 🙏 Acknowledgments

### Libraries & Frameworks
- **[Django](https://www.djangoproject.com/)** - The web framework for perfectionists with deadlines
- **[OpenCV](https://opencv.org/)** - Open source computer vision library
- **[face_recognition](https://github.com/ageitgey/face_recognition)** - The world's simplest facial recognition API
- **[scikit-learn](https://scikit-learn.org/)** - Machine learning library for Python
- **[Font Awesome](https://fontawesome.com/)** - Icon library
- **[Google Fonts](https://fonts.google.com/)** - Typography

### Research Papers
- Dalal, N., & Triggs, B. (2005). Histograms of oriented gradients for human detection.
- Zhang, K., et al. (2016). Joint face detection and alignment using multitask cascaded convolutional networks.
- Schroff, F., Kalenichenko, D., & Philbin, J. (2015). FaceNet: A unified embedding for face recognition and clustering.

### Special Thanks
- **Far Western University** - For providing the platform and resources
- **All Team Members** - For their dedication and hard work
- **Open Source Community** - For the incredible tools and libraries
- **GitHub** - For hosting the project

---

## 📞 Support

### Documentation
- [Project Wiki](https://github.com/lalit058/Automatic-Facial-Recognition-Based-Attendance-System-AFRAS-/wiki)
- [API Reference](https://github.com/lalit058/Automatic-Facial-Recognition-Based-Attendance-System-AFRAS-/wiki/API)
- [Installation Guide](https://github.com/lalit058/Automatic-Facial-Recognition-Based-Attendance-System-AFRAS-/wiki/Installation)

### Contact
- **Email:** 56.negilalit@gmail.com
- **GitHub Issues:** [Report Bug](https://github.com/lalit058/Automatic-Facial-Recognition-Based-Attendance-System-AFRAS-/issues)
- **GitHub Discussions:** [Ask Question](https://github.com/lalit058/Automatic-Facial-Recognition-Based-Attendance-System-AFRAS-/discussions)

---

## 🌟 Show Your Support

If you found this project helpful, please consider:

- ⭐ **Starring** the repository
- 🍴 **Forking** the project
- 📢 **Sharing** with others
- 🐛 **Reporting** issues
- 💡 **Suggesting** features

[![Star on GitHub](https://img.shields.io/github/stars/lalit058/Automatic-Facial-Recognition-Based-Attendance-System-AFRAS-.svg?style=social)](https://github.com/lalit058/Automatic-Facial-Recognition-Based-Attendance-System-AFRAS-/stargazers)
[![Fork on GitHub](https://img.shields.io/github/forks/lalit058/Automatic-Facial-Recognition-Based-Attendance-System-AFRAS-.svg?style=social)](https://github.com/lalit058/Automatic-Facial-Recognition-Based-Attendance-System-AFRAS-/network)

---

## 📝 Changelog

### v2.5.0 (July 2026)
- ✅ Added hybrid face recognition with ensemble voting
- ✅ Implemented single-shot detection mode
- ✅ Added quality validation (blur, brightness, size)
- ✅ Built responsive dashboard
- ✅ Integrated auto-scheduling
- ✅ Added CSV export
- ✅ Manual attendance override

### v2.0.0 (June 2026)
- ✅ Basic face recognition
- ✅ Session management
- ✅ Real-time monitoring
- ✅ Attendance reports

### v1.0.0 (May 2026)
- ✅ Initial release
- ✅ Student management
- ✅ Basic attendance marking

---

**Made with ❤️ by the AFRAS Team | Far Western University, Nepal**

---

<div align="center">
  <sub>Built with ❤️ by the AFRAS Team</sub>
  <br>
  <sub>© 2026 AFRAS - Automatic Facial Recognition Attendance System</sub>
</div>
