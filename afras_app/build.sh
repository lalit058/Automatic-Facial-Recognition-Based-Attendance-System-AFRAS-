#!/usr/bin/env bash
set -o errexit

echo "🚀 Starting build..."
echo "📌 Python version: $(python --version)"

cd afras_app || exit 1

pip install --upgrade pip

# ============================================
# Install packages in batches to avoid memory spikes
# ============================================

# 1. Core Django (lightweight)
echo "📦 Installing Django core..."
pip install --no-cache-dir \
    asgiref==3.11.0 \
    click==8.3.1 \
    colorama==0.4.6 \
    Django==5.2.10 \
    django-browser-reload==1.21.0 \
    sqlparse==0.5.5 \
    typing_extensions==4.15.0 \
    tzdata==2025.3 \
    dj-database-url==3.1.2 \
    psycopg2-binary==2.9.12 \
    gunicorn==26.0.0 \
    whitenoise==6.12.0

# 2. Image Processing (medium)
echo "📦 Installing image processing..."
pip install --no-cache-dir \
    pillow==12.1.0 \
    opencv-python-headless==4.12.0.88

# 3. Install numpy first (it has wheels)
echo "📦 Installing numpy..."
pip install --no-cache-dir --only-binary :all: numpy==2.2.6

# 4. Install scipy (TRY with pre-built wheels only)
echo "📦 Installing scipy..."
pip install --no-cache-dir --only-binary :all: scipy==1.13.0 || \
    pip install --no-cache-dir scipy==1.11.4

# 5. Install scikit-learn (TRY with pre-built wheels only)
echo "📦 Installing scikit-learn..."
pip install --no-cache-dir --only-binary :all: scikit-learn==1.5.2 || \
    pip install --no-cache-dir scikit-learn==1.4.2

# 6. Install pandas (TRY with pre-built wheels only)
echo "📦 Installing pandas..."
pip install --no-cache-dir --only-binary :all: pandas==2.2.3 || \
    pip install --no-cache-dir pandas==2.1.4

# 7. Remaining packages
echo "📦 Installing remaining packages..."
pip install --no-cache-dir \
    pymysql==1.2.0 \
    psutil==7.2.2 \
    python-dotenv==1.0.0 \
    pdfplumber==0.11.9 \
    dlib-bin==20.0.1 \
    face-recognition==1.3.0 \
    face-recognition-models==0.3.0

# Run Django commands
echo "📁 Collecting static files..."
python manage.py collectstatic --no-input

echo "🗄️ Applying migrations..."
python manage.py migrate --noinput

cd ..

echo "✅ Build completed successfully!"