#!/usr/bin/env python
"""
Supabase Migration Script
Migrates Django project from SQLite to Supabase PostgreSQL

Usage:
    python migrate_to_supabase.py
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path
from datetime import datetime

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

import django
django.setup()

from django.core.management import call_command
from django.db import connection


class SupabaseMigrator:
    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.env_file = self.base_dir / '.env'
        self.sqlite_db = self.base_dir / 'db.sqlite3'
        self.backup_dir = self.base_dir / 'backups'
        self.backup_dir.mkdir(exist_ok=True)
        
    def print_header(self, text):
        print("\n" + "=" * 50)
        print(text)
        print("=" * 50 + "\n")
    
    def print_step(self, step_num, text):
        print(f"Step {step_num}: {text}...")
    
    def print_success(self, text):
        print(f"✅ {text}")
    
    def print_error(self, text):
        print(f"❌ {text}")
    
    def print_info(self, text):
        print(f"ℹ️  {text}")
    
    def check_env(self):
        """Check if .env file exists and has DATABASE_URL"""
        self.print_step(0, "Checking environment")
        
        if not self.env_file.exists():
            self.print_error(".env file not found")
            sys.exit(1)
        
        with open(self.env_file, 'r') as f:
            content = f.read()
            if 'DATABASE_URL' not in content:
                self.print_error("DATABASE_URL not found in .env")
                sys.exit(1)
        
        self.print_success(".env file configured")
    
    def backup_sqlite(self):
        """Backup existing SQLite database and data"""
        self.print_step(1, "Backing up SQLite data")
        
        if not self.sqlite_db.exists():
            self.print_info("No existing SQLite database found (fresh start)")
            return
        
        # Backup database file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_db = self.backup_dir / f'db.sqlite3.{timestamp}.backup'
        shutil.copy2(self.sqlite_db, backup_db)
        self.print_success(f"Database backed up: {backup_db}")
        
        # Export data
        backup_json = self.backup_dir / f'data.{timestamp}.json'
        try:
            with open(backup_json, 'w') as f:
                call_command('dumpdata', stdout=f)
            self.print_success(f"Data exported: {backup_json}")
            return backup_json
        except Exception as e:
            self.print_error(f"Failed to export data: {e}")
            return None
    
    def create_migrations(self):
        """Create Django migrations"""
        self.print_step(2, "Creating migrations")
        
        try:
            call_command('makemigrations')
            self.print_success("Migrations created")
        except Exception as e:
            self.print_error(f"Failed to create migrations: {e}")
            sys.exit(1)
    
    def apply_migrations(self):
        """Apply migrations to Supabase"""
        self.print_step(3, "Applying migrations to Supabase")
        
        try:
            call_command('migrate')
            self.print_success("Migrations applied to Supabase")
        except Exception as e:
            self.print_error(f"Failed to apply migrations: {e}")
            sys.exit(1)
    
    def load_data(self, backup_json):
        """Load backed up data into Supabase"""
        if not backup_json or not backup_json.exists():
            self.print_info("No data to load")
            return
        
        self.print_step(4, "Loading data into Supabase")
        
        try:
            call_command('loaddata', str(backup_json))
            self.print_success("Data loaded into Supabase")
        except Exception as e:
            self.print_error(f"Failed to load data: {e}")
            self.print_info("You can manually load data later with:")
            print(f"  python manage.py loaddata {backup_json}")
    
    def verify_connection(self):
        """Verify connection to Supabase"""
        self.print_step(5, "Verifying Supabase connection")
        
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT version();")
                version = cursor.fetchone()
                self.print_success(f"Connected to: {version[0]}")
        except Exception as e:
            self.print_error(f"Connection failed: {e}")
            sys.exit(1)
    
    def verify_tables(self):
        """Verify tables were created"""
        self.print_step(6, "Verifying tables")
        
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                    ORDER BY table_name;
                """)
                tables = cursor.fetchall()
                
                if tables:
                    self.print_success(f"Found {len(tables)} tables:")
                    for table in tables:
                        print(f"  - {table[0]}")
                else:
                    self.print_error("No tables found")
        except Exception as e:
            self.print_error(f"Failed to verify tables: {e}")
    
    def run(self):
        """Run the complete migration"""
        self.print_header("SQLite to Supabase Migration")
        
        self.check_env()
        backup_json = self.backup_sqlite()
        self.create_migrations()
        self.apply_migrations()
        self.load_data(backup_json)
        self.verify_connection()
        self.verify_tables()
        
        self.print_header("✅ Migration Complete!")
        
        print("Next steps:")
        print("1. Create superuser: python manage.py createsuperuser")
        print("2. Test your application")
        print("3. Verify tables in Supabase dashboard")
        print("")
        print("To switch back to SQLite for development:")
        print("  - Update DATABASE_URL in .env to: sqlite:///db.sqlite3")
        print("  - Run: python manage.py migrate")
        print("")
        print(f"Backups saved to: {self.backup_dir}")


if __name__ == '__main__':
    migrator = SupabaseMigrator()
    migrator.run()
