"""
Blood Camp Donor Deduplication Script
======================================
Finds all duplicate blood donor records where BOTH name_of_donor AND
mobile_number match. Keeps the OLDEST record (lowest id / earliest
submission_timestamp) and deletes the rest.

Usage:
    python scripts/deduplicate_blood_donors.py            # dry run (safe, no changes)
    python scripts/deduplicate_blood_donors.py --execute  # actually delete duplicates
"""

import os
import sys
import argparse
from dotenv import load_dotenv

# Add project root to path so app imports work
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, PROJECT_ROOT)

# Load .env from project root explicitly
env_file = os.path.join(PROJECT_ROOT, '.env')
if os.path.exists(env_file):
    load_dotenv(env_file)
    print(f"Loaded .env from: {env_file}")
else:
    print(f"WARNING: No .env file found at {env_file}")
    print("Make sure DB_HOST, DB_NAME, DB_USER, DB_PASSWORD are set as environment variables.\n")

from app import create_app
from app.models import db, BloodCampDonor
from sqlalchemy import func


def find_duplicates():
    """
    Return a list of (name_of_donor, mobile_number, count) for every
    name+mobile combination that appears more than once.
    """
    results = (
        db.session.query(
            BloodCampDonor.name_of_donor,
            BloodCampDonor.mobile_number,
            func.count(BloodCampDonor.id).label('cnt')
        )
        .group_by(BloodCampDonor.name_of_donor, BloodCampDonor.mobile_number)
        .having(func.count(BloodCampDonor.id) > 1)
        .order_by(func.count(BloodCampDonor.id).desc())
        .all()
    )
    return results


def get_ids_to_delete(name, mobile):
    """
    For a given name+mobile, return all record IDs except the oldest one
    (oldest = smallest id, i.e. first inserted).
    """
    records = (
        db.session.query(BloodCampDonor.id, BloodCampDonor.donor_id, BloodCampDonor.submission_timestamp)
        .filter(
            BloodCampDonor.name_of_donor == name,
            BloodCampDonor.mobile_number == mobile
        )
        .order_by(BloodCampDonor.id.asc())  # oldest first
        .all()
    )

    keep = records[0]   # keep the oldest (first) record
    delete = records[1:]  # delete everything else
    return keep, delete


def run(execute=False):
    duplicates = find_duplicates()

    if not duplicates:
        print("No duplicates found. Database is clean!")
        return

    total_to_delete = sum(row.cnt - 1 for row in duplicates)
    unique_donors = len(duplicates)

    print(f"\n{'='*60}")
    print(f"  DUPLICATE BLOOD DONORS REPORT")
    print(f"{'='*60}")
    print(f"  Unique name+mobile combinations with duplicates : {unique_donors}")
    print(f"  Total extra records to delete (keeping 1 each)  : {total_to_delete}")
    print(f"  Mode : {'*** EXECUTE — WILL DELETE ***' if execute else 'DRY RUN (no changes)'}")
    print(f"{'='*60}\n")

    ids_to_delete_all = []

    for row in duplicates:
        keep, to_delete = get_ids_to_delete(row.name_of_donor, row.mobile_number)

        print(f"  Donor : {row.name_of_donor} | Mobile : {row.mobile_number}")
        print(f"    KEEP   -> DB id={keep.id}  donor_id={keep.donor_id}  submitted={keep.submission_timestamp}")
        for rec in to_delete:
            print(f"    DELETE -> DB id={rec.id}  donor_id={rec.donor_id}  submitted={rec.submission_timestamp}")
            ids_to_delete_all.append(rec.id)
        print()

    print(f"{'='*60}")
    print(f"  Records to delete : {len(ids_to_delete_all)}")
    print(f"{'='*60}\n")

    if not execute:
        print("DRY RUN complete — no records were deleted.")
        print("Run with --execute to permanently delete the duplicates.\n")
        return

    # ---- EXECUTE: delete in batches ----
    confirm = input(f"Type YES to permanently delete {len(ids_to_delete_all)} records: ").strip()
    if confirm != "YES":
        print("Aborted. No records deleted.")
        return

    # Delete in chunks to avoid huge single queries
    chunk_size = 100
    deleted_total = 0
    for i in range(0, len(ids_to_delete_all), chunk_size):
        chunk = ids_to_delete_all[i:i + chunk_size]
        deleted = (
            db.session.query(BloodCampDonor)
            .filter(BloodCampDonor.id.in_(chunk))
            .delete(synchronize_session=False)
        )
        db.session.commit()
        deleted_total += deleted
        print(f"  Deleted batch {i // chunk_size + 1}: {deleted} records")

    print(f"\nDone. {deleted_total} duplicate records deleted.")
    print("One record per name+mobile combination has been kept (the oldest).")


def main():
    parser = argparse.ArgumentParser(description='Deduplicate blood camp donors by name + mobile number.')
    parser.add_argument('--execute', action='store_true',
                        help='Actually delete duplicates (default is dry run)')
    args = parser.parse_args()

    # We need the Flask app context for SQLAlchemy
    os.environ.setdefault('USE_DATABASE', 'true')

    use_sqlite = os.environ.get('USE_SQLITE', 'false').lower() in ('true', '1', 'yes')

    if use_sqlite:
        sqlite_path = os.environ.get('SQLITE_DB_PATH', 'instance/rssbsne.db')
        print(f"\nConnecting to: SQLite at {sqlite_path}\n")
    else:
        db_host = os.environ.get('DB_HOST', 'localhost')
        db_port = os.environ.get('DB_PORT', '5432')
        db_name = os.environ.get('DB_NAME', 'rssbsne')
        db_user = os.environ.get('DB_USER', 'postgres')
        db_pass = os.environ.get('DB_PASSWORD', '')
        print(f"\nConnecting to: postgresql://{db_user}@{db_host}:{db_port}/{db_name}")
        if not db_pass:
            print("ERROR: DB_PASSWORD is not set. Check your .env file.\n")
            sys.exit(1)
        print()

    app = create_app()
    with app.app_context():
        run(execute=args.execute)


if __name__ == '__main__':
    main()
