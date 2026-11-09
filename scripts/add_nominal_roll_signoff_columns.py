"""
Add Nominal Roll Sign-Off / Mobile Columns
============================================
Adds the new columns introduced by the revised SCI/2020/84 nominal roll format:
    nominal_rolls.jathedar_sign_date, jathedar_contact_no,
                  functionary_sign_date, functionary_contact_no
    nominal_roll_sewadars.mobile_no

db.create_all() only creates missing TABLES, it never ALTERs existing ones, so
this is needed if the nominal_rolls / nominal_roll_sewadars tables were already
created by a previous scripts/init_db.py run. Safe to re-run: columns that
already exist are skipped.

Usage:
    python scripts/add_nominal_roll_signoff_columns.py              # dry run
    python scripts/add_nominal_roll_signoff_columns.py --execute    # apply
"""

import os
import sys
import argparse
from dotenv import load_dotenv

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, PROJECT_ROOT)

env_file = os.path.join(PROJECT_ROOT, '.env')
if os.path.exists(env_file):
    load_dotenv(env_file)

os.environ.setdefault('USE_DATABASE', 'true')

from sqlalchemy import text
from app import create_app
from app.models import db
from app.database import DatabaseConfig

COLUMNS_TO_ADD = [
    ('nominal_rolls', 'jathedar_sign_date', 'VARCHAR(50)'),
    ('nominal_rolls', 'jathedar_contact_no', 'VARCHAR(20)'),
    ('nominal_rolls', 'functionary_sign_date', 'VARCHAR(50)'),
    ('nominal_rolls', 'functionary_contact_no', 'VARCHAR(20)'),
    ('nominal_roll_sewadars', 'mobile_no', 'VARCHAR(15)'),
]


def existing_columns(table):
    if DatabaseConfig.use_sqlite():
        rows = db.session.execute(text(f"PRAGMA table_info({table})")).fetchall()
        return {row[1] for row in rows}  # row[1] = column name
    else:
        rows = db.session.execute(text(
            "SELECT column_name FROM information_schema.columns WHERE table_name = :table"
        ), {"table": table}).fetchall()
        return {row[0] for row in rows}


def run(execute):
    app = create_app()
    with app.app_context():
        to_add = []
        for table, column, col_type in COLUMNS_TO_ADD:
            if column not in existing_columns(table):
                to_add.append((table, column, col_type))

        print(f"\n{'='*60}")
        print("  NOMINAL ROLL COLUMN MIGRATION")
        print(f"{'='*60}")
        if not to_add:
            print("  All columns already exist. Nothing to do.")
            print(f"{'='*60}\n")
            return

        for table, column, col_type in to_add:
            print(f"  ADD  {table}.{column} {col_type}")
        print(f"  Mode: {'*** EXECUTE ***' if execute else 'DRY RUN (no changes)'}")
        print(f"{'='*60}\n")

        if not execute:
            print("DRY RUN complete - no changes made. Run with --execute to apply.\n")
            return

        for table, column, col_type in to_add:
            db.session.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
            db.session.commit()
            print(f"  Added {table}.{column}")

        print("\nDone.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Add new nominal roll columns for the revised SCI/2020/84 format.')
    parser.add_argument('--execute', action='store_true', help='Actually run the ALTER TABLE statements (default is dry run)')
    args = parser.parse_args()
    run(args.execute)
