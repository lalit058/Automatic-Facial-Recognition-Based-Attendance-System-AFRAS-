FROM python:3.10-slim-bullseye

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=10000 \
    CMAKE_BUILD_PARALLEL_LEVEL=1 \
    CFLAGS="-O1" \
    CXXFLAGS="-O1"

WORKDIR /app

# 1. Install build tools, cmake, git, and system libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    git \
    libopenblas-dev \
    liblapack-dev \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 2. Pin setuptools < 70
RUN pip install --no-cache-dir "setuptools<70.0.0" wheel

# 3. Build dlib single-threaded
RUN pip install --no-cache-dir dlib==19.24.6

# 4. Install face_recognition and models
RUN pip install --no-cache-dir git+https://github.com/ageitgey/face_recognition_models && \
    pip install --no-cache-dir --no-deps face-recognition==1.3.0

# 5. Install remaining requirements
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# 6. Copy project files
COPY . /app/

# 7. Collect static files
WORKDIR /app/afras_app
RUN python -c "import django, os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'afras_backend.settings'); django.setup(); from django.contrib.staticfiles.finders import get_finders; [print(f.__class__.__name__, ':', list(f.list(None))) for f in get_finders()]"
RUN python manage.py collectstatic --noinput

# 8. Expose port, run migrations, create superuser, and start Gunicorn
EXPOSE 10000
CMD ["sh", "-c", "python manage.py migrate --noinput && python create_superuser.py && gunicorn afras_backend.wsgi:application --bind 0.0.0.0:10000 --workers 2 --timeout 120"]