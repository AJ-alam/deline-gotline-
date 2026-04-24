#!/usr/bin/env python
"""
Test Supabase connection directly with psycopg2
This bypasses Django and tests the raw database connection
"""

import psycopg2
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Get DATABASE_URL
DATABASE_URL = os.getenv("DATABASE_URL")

print("=" * 60)
print("Testing Supabase Connection")
print("=" * 60)
print()

if not DATABASE_URL:
    print("❌ ERROR: DATABASE_URL not found in .env")
    exit(1)

print(f"Connection String: {DATABASE_URL[:50]}...")
print()

try:
    print("Attempting to connect to Supabase...")
    connection = psycopg2.connect(DATABASE_URL)
    
    print("✅ Connection successful!")
    print()
    
    # Get connection info
    cursor = connection.cursor()
    
    # Test 1: Get PostgreSQL version
    cursor.execute("SELECT version();")
    version = cursor.fetchone()
    print(f"✅ PostgreSQL Version: {version[0]}")
    print()
    
    # Test 2: List tables
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public'
        ORDER BY table_name;
    """)
    tables = cursor.fetchall()
    print(f"✅ Tables in database: {len(tables)}")
    for table in tables[:10]:
        print(f"   - {table[0]}")
    if len(tables) > 10:
        print(f"   ... and {len(tables) - 10} more")
    print()
    
    # Test 3: Check if migrations table exists
    cursor.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_name = 'django_migrations'
        );
    """)
    has_migrations = cursor.fetchone()[0]
    print(f"✅ Django migrations table exists: {has_migrations}")
    print()
    
    cursor.close()
    connection.close()
    
    print("=" * 60)
    print("✅ ALL TESTS PASSED!")
    print("=" * 60)
    print()
    print("You can now run Django migrations:")
    print("  python manage.py migrate")
    
except psycopg2.OperationalError as e:
    print(f"❌ Connection Error: {e}")
    print()
    print("Troubleshooting:")
    print("1. Check if Supabase project is active (not paused)")
    print("2. Verify DATABASE_URL in .env is correct")
    print("3. Check internet connection: ping 8.8.8.8")
    print("4. Try flushing DNS: ipconfig /flushdns")
    exit(1)
    
except Exception as e:
    print(f"❌ Unexpected Error: {e}")
    exit(1)
