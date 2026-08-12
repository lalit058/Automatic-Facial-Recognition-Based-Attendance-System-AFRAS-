set -o errexit

echo "🚀 Starting build..."

# Navigate to the app directory
cd afras_app || exit 1

# Upgrade pip
pip install --upgrade pip

# Install dlib-bin (pre-compiled)
echo "📦 Installing dlib-bin..."
pip install dlib-bin

# Install face-recognition-models
echo "📦 Installing face-recognition-models..."
pip install face-recognition-models

# Install face-recognition
echo "📦 Installing face-recognition..."
pip install face-recognition

# Install remaining requirements
echo "📦 Installing requirements..."
pip install --no-cache-dir -r requirements.txt

# Run Django management commands
echo "📁 Collecting static files..."
python manage.py collectstatic --no-input

echo "🗄️ Applying migrations..."
python manage.py migrate --noinput

# Go back to root
cd ..

echo "✅ Build completed successfully!"