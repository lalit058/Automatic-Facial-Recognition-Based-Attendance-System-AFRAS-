#!/usr/bin/env bash
set -o errexit

echo "🚀 Starting build..."

# Navigate to the app directory
cd afras_app || exit 1

pip install --upgrade pip

# Install dlib-bin (pre-compiled binary, no cmake needed)
pip install dlib-bin

# Install face-recognition-models (required for face_recognition)
pip install face-recognition-models

# Install face-recognition without dependencies (deps handled by requirements)
pip install face-recognition --no-deps

# Install remaining requirements
pip install --no-cache-dir -r requirements.txt

# Run Django management commands
python manage.py collectstatic --no-input
python manage.py migrate

# Go back to root
cd ..

echo "✅ Build completed successfully!"