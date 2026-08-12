FROM python:3.10-slim-bullseye

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=10000

WORKDIR /app

# Install system dependencies & pre-compiled dlib/cmake tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    libopenblas-dev \
    liblapack-dev \
    libx11-dev \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies with single-threaded compile limit
ENV CMAKE_BUILD_PARALLEL_LEVEL=1

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir https://github.com/z-a-f/dlib-wheels/releases/download/v19.24.2/dlib-19.24.2-cp310-cp310-linux_x86_64.whl && \
    pip install --no-cache-dir --no-deps face-recognition==1.3.0 && \
    pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . /app/

# Run static collection inside the subfolder
WORKDIR /app/afras_app
RUN python manage.py collectstatic --noinput

# Expose Render port
EXPOSE 10000

# Start Gunicorn
CMD ["gunicorn", "afras_backend.wsgi:application", "--bind", "0.0.0.0:10000"]