#!/bin/bash
set -e

echo "Setting up workspace for Perp DEX Trading Aggregator..."

# Check for Python 3
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed. Please install Python 3.8+ to continue."
    exit 1
fi

# Check for pip
if ! command -v pip3 &> /dev/null; then
    echo "Error: pip3 is not installed. Please install pip3 to continue."
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "Installing dependencies..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
else
    echo "Warning: requirements.txt not found"
fi

# Install development dependencies if they exist
if [ -f "requirements-dev.txt" ]; then
    echo "Installing development dependencies..."
    pip install -r requirements-dev.txt
fi

# Copy environment file if it doesn't exist and example exists
if [ ! -f ".env" ]; then
    if [ -f "$CONDUCTOR_ROOT_PATH/.env.example" ]; then
        echo "Creating .env file from example..."
        cp "$CONDUCTOR_ROOT_PATH/.env.example" .env
        echo "Please update .env with your configuration"
    elif [ -f ".env.example" ]; then
        echo "Creating .env file from example..."
        cp .env.example .env
        echo "Please update .env with your configuration"
    else
        echo "Warning: No .env.example file found"
    fi
fi

# Check for database services
echo "Checking database dependencies..."
if command -v psql &> /dev/null; then
    echo "✓ PostgreSQL client found"
else
    echo "⚠️  PostgreSQL client not found - database features may not work"
fi

if command -v redis-cli &> /dev/null; then
    echo "✓ Redis client found"
else
    echo "⚠️  Redis client not found - caching features may not work"
fi

echo ""
echo "✅ Workspace setup complete!"
echo ""
echo "Next steps:"
echo "1. Activate the virtual environment: source venv/bin/activate"
echo "2. Update your .env file with API keys and configuration"
echo "3. Initialize the database: make db-init"
echo "4. Run the application: make dev"