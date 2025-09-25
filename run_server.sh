#!/bin/bash

# Perp DEX Trading Backend - Server Startup Script

echo "🚀 Starting Perp DEX Trading Backend..."

# Activate virtual environment
source venv/bin/activate

# Clear any existing DATABASE_URL from shell environment
unset DATABASE_URL

# Set encryption key (uses .env file if available)
export ENCRYPTION_KEY="${ENCRYPTION_KEY:-your-32-byte-encryption-key-here}"

# Run the server
echo "📡 Server starting on http://localhost:8000"
echo "📖 API Docs: http://localhost:8000/docs"
echo "📋 ReDoc: http://localhost:8000/redoc"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Run with reload for development
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000