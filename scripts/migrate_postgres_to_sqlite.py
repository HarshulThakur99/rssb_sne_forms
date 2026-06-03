#!/usr/bin/env python3
"""
PostgreSQL to SQLite Migration Script
Migrates all data from RDS PostgreSQL to local SQLite database

Usage:
    python scripts/migrate_postgres_to_sqlite.py

Requirements:
    - PostgreSQL credentials in environment or .env file
    - Sufficient disk space for SQLite database
    - Write permissions in app directory
"""

import os
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import models
from app.models import db, SNEForm, BloodCampDonor, Attendant

def get_postgres_uri():
    """Get PostgreSQL connection URI from environment"""
    db_host = os.environ.get('DB_HOST')
    db_port = os.environ.get('DB_PORT', '5432')
    db_name = os.environ.get('DB_NAME')
    db_user = os.environ.get('DB_USER')
    db_password = os.environ.get('DB_PASSWORD')
    
    if not all([db_host, db_name, db_user, db_password]):
        print("ERROR: Missing required PostgreSQL environment variables!")
        print("Required: DB_HOST, DB_NAME, DB_USER, DB_PASSWORD")
        sys.exit(1)
    
    return f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

def get_sqlite_uri():
    """Get SQLite database path"""
    sqlite_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance', 'rssbsne.db')
    os.makedirs(os.path.dirname(sqlite_path), exist_ok=True)
    return f"sqlite:///{sqlite_path}"

def create_backup(postgres_engine):
    """Create a SQL dump backup of PostgreSQL database"""
    print("\n📦 Creating PostgreSQL backup...")
    backup_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'backups')
    os.makedirs(backup_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = os.path.join(backup_dir, f'postgres_backup_{timestamp}.sql')
    
    # Get connection details
    db_host = os.environ.get('DB_HOST')
    db_name = os.environ.get('DB_NAME')
    db_user = os.environ.get('DB_USER')
    
    print(f"Backup will be saved to: {backup_file}")
    print(f"\nTo create backup, run this command on your local machine or EC2:")
    print(f"pg_dump -h {db_host} -U {db_user} -d {db_name} -F p -f {backup_file}")
    print("\nPress Enter to continue with migration (or Ctrl+C to exit and create backup first)...")
    input()
    
    return backup_file

def migrate_data(postgres_engine, sqlite_engine):
    """Migrate all data from PostgreSQL to SQLite"""
    
    # Create sessions
    PostgresSession = sessionmaker(bind=postgres_engine)
    SQLiteSession = sessionmaker(bind=sqlite_engine)
    
    pg_session = PostgresSession()
    sqlite_session = SQLiteSession()
    
    models_to_migrate = [
        (SNEForm, 'SNE Forms'),
        (BloodCampDonor, 'Blood Camp Donors'),
        (Attendant, 'Attendants'),
    ]
    
    migration_summary = {}
    
    for model, name in models_to_migrate:
        try:
            print(f"\n📋 Migrating {name}...")
            
            # Count records in PostgreSQL
            pg_count = pg_session.query(model).count()
            print(f"   Found {pg_count} records in PostgreSQL")
            
            if pg_count == 0:
                print(f"   ⚠️  No records to migrate")
                migration_summary[name] = {'source': 0, 'migrated': 0, 'status': 'empty'}
                continue
            
            # Fetch all records from PostgreSQL
            records = pg_session.query(model).all()
            
            # Insert into SQLite
            migrated_count = 0
            for record in records:
                # Create a dictionary of all columns
                record_dict = {c.name: getattr(record, c.name) for c in record.__table__.columns}
                
                # Create new instance for SQLite
                new_record = model(**record_dict)
                sqlite_session.add(new_record)
                migrated_count += 1
                
                # Commit in batches of 100
                if migrated_count % 100 == 0:
                    sqlite_session.commit()
                    print(f"   Migrated {migrated_count}/{pg_count} records...")
            
            # Final commit
            sqlite_session.commit()
            
            # Verify count in SQLite
            sqlite_count = sqlite_session.query(model).count()
            
            if sqlite_count == pg_count:
                print(f"   ✅ Successfully migrated {sqlite_count} records")
                migration_summary[name] = {'source': pg_count, 'migrated': sqlite_count, 'status': 'success'}
            else:
                print(f"   ⚠️  Warning: Count mismatch! PostgreSQL: {pg_count}, SQLite: {sqlite_count}")
                migration_summary[name] = {'source': pg_count, 'migrated': sqlite_count, 'status': 'warning'}
        
        except Exception as e:
            print(f"   ❌ Error migrating {name}: {str(e)}")
            migration_summary[name] = {'source': pg_count if 'pg_count' in locals() else 0, 'migrated': 0, 'status': 'error', 'error': str(e)}
            sqlite_session.rollback()
    
    # Close sessions
    pg_session.close()
    sqlite_session.close()
    
    return migration_summary

def verify_migration(postgres_engine, sqlite_engine):
    """Verify that migration was successful"""
    print("\n🔍 Verifying migration...")
    
    PostgresSession = sessionmaker(bind=postgres_engine)
    SQLiteSession = sessionmaker(bind=sqlite_engine)
    
    pg_session = PostgresSession()
    sqlite_session = SQLiteSession()
    
    models = [SNEForm, BloodCampDonor, Attendant]
    
    all_match = True
    for model in models:
        pg_count = pg_session.query(model).count()
        sqlite_count = sqlite_session.query(model).count()
        
        if pg_count == sqlite_count:
            print(f"   ✅ {model.__name__}: {pg_count} records match")
        else:
            print(f"   ❌ {model.__name__}: PostgreSQL={pg_count}, SQLite={sqlite_count}")
            all_match = False
    
    pg_session.close()
    sqlite_session.close()
    
    return all_match

def main():
    """Main migration function"""
    print("=" * 70)
    print("PostgreSQL to SQLite Migration Script")
    print("=" * 70)
    
    # Get database URIs
    postgres_uri = get_postgres_uri()
    sqlite_uri = get_sqlite_uri()
    
    print(f"\n📊 Source: PostgreSQL (RDS)")
    print(f"📊 Target: {sqlite_uri.replace('sqlite:///', '')}")
    
    # Create database engines
    print("\n🔌 Connecting to databases...")
    try:
        postgres_engine = create_engine(postgres_uri)
        sqlite_engine = create_engine(sqlite_uri)
        
        # Test connections
        with postgres_engine.connect() as conn:
            print("   ✅ Connected to PostgreSQL")
        
        with sqlite_engine.connect() as conn:
            print("   ✅ Connected to SQLite")
    
    except Exception as e:
        print(f"   ❌ Connection error: {str(e)}")
        sys.exit(1)
    
    # Create backup prompt
    create_backup(postgres_engine)
    
    # Create SQLite schema
    print("\n🏗️  Creating SQLite schema...")
    from app.models import db
    
    # Bind metadata to SQLite engine and create tables
    db.metadata.create_all(sqlite_engine)
    print("   ✅ Schema created successfully")
    
    # Migrate data
    print("\n🚀 Starting data migration...")
    migration_summary = migrate_data(postgres_engine, sqlite_engine)
    
    # Verify migration
    all_match = verify_migration(postgres_engine, sqlite_engine)
    
    # Print summary
    print("\n" + "=" * 70)
    print("MIGRATION SUMMARY")
    print("=" * 70)
    
    for table_name, stats in migration_summary.items():
        status_icon = "✅" if stats['status'] == 'success' else "⚠️" if stats['status'] == 'warning' else "❌"
        print(f"{status_icon} {table_name}: {stats['migrated']} / {stats['source']} records")
        if stats['status'] == 'error':
            print(f"   Error: {stats.get('error', 'Unknown error')}")
    
    print("\n" + "=" * 70)
    
    if all_match:
        print("✅ Migration completed successfully!")
        print("\n📝 Next steps:")
        print("   1. Update your .env file to use SQLite:")
        print("      Add: USE_SQLITE=true")
        print("   2. Test your application thoroughly")
        print("   3. Once verified, delete RDS instance to save $18/month")
        print("   4. Keep PostgreSQL backup for rollback if needed")
    else:
        print("⚠️  Migration completed with warnings. Please review the summary above.")
        print("   Do NOT delete PostgreSQL until all issues are resolved!")
    
    print("\n" + "=" * 70)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Migration cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Migration failed: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
