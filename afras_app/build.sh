#!/usr/bin/env bash
set -o errexit

echo "🚀 Starting build..."
echo "📌 Python version: $(python --version)"

pip install --upgrade pip

# 1. Install pre-compiled dlib wheel directly to skip compiling
pip install https://github.com/z-a-f/dlib-wheels/releases/download/v19.24.2/dlib-19.24.2-cp310-cp310-linux_x86_64.whl

# 2. Install the remaining requirements
cd afras_app || exit 1

pip install --no-cache-dir \
    asgiref==3.11.0 \
    click==8.3.1 \
    colorama==0.4.6 \
    Django==5.2.10 \
    sqlparse==0.5.5 \
    typing_extensions==4.15.0 \
    tzdata==2025.3 \
    dj-database-url==3.1.2 \
    psycopg2-binary==2.9.12 \
    gunicorn==26.0.0 \
    whitenoise==6.12.0 \
    pillow==12.1.0 \
    opencv-python-headless==4.12.0.88 \
    numpy<2.0.0 \
    pymysql==1.2.0 \
    psutil==7.2.2 \
    python-dotenv==1.0.0 \
    pdfplumber==0.11.9 \
    face-recognition==1.3.0 \
    face-recognition-models==0.3.0

python manage.py collectstatic --no-input
python manage.py migrate --noinput

cd ..

echo "✅ Build completed successfully!"