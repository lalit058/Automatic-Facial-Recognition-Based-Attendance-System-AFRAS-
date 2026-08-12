FROM python:3.10-slim-bullseye

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=10000 \
    CMAKE_BUILD_PARALLEL_LEVEL=1 \
    CFLAGS="-O1" \
    CXXFLAGS="-O1"

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    libopenblas-dev \
    liblapack-dev \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install dlib individually under single-threaded compilation
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir dlib==19.24.6

# Install face-recognition and project requirements
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --no-deps face-recognition==1.3.0 && \
    pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . /app/

# Collect static files
WORKDIR /app/afras_app
RUN python manage.py collectstatic --noinput

# Expose Render port & start Gunicorn
EXPOSE 10000
CMD ["gunicorn", "afras_backend.wsgi:application", "--bind", "0.0.0.0:10000"]