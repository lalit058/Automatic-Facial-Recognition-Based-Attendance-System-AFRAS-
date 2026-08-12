#!/usr/bin/env bash
set -o errexit

echo "🚀 Starting build..."
echo "📌 Python version: $(python --version)"

cd afras_app || exit 1

pip install --upgrade pip

# Install all packages with memory optimization
echo "📦 Installing all packages..."
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
    whitenoise==6.12.0 \
    pillow==12.1.0 \
    opencv-python-headless==4.12.0.88 \
    numpy==2.2.6 \
    scipy==1.13.0 \
    scikit-learn==1.5.2 \
    pandas==2.2.3 \
    pymysql==1.2.0 \
    psutil==7.2.2 \
    python-dotenv==1.0.0 \
    pdfplumber==0.11.9 \
    dlib-bin==20.0.1 \
    face-recognition==1.3.0 \
    face-recognition-models==0.3.0

python manage.py collectstatic --no-input
python manage.py migrate --noinput

cd ..

echo "✅ Build completed successfully!"