#!/usr/bin/env bash
set -o errexit

# Install packages preferring wheels (prevents dlib compilation memory spike)
pip install --no-cache-dir --prefer-binary -r requirements.txt

python manage.py collectstatic --no-input
python manage.py migrate