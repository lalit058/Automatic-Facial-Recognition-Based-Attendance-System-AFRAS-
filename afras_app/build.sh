#!/usr/bin/env bash
# exit on error
set -o errexit

# Limit C++ parallel compilation jobs to 1 to prevent RAM spikes (dlib / cmake)
export CMAKE_BUILD_PARALLEL_LEVEL=1
export MAX_JOBS=1

# Install requirements without caching in RAM
pip install --upgrade pip
pip install --no-cache-dir -r requirements.txt

python manage.py collectstatic --no-input
python manage.py migrate