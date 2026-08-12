FROM python:3.10-slim-bullseye

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=10000 \
    CMAKE_BUILD_PARALLEL_LEVEL=1 \
    CFLAGS="-O1" \
    CXXFLAGS="-O1"

WORKDIR /app

# 1. Install build tools, cmake, git, and graphics libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    git \
    libopenblas-dev \
    liblapack-dev \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 2. Build dlib single-threaded
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir dlib==19.24.6

# 3. Install the official model weights from git and face-recognition
RUN pip install --no-cache-dir git+https://github.com/ageitgey/face_recognition_models && \
    pip install --no-cache-dir --no-deps face-recognition==1.3.0

# 4. Install remaining requirements
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy project files
COPY . /app/

# 6. Collect static files
WORKDIR /app/afras_app
RUN python manage.py collectstatic --noinput

# 7. Expose port & start Gunicorn
EXPOSE 10000
CMD ["gunicorn", "afras_backend.wsgi:application", "--bind", "0.0.0.0:10000", "--timeout", "120"]