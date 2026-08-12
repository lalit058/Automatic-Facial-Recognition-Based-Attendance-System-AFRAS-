set -o errexit

echo "🚀 Starting build..."

# Navigate to app directory
cd afras_app || exit 1

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install cmake (required for dlib)
echo "Installing cmake..."
pip install cmake

# Install dlib with pre-compiled binary
echo "Installing dlib..."
pip install dlib-bin

# Install face_recognition dependencies
echo "Installing face_recognition..."
pip install face-recognition-models
pip install face-recognition --no-deps

# Install remaining requirements
echo "Installing requirements..."
pip install --no-cache-dir -r requirements.txt

# Run Django commands
echo "Collecting static files..."
python manage.py collectstatic --no-input

echo "Applying migrations..."
python manage.py migrate --noinput

cd ..

echo "✅ Build completed!"