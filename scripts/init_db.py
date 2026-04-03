#!/usr/bin/env python3
"""
Database Initialization Script
Creates all tables in PostgreSQL database

Usage:
    python init_db.py                    # Create tables
    python init_db.py --drop             # Drop and recreate all tables (DANGER!)
    python init_db.py --check            # Check database connection
"""
import sys
import os
import argparse
import logging

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask
from app.models import db, SNEForm, BloodCampDonor, Attendant
from app.database import init_db, create_tables, drop_tables, check_connection, DatabaseConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_app():
    """Create minimal Flask app for database operations"""
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'init-db-secret'  # Temporary secret for init
    
    # Initialize database
    init_db(app)
    
    return app


def main():
    parser = argparse.ArgumentParser(description='Initialize PostgreSQL database')
    parser.add_argument('--drop', action='store_true', 
                       help='Drop all tables before creating (DANGER!)')
    parser.add_argument('--check', action='store_true',
                       help='Only check database connection')
    args = parser.parse_args()
    
    # Check required environment variables
    required_vars = ['DB_HOST', 'DB_NAME', 'DB_USER', 'DB_PASSWORD']
    missing_vars = [var for var in required_vars if not os.environ.get(var)]
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        logger.info("\nRequired environment variables:")
        logger.info("  DB_HOST     - PostgreSQL host (e.g., localhost or RDS endpoint)")
        logger.info("  DB_PORT     - PostgreSQL port (default: 5432)")
        logger.info("  DB_NAME     - Database name (e.g., rssbsne)")
        logger.info("  DB_USER     - Database username")
        logger.info("  DB_PASSWORD - Database password")
        logger.info("\nFor local development, create a .env file with:")
        logger.info("  DB_HOST=localhost")
        logger.info("  DB_PORT=5432")
        logger.info("  DB_NAME=rssbsne_dev")
        logger.info("  DB_USER=postgres")
        logger.info("  DB_PASSWORD=your_password")
        sys.exit(1)
    
    # Display connection info (without password)
    logger.info("=" * 60)
    logger.info("Database Connection Information")
    logger.info("=" * 60)
    logger.info(f"Host:     {os.environ.get('DB_HOST')}")
    logger.info(f"Port:     {os.environ.get('DB_PORT', '5432')}")
    logger.info(f"Database: {os.environ.get('DB_NAME')}")
    logger.info(f"User:     {os.environ.get('DB_USER')}")
    logger.info("=" * 60)
    
    # Create Flask app
    app = create_app()
    
    with app.app_context():
        # Check connection
        logger.info("\nChecking database connection...")
        if not check_connection():
            logger.error("Failed to connect to database!")
            logger.error("Please verify:")
            logger.error("  1. PostgreSQL server is running")
            logger.error("  2. Database exists (create it with: CREATE DATABASE rssbsne;)")
            logger.error("  3. User has proper permissions")
            logger.error("  4. Network connectivity (especially for RDS)")
            sys.exit(1)
        
        logger.info("✓ Database connection successful!")
        
        if args.check:
            logger.info("Connection check complete.")
            sys.exit(0)
        
        # Drop tables if requested
        if args.drop:
            logger.warning("\n" + "!" * 60)
            logger.warning("WARNING: This will DELETE ALL DATA in the database!")
            logger.warning("!" * 60)
            
            if os.environ.get('FLASK_ENV') == 'production':
                logger.error("Cannot drop tables in production!")
                sys.exit(1)
            
            response = input("\nType 'YES DELETE ALL DATA' to confirm: ")
            if response != 'YES DELETE ALL DATA':
                logger.info("Aborted.")
                sys.exit(0)
            
            logger.warning("Dropping all tables...")
            drop_tables(app)
            logger.warning("✓ All tables dropped")
        
        # Create tables
        logger.info("\nCreating database tables...")
        try:
            create_tables(app)
            logger.info("✓ All tables created successfully!")
            
            # Display created tables
            logger.info("\nCreated tables:")
            logger.info(f"  - {SNEForm.__tablename__} (SNE registrations)")
            logger.info(f"  - {BloodCampDonor.__tablename__} (Blood donor records)")
            logger.info(f"  - {Attendant.__tablename__} (Attendant badges)")
            
            # Show table counts
            sne_count = db.session.query(SNEForm).count()
            blood_count = db.session.query(BloodCampDonor).count()
            attendant_count = db.session.query(Attendant).count()
            
            logger.info("\nCurrent record counts:")
            logger.info(f"  - SNE Forms: {sne_count}")
            logger.info(f"  - Blood Donors: {blood_count}")
            logger.info(f"  - Attendants: {attendant_count}")
            
            logger.info("\n" + "=" * 60)
            logger.info("Database initialization complete!")
            logger.info("=" * 60)
            
            if sne_count == 0 and blood_count == 0 and attendant_count == 0:
                logger.info("\nNext steps:")
                logger.info("  1. Run migration script to import data from Google Sheets:")
                logger.info("     python scripts/migrate_sheets_to_postgres.py")
                logger.info("  2. Update your Flask app to use PostgreSQL")
                logger.info("  3. Test the application thoroughly")
            
        except Exception as e:
            logger.error(f"Error creating tables: {e}", exc_info=True)
            sys.exit(1)


if __name__ == '__main__':
    main()
