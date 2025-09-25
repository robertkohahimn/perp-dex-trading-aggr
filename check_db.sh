#!/bin/bash

# Database check script

echo "🔍 Checking PostgreSQL and database..."
echo ""

# Check if PostgreSQL is running
if pg_ctl status > /dev/null 2>&1; then
    echo "✅ PostgreSQL is running"
else
    echo "❌ PostgreSQL is not running"
    echo "   Start it with: brew services start postgresql"
    exit 1
fi

# Check if database exists and show tables
echo ""
echo "📊 Database tables:"
psql -U perp_user -d perp_dex_db -c "\dt" 2>&1 | grep -E "(public|rows)" || echo "❌ Cannot connect to database"

echo ""
echo "To connect to the database manually:"
echo "  psql -U perp_user -d perp_dex_db"
echo ""
echo "Password: perp_password123"