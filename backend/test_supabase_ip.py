#!/usr/bin/env python
"""
Test Supabase connection using IP address instead of hostname
"""

import psycopg2
from dotenv import load_dotenv
import os
import socket

# Load environment variables
load_dotenv()

print("=" * 60)
print("Testing Supabase Connection (IP Method)")
print("=" * 60)
print()

# Get hostname from .env
DATABASE_URL = os.getenv("DATABASE_URL")
hostname = "db.whxqwxwznrsqahsjrfih.supabase.co"

print(f"Hostname: {hostname}")

# Resolve hostname to IP
try:
    print("Resolving hostname to IP...")
    ip_address = socket.gethostbyname(hostname)
    print(f"✅ Resolved to IP: {ip_address}")
except socket.gaierror as e:
    print(f"❌ Failed to resolve: {e}")
    print()
    print("Trying IPv6...")
    try:
        ip_address = socket.getaddrinfo(hostname, 5432, socket.AF_INET6)[0][4][0]
        print(f"✅ Resolved to IPv6: {ip_address}")
    except Exception as e2:
        print(f"❌ IPv6 also failed: {e2}")
        exit(1)

print()

# Create connection string with IP
connection_string = DATABASE_URL.replace(hostname, ip_address)
print(f"Connection String (with IP): {connection_string[:60]}...")
print()

try:
    print("Attempting to connect to Supabase...")
    connection = psycopg2.connect(connection_string)
    
    print("✅ Connection successful!")
    print()
    
    # Get connection info
    cursor = connection.cursor()
    
    # Test 1: Get PostgreSQL version
    cursor.execute("SELECT version();")
    version = cursor.fetchone()
    print(f"✅ PostgreSQL Version: {version[0][:50]}...")
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
    print()
    
    cursor.close()
    connection.close()
    
    print("=" * 60)
    print("✅ CONNECTION WORKS WITH IP ADDRESS!")
    print("=" * 60)
    print()
    print("Solution: Update DATABASE_URL to use IP instead of hostname")
    print(f"DATABASE_URL=postgresql://postgres:%23Dgg123456%3B%27%2743%27%23@{ip_address}:5432/postgres?sslmode=require")
    
except psycopg2.OperationalError as e:
    print(f"❌ Connection Error: {e}")
    exit(1)
    
except Exception as e:
    print(f"❌ Unexpected Error: {e}")
    exit(1)
