#!/usr/bin/env python3
"""
Google Sheets to PostgreSQL Migration Script

Migrates all existing data from Google Sheets to PostgreSQL database.
Handles all three sheets: SNE Forms, Blood Camp Donors, and Attendants.

Usage:
    python migrate_sheets_to_postgres.py              # Migrate all data
    python migrate_sheets_to_postgres.py --dry-run    # Test without writing
    python migrate_sheets_to_postgres.py --table sne  # Migrate specific table
"""
import sys
import os
import argparse
import logging
from datetime import datetime
from dateutil import parser as date_parser

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask
from app.models import db, SNEForm, BloodCampDonor, Attendant
from app.database import init_db, check_connection
from app import config, utils

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_app():
    """Create minimal Flask app for migration"""
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'migration-secret'
    init_db(app)
    return app


def parse_date(date_str):
    """Parse date string to date object, return None if invalid"""
    if not date_str or str(date_str).strip() == '':
        return None
    try:
        return date_parser.parse(str(date_str)).date()
    except:
        return None


def parse_datetime(dt_str):
    """Parse datetime string, return None if invalid"""
    if not dt_str or str(dt_str).strip() == '':
        return None
    try:
        return date_parser.parse(str(dt_str))
    except:
        return None


def parse_int(int_str):
    """Parse integer, return None if invalid"""
    if not int_str or str(int_str).strip() == '':
        return None
    try:
        return int(int_str)
    except:
        return None


def migrate_sne_forms(dry_run=False):
    """Migrate SNE Forms from Google Sheets to PostgreSQL"""
    logger.info("\n" + "=" * 60)
    logger.info("Migrating SNE Forms")
    logger.info("=" * 60)
    
    try:
        # Fetch data from Google Sheets
        logger.info("Fetching data from Google Sheets...")
        sheet_data = utils.get_all_sheet_data(
            config.SNE_SHEET_ID,
            config.SNE_SERVICE_ACCOUNT_FILE,
            config.SNE_SHEET_HEADERS
        )
        logger.info(f"Found {len(sheet_data)} records in Google Sheets")
        
        if dry_run:
            logger.info("DRY RUN - No data will be written to database")
            if sheet_data:
                logger.info("\nSample record:")
                sample = sheet_data[0]
                for key, value in sample.items():
                    logger.info(f"  {key}: {value[:50] if len(str(value)) > 50 else value}")
            return len(sheet_data)
        
        # Migrate each record
        migrated = 0
        skipped = 0
        errors = 0
        
        for idx, record in enumerate(sheet_data, 1):
            try:
                badge_id = record.get('Badge ID', '').strip()
                if not badge_id:
                    logger.warning(f"Row {idx}: Missing Badge ID, skipping")
                    skipped += 1
                    continue
                
                # Check if already exists
                existing = SNEForm.query.filter_by(badge_id=badge_id).first()
                if existing:
                    logger.debug(f"Badge ID {badge_id} already exists, skipping")
                    skipped += 1
                    continue
                
                # Create new record
                sne = SNEForm(
                    badge_id=badge_id,
                    submission_date=parse_date(record.get('Submission Date')) or datetime.now().date(),
                    area=record.get('Area', '').strip(),
                    satsang_place=record.get('Satsang Place', '').strip(),
                    first_name=record.get('First Name', '').strip(),
                    last_name=record.get('Last Name', '').strip(),
                    father_husband_name=record.get("Father's/Husband's Name", '').strip(),
                    gender=record.get('Gender', '').strip(),
                    date_of_birth=parse_date(record.get('Date of Birth')),
                    age=parse_int(record.get('Age')),
                    blood_group=record.get('Blood Group', '').strip(),
                    aadhaar_no=utils.clean_aadhaar_number(record.get('Aadhaar No', '')),
                    mobile_no=utils.clean_phone_number(record.get('Mobile No', '')),
                    physically_challenged=record.get('Physically Challenged (Yes/No)', '').strip(),
                    physically_challenged_details=record.get('Physically Challenged Details', '').strip(),
                    help_required_home_pickup=record.get('Help Required for Home Pickup (Yes/No)', '').strip(),
                    help_pickup_reasons=record.get('Help Pickup Reasons', '').strip(),
                    handicap=record.get('Handicap (Yes/No)', '').strip(),
                    stretcher_required=record.get('Stretcher Required (Yes/No)', '').strip(),
                    wheelchair_required=record.get('Wheelchair Required (Yes/No)', '').strip(),
                    ambulance_required=record.get('Ambulance Required (Yes/No)', '').strip(),
                    pacemaker_operated=record.get('Pacemaker Operated (Yes/No)', '').strip(),
                    chair_required_sitting=record.get('Chair Required for Sitting (Yes/No)', '').strip(),
                    special_attendant_required=record.get('Special Attendant Required (Yes/No)', '').strip(),
                    hearing_loss=record.get('Hearing Loss (Yes/No)', '').strip(),
                    willing_attend_satsangs=record.get('Willing to Attend Satsangs (Yes/No)', '').strip(),
                    satsang_pickup_help_details=record.get('Satsang Pickup Help Details', '').strip(),
                    other_special_requests=record.get('Other Special Requests', '').strip(),
                    emergency_contact_name=record.get('Emergency Contact Name', '').strip(),
                    emergency_contact_number=record.get('Emergency Contact Number', '').strip(),
                    emergency_contact_relation=record.get('Emergency Contact Relation', '').strip(),
                    address=record.get('Address', '').strip(),
                    state=record.get('State', '').strip(),
                    pin_code=record.get('PIN Code', '').strip(),
                    photo_filename=record.get('Photo Filename', '').strip()
                )
                
                db.session.add(sne)
                migrated += 1
                
                if migrated % 100 == 0:
                    db.session.commit()
                    logger.info(f"Progress: {migrated}/{len(sheet_data)} records migrated")
                
            except Exception as e:
                logger.error(f"Row {idx} (Badge ID: {record.get('Badge ID', 'N/A')}): {e}")
                errors += 1
                continue
        
        # Final commit
        db.session.commit()
        
        logger.info(f"\nSNE Forms Migration Complete:")
        logger.info(f"  ✓ Migrated: {migrated}")
        logger.info(f"  - Skipped:  {skipped}")
        logger.info(f"  ✗ Errors:   {errors}")
        
        return migrated
        
    except Exception as e:
        logger.error(f"Fatal error migrating SNE forms: {e}", exc_info=True)
        return 0


def migrate_blood_camp(dry_run=False):
    """Migrate Blood Camp Donors from Google Sheets to PostgreSQL"""
    logger.info("\n" + "=" * 60)
    logger.info("Migrating Blood Camp Donors")
    logger.info("=" * 60)
    
    try:
        logger.info("Fetching data from Google Sheets...")
        sheet_data = utils.get_all_sheet_data(
            config.BLOOD_CAMP_SHEET_ID,
            config.BLOOD_CAMP_SERVICE_ACCOUNT_FILE,
            config.BLOOD_CAMP_SHEET_HEADERS
        )
        logger.info(f"Found {len(sheet_data)} records in Google Sheets")
        
        if dry_run:
            logger.info("DRY RUN - No data will be written to database")
            if sheet_data:
                logger.info("\nSample record:")
                sample = sheet_data[0]
                for key, value in sample.items():
                    logger.info(f"  {key}: {value[:50] if len(str(value)) > 50 else value}")
            return len(sheet_data)
        
        migrated = 0
        skipped = 0
        errors = 0
        
        for idx, record in enumerate(sheet_data, 1):
            try:
                donor_id = record.get('Donor ID', '').strip()
                if not donor_id:
                    logger.warning(f"Row {idx}: Missing Donor ID, skipping")
                    skipped += 1
                    continue
                
                existing = BloodCampDonor.query.filter_by(donor_id=donor_id).first()
                if existing:
                    logger.debug(f"Donor ID {donor_id} already exists, skipping")
                    skipped += 1
                    continue
                
                donor = BloodCampDonor(
                    donor_id=donor_id,
                    submission_timestamp=parse_datetime(record.get('Submission Timestamp')) or datetime.now(),
                    area=record.get('Area', '').strip(),
                    name_of_donor=record.get('Name of Donor', '').strip(),
                    father_husband_name=record.get("Father's/Husband's Name", '').strip(),
                    date_of_birth=parse_date(record.get('Date of Birth')),
                    gender=record.get('Gender', '').strip(),
                    occupation=record.get('Occupation', '').strip(),
                    house_no=record.get('House No.', '').strip(),
                    sector=record.get('Sector', '').strip(),
                    city=record.get('City', '').strip(),
                    mobile_number=utils.clean_phone_number(record.get('Mobile Number', '')),
                    blood_group=record.get('Blood Group', '').strip(),
                    allow_call=record.get('Allow Call', '').strip(),
                    donation_date=parse_date(record.get('Donation Date')),
                    donation_location=record.get('Donation Location', '').strip(),
                    first_donation_date=parse_date(record.get('First Donation Date')),
                    total_donations=parse_int(record.get('Total Donations')) or 1,
                    status=record.get('Status', 'Pending').strip(),
                    reason_for_rejection=record.get('Reason for Rejection', '').strip()
                )
                
                db.session.add(donor)
                migrated += 1
                
                if migrated % 100 == 0:
                    db.session.commit()
                    logger.info(f"Progress: {migrated}/{len(sheet_data)} records migrated")
                
            except Exception as e:
                logger.error(f"Row {idx} (Donor ID: {record.get('Donor ID', 'N/A')}): {e}")
                errors += 1
                continue
        
        db.session.commit()
        
        logger.info(f"\nBlood Camp Migration Complete:")
        logger.info(f"  ✓ Migrated: {migrated}")
        logger.info(f"  - Skipped:  {skipped}")
        logger.info(f"  ✗ Errors:   {errors}")
        
        return migrated
        
    except Exception as e:
        logger.error(f"Fatal error migrating blood camp: {e}", exc_info=True)
        return 0


def migrate_attendants(dry_run=False):
    """Migrate Attendants from Google Sheets to PostgreSQL"""
    logger.info("\n" + "=" * 60)
    logger.info("Migrating Attendants")
    logger.info("=" * 60)
    
    try:
        logger.info("Fetching data from Google Sheets...")
        sheet_data = utils.get_all_sheet_data(
            config.ATTENDANT_SHEET_ID,
            config.ATTENDANT_SERVICE_ACCOUNT_FILE,
            config.ATTENDANT_SHEET_HEADERS
        )
        logger.info(f"Found {len(sheet_data)} records in Google Sheets")
        
        if dry_run:
            logger.info("DRY RUN - No data will be written to database")
            if sheet_data:
                logger.info("\nSample record:")
                sample = sheet_data[0]
                for key, value in sample.items():
                    logger.info(f"  {key}: {value[:50] if len(str(value)) > 50 else value}")
            return len(sheet_data)
        
        migrated = 0
        skipped = 0
        errors = 0
        
        for idx, record in enumerate(sheet_data, 1):
            try:
                badge_id = record.get('Badge ID', '').strip()
                if not badge_id:
                    logger.warning(f"Row {idx}: Missing Badge ID, skipping")
                    skipped += 1
                    continue
                
                existing = Attendant.query.filter_by(badge_id=badge_id).first()
                if existing:
                    logger.debug(f"Badge ID {badge_id} already exists, skipping")
                    skipped += 1
                    continue
                
                attendant = Attendant(
                    badge_id=badge_id,
                    submission_date=parse_date(record.get('Submission Date')) or datetime.now().date(),
                    area=record.get('Area', '').strip(),
                    centre=record.get('Centre', '').strip(),
                    name=record.get('Name', '').strip(),
                    phone_number=utils.clean_phone_number(record.get('Phone Number', '')),
                    address=record.get('Address', '').strip(),
                    attendant_type=record.get('Attendant Type', '').strip(),
                    photo_filename=record.get('Photo Filename', '').strip(),
                    sne_id=record.get('SNE ID', '').strip(),
                    sne_name=record.get('SNE Name', '').strip(),
                    sne_gender=record.get('SNE Gender', '').strip(),
                    sne_address=record.get('SNE Address', '').strip(),
                    sne_photo_filename=record.get('SNE Photo Filename', '').strip()
                )
                
                db.session.add(attendant)
                migrated += 1
                
                if migrated % 100 == 0:
                    db.session.commit()
                    logger.info(f"Progress: {migrated}/{len(sheet_data)} records migrated")
                
            except Exception as e:
                logger.error(f"Row {idx} (Badge ID: {record.get('Badge ID', 'N/A')}): {e}")
                errors += 1
                continue
        
        db.session.commit()
        
        logger.info(f"\nAttendants Migration Complete:")
        logger.info(f"  ✓ Migrated: {migrated}")
        logger.info(f"  - Skipped:  {skipped}")
        logger.info(f"  ✗ Errors:   {errors}")
        
        return migrated
        
    except Exception as e:
        logger.error(f"Fatal error migrating attendants: {e}", exc_info=True)
        return 0


def main():
    parser = argparse.ArgumentParser(description='Migrate Google Sheets to PostgreSQL')
    parser.add_argument('--dry-run', action='store_true',
                       help='Test migration without writing to database')
    parser.add_argument('--table', choices=['sne', 'blood', 'attendant', 'all'],
                       default='all', help='Which table to migrate')
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("Google Sheets to PostgreSQL Migration")
    logger.info("=" * 60)
    
    # Create app and check connection
    app = create_app()
    
    with app.app_context():
        if not check_connection():
            logger.error("Failed to connect to database!")
            sys.exit(1)
        
        logger.info("✓ Database connection successful\n")
        
        total_migrated = 0
        
        # Migrate tables
        if args.table in ['sne', 'all']:
            total_migrated += migrate_sne_forms(args.dry_run)
        
        if args.table in ['blood', 'all']:
            total_migrated += migrate_blood_camp(args.dry_run)
        
        if args.table in ['attendant', 'all']:
            total_migrated += migrate_attendants(args.dry_run)
        
        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("Migration Summary")
        logger.info("=" * 60)
        logger.info(f"Total records migrated: {total_migrated}")
        
        if not args.dry_run:
            logger.info("\n✓ Migration complete!")
            logger.info("\nNext steps:")
            logger.info("  1. Verify data in PostgreSQL")
            logger.info("  2. Update Flask app to use PostgreSQL")
            logger.info("  3. Test application thoroughly before going live")
            logger.info("  4. Keep Google Sheets as backup until fully tested")
        else:
            logger.info("\nDRY RUN complete - no data was written")
            logger.info("Run without --dry-run to perform actual migration")


if __name__ == '__main__':
    main()
