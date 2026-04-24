#!/bin/bash

# Supabase Migration Script
# This script helps migrate from SQLite to Supabase PostgreSQL

set -e

echo "================================"
echo "SQLite to Supabase Migration"
echo "================================"
echo ""

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "❌ Error: .env file not found"
    echo "Please create .env file with Supabase credentials"
    exit 1
fi

# Check if DATABASE_URL is set
if ! grep -q "DATABASE_URL" .env; then
    echo "❌ Error: DATABASE_URL not found in .env"
    exit 1
fi

echo "✅ .env file found"
echo ""

# Step 1: Backup existing data
echo "Step 1: Backing up existing SQLite data..."
if [ -f "db.sqlite3" ]; then
    cp db.sqlite3 db.sqlite3.backup
    echo "✅ Backup created: db.sqlite3.backup"
    
    # Export data
    python manage.py dumpdata > data_backup.json
    echo "✅ Data exported: data_backup.json"
else
    echo "ℹ️  No existing SQLite database found (fresh start)"
fi
echo ""

# Step 2: Create migrations
echo "Step 2: Creating migrations..."
python manage.py makemigrations
echo "✅ Migrations created"
echo ""

# Step 3: Apply migrations to Supabase
echo "Step 3: Applying migrations to Supabase..."
python manage.py migrate
echo "✅ Migrations applied to Supabase"
echo ""

# Step 4: Load data if it exists
if [ -f "data_backup.json" ]; then
    echo "Step 4: Loading data into Supabase..."
    python manage.py loaddata data_backup.json
    echo "✅ Data loaded into Supabase"
    echo ""
fi

# Step 5: Verify connection
echo "Step 5: Verifying connection..."
python manage.py shell << EOF
from django.db import connection
try:
    with connection.cursor() as cursor:
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        print(f"✅ Connected to: {version[0]}")
except Exception as e:
    print(f"❌ Connection failed: {e}")
    exit(1)
EOF
echo ""

echo "================================"
echo "✅ Migration Complete!"
echo "================================"
echo ""
echo "Next steps:"
echo "1. Create superuser: python manage.py createsuperuser"
echo "2. Test your application"
echo "3. Verify tables in Supabase dashboard"
echo ""
echo "To switch back to SQLite for development:"
echo "  - Update DATABASE_URL in .env to: sqlite:///db.sqlite3"
echo "  - Run: python manage.py migrate"
