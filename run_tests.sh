#!/bin/bash

# Test runner script for perp-dex backend

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_color() {
    color=$1
    message=$2
    echo -e "${color}${message}${NC}"
}

# Check if virtual environment is activated
if [[ "$VIRTUAL_ENV" == "" ]]; then
    print_color "$YELLOW" "Virtual environment not activated. Activating..."
    source venv/bin/activate
fi

# Install test dependencies if needed
print_color "$GREEN" "Installing test dependencies..."
pip install -q pytest pytest-asyncio pytest-cov pytest-mock aiosqlite

# Create test database if needed
export TEST_DATABASE_URL="sqlite+aiosqlite:///:memory:"
export ENVIRONMENT="test"

# Run different test suites based on argument
case "$1" in
    unit)
        print_color "$GREEN" "Running unit tests..."
        pytest tests/unit -v -m unit
        ;;
    integration)
        print_color "$GREEN" "Running integration tests..."
        pytest tests/integration -v -m integration
        ;;
    coverage)
        print_color "$GREEN" "Running all tests with coverage..."
        pytest tests/ --cov=services --cov=connectors --cov=app --cov-report=html --cov-report=term
        print_color "$YELLOW" "Coverage report generated in htmlcov/index.html"
        ;;
    fast)
        print_color "$GREEN" "Running fast tests (excluding slow tests)..."
        pytest tests/ -v -m "not slow"
        ;;
    specific)
        if [ -z "$2" ]; then
            print_color "$RED" "Please specify a test file or directory"
            exit 1
        fi
        print_color "$GREEN" "Running specific tests: $2"
        pytest "$2" -v
        ;;
    watch)
        print_color "$GREEN" "Running tests in watch mode..."
        pytest-watch tests/ -v
        ;;
    debug)
        print_color "$GREEN" "Running tests with debug output..."
        pytest tests/ -vvs --tb=long --log-cli-level=DEBUG
        ;;
    lint)
        print_color "$GREEN" "Running linting checks..."
        python -m flake8 services/ app/ connectors/ --max-line-length=120
        python -m mypy services/ app/ connectors/ --ignore-missing-imports
        ;;
    all)
        print_color "$GREEN" "Running all tests..."
        pytest tests/ -v
        ;;
    *)
        print_color "$YELLOW" "Usage: $0 {unit|integration|coverage|fast|specific <path>|watch|debug|lint|all}"
        echo ""
        echo "Options:"
        echo "  unit         - Run unit tests only"
        echo "  integration  - Run integration tests only"
        echo "  coverage     - Run all tests with coverage report"
        echo "  fast         - Run all tests except slow ones"
        echo "  specific     - Run specific test file or directory"
        echo "  watch        - Run tests in watch mode (requires pytest-watch)"
        echo "  debug        - Run tests with debug output"
        echo "  lint         - Run linting checks"
        echo "  all          - Run all tests"
        exit 1
        ;;
esac

# Check exit code
if [ $? -eq 0 ]; then
    print_color "$GREEN" "✓ Tests passed successfully!"
else
    print_color "$RED" "✗ Tests failed!"
    exit 1
fi