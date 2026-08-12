set -o errexit

# Navigate to the app directory
cd afras_app || exit 1

pip install --upgrade pip

# Install pre-compiled binary wheel for dlib (bypasses C++ compilation & RAM spike)
pip install dlib-bin
pip install face-recognition-models
pip install face-recognition --no-deps

# Install remaining requirements from requirements.txt
pip install --no-cache-dir -r requirements.txt

# Run Django management commands
python manage.py collectstatic --no-input
python manage.py migrate

# Go back to root
cd ..

echo "✅ Build completed successfully!"