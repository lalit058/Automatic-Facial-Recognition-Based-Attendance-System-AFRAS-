#!/usr/bin/env bash
set -o errexit

echo "🚀 Starting build..."
echo "📌 Python version: $(python --version)"

# Install dlib-bin (pre-compiled)
echo "📦 Installing dlib-bin..."
pip install dlib-bin

# Install face-recognition-models
echo "📦 Installing face-recognition-models..."
pip install face-recognition-models

# Install face-recognition WITHOUT dependencies
echo "📦 Installing face-recognition..."
pip install face-recognition --no-deps

# Navigate to app directory
cd afras_app || exit 1

# Install requirements
echo "📦 Installing requirements..."
pip install --no-cache-dir -r requirements.txt

# Run Django commands
echo "📁 Collecting static files..."
python manage.py collectstatic --no-input

echo "🗄️ Applying migrations..."
python manage.py migrate --noinput

cd ..

echo "✅ Build completed successfully!"