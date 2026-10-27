"""
Sewadar Master List Importer
=============================
Loads a cleaned sewadar CSV (see dedupe_sewadar_badges.py) into the `sewadars`
table so it can be viewed on the website's Database Viewer like the other
tables. The CSV is expected to have this exact column order (the header has
"Age" twice - once for Blood Group, once for the real age):

    Badge_Number, Old_Badge_Number, Sewadar_Name, Relation, Father_Husband_Name,
    DOB, DOE, Gender, Age (blood group), Centre, Department, Address,
    Contact_No, City, State, Age (real age), Year of Birth

Usage:
    python scripts/import_sewadars_csv.py <input.csv>              # dry run (safe, no changes)
    python scripts/import_sewadars_csv.py <input.csv> --execute    # actually import
    python scripts/import_sewadars_csv.py <input.csv> --execute --replace  # wipe table first, then import
"""

import os
import sys
import csv
import argparse
import datetime
from dotenv import load_dotenv

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, PROJECT_ROOT)

env_file = os.path.join(PROJECT_ROOT, '.env')
if os.path.exists(env_file):
    load_dotenv(env_file)

from app import create_app
from app.models import db, Sewadar

EXPECTED_HEADER = [
    'Badge_Number', 'Old_Badge_Number', 'Sewadar_Name', 'Relation', 'Father_Husband_Name',
    'DOB', 'DOE', 'Gender', 'Age', 'Centre', 'Department', 'Address',
    'Contact_No', 'City', 'State', 'Age', 'Year of Birth'
]


def parse_date(value):
    value = (value or '').strip()
    if not value:
        return None
    for fmt in ('%d/%m/%Y', '%Y-%m-%d'):
        try:
            return datetime.datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def parse_int(value):
    value = (value or '').strip()
    try:
        return int(float(value))
    except ValueError:
        return None


def clean(value):
    value = (value or '').strip()
    return value or None


def load_rows(csv_path):
    with open(csv_path, newline='', encoding='utf-8-sig') as f:
        rows = list(csv.reader(f))

    if not rows:
        raise ValueError("CSV file is empty.")

    header = [h.strip() for h in rows[0]]
    if header != EXPECTED_HEADER:
        raise ValueError(
            f"Unexpected CSV header.\nExpected: {EXPECTED_HEADER}\nGot:      {header}\n"
            "Re-export from dedupe_sewadar_badges.py so the column order matches."
        )

    sewadars = []
    for row in rows[1:]:
        row = row + [''] * (len(EXPECTED_HEADER) - len(row))  # pad ragged rows
        sewadars.append(Sewadar(
            badge_number=clean(row[0]),
            old_badge_number=clean(row[1]),
            sewadar_name=clean(row[2]) or 'UNKNOWN',
            relation=clean(row[3]),
            father_husband_name=clean(row[4]),
            dob=parse_date(row[5]),
            doe=parse_date(row[6]),
            gender=clean(row[7]),
            blood_group=clean(row[8]),
            centre=clean(row[9]) or 'UNKNOWN',
            department=clean(row[10]),
            address=clean(row[11]),
            contact_no=clean(row[12]),
            city=clean(row[13]),
            state=clean(row[14]),
            age=parse_int(row[15]),
            year_of_birth=parse_int(row[16]),
        ))
    return sewadars


def run(csv_path, execute, replace):
    sewadars = load_rows(csv_path)

    print(f"\n{'='*60}")
    print(f"  SEWADAR CSV IMPORT")
    print(f"{'='*60}")
    print(f"  Rows parsed from CSV : {len(sewadars)}")
    print(f"  Mode                 : {'*** EXECUTE ***' if execute else 'DRY RUN (no changes)'}")
    print(f"  Replace existing rows: {replace}")
    print(f"{'='*60}\n")

    if not execute:
        print("DRY RUN complete - no database changes made.")
        print("Run with --execute to import, add --replace to wipe the table first.\n")
        return

    app = create_app()
    with app.app_context():
        existing_count = db.session.query(Sewadar).count()

        if replace and existing_count:
            confirm = input(f"Type YES to permanently delete all {existing_count} existing Sewadar rows: ").strip()
            if confirm != "YES":
                print("Aborted. No changes made.")
                return
            db.session.query(Sewadar).delete()
            db.session.commit()
            print(f"Deleted {existing_count} existing rows.")

        db.session.bulk_save_objects(sewadars)
        db.session.commit()
        print(f"Imported {len(sewadars)} sewadar rows successfully.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Import a cleaned sewadar CSV into the sewadars table')
    parser.add_argument('csv_path', help='Path to the cleaned CSV file')
    parser.add_argument('--execute', action='store_true', help='Actually write to the database')
    parser.add_argument('--replace', action='store_true', help='Delete all existing rows before importing')
    args = parser.parse_args()

    run(args.csv_path, args.execute, args.replace)
