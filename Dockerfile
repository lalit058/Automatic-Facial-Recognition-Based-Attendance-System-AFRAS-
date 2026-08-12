FROM python:3.10-slim-bullseye

# Prevent Python from writing .pyc and buffering stdout
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=10000

WORKDIR /app

# 1. Install Debian system packages including pre-compiled dlib
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-dlib \
    libgl1 \
    libglib2.0-0 \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 2. Copy pre-built Debian dlib into Python 3.10 site-packages
RUN cp -r /usr/lib/python3/dist-packages/dlib* /usr/local/lib/python3.10/site-packages/

# 3. Install dependencies and face-recognition without triggering dlib rebuild
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir --no-deps face-recognition==1.3.0 && \
    pip install --no-cache-dir -r requirements.txt

# 4. Copy project files
COPY . /app/

# 5. Collect static files
WORKDIR /app/afras_app
RUN python manage.py collectstatic --noinput

# 6. Expose port & start Gunicorn
EXPOSE 10000
CMD ["gunicorn", "afras_backend.wsgi:application", "--bind", "0.0.0.0:10000"]