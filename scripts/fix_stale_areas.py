"""
Fix Stale Area Names
=====================
SNE_BADGE_CONFIG's area names have been renamed multiple times (e.g. "New
Chandigarh" -> "Mullanpur Garibdass" -> "Mohali"), but existing sne_forms and
attendants rows keep whatever area string was current when they were saved.
A centre's *name* doesn't change when the area it's grouped under is renamed,
so this script uses each row's centre to look up the area it SHOULD have
under the current config, and fixes any row where the stored area is stale.

Rows whose centre doesn't match any centre in the current config at all are
left untouched and listed separately for manual review (renaming the area
won't help there - the centre itself may have been renamed/removed).

Usage:
    python scripts/fix_stale_areas.py              # dry run (safe, no changes)
    python scripts/fix_stale_areas.py --execute    # actually update the rows
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

from app import create_app, config
from app.models import db, SNEForm, Attendant

# centre name -> the area it currently belongs to
CENTRE_TO_AREA = {
    centre: area
    for area, centres in config.SNE_BADGE_CONFIG.items()
    for centre in centres
}


def plan_fixes(model, area_attr, centre_attr):
    """Returns (fixes, unknown) where fixes is a list of
    (stored_area, centre, correct_area, count) and unknown is a list of
    (stored_area, centre, count) for centres not found in the current config."""
    area_col = getattr(model, area_attr)
    centre_col = getattr(model, centre_attr)

    rows = (
        db.session.query(area_col, centre_col, db.func.count(model.id))
        .group_by(area_col, centre_col)
        .all()
    )

    fixes, unknown = [], []
    for stored_area, centre, count in rows:
        correct_area = CENTRE_TO_AREA.get(centre)
        if correct_area is None:
            unknown.append((stored_area, centre, count))
        elif correct_area != stored_area:
            fixes.append((stored_area, centre, correct_area, count))
    return fixes, unknown


def run(execute):
    app = create_app()
    with app.app_context():
        targets = [
            ('SNE Forms', SNEForm, 'area', 'satsang_place'),
            ('Attendants', Attendant, 'area', 'centre'),
        ]

        print(f"\n{'='*70}")
        print("  STALE AREA REPORT")
        print(f"{'='*70}")

        all_fixes = []  # (table_label, model, area_attr, centre_attr, stored_area, centre, correct_area, count)
        for label, model, area_attr, centre_attr in targets:
            fixes, unknown = plan_fixes(model, area_attr, centre_attr)

            print(f"\n{label}:")
            if fixes:
                for stored_area, centre, correct_area, count in fixes:
                    print(f"  FIX     '{stored_area}' -> '{correct_area}'  (centre='{centre}', {count} rows)")
                    all_fixes.append((label, model, area_attr, centre_attr, stored_area, centre, correct_area, count))
            else:
                print("  No stale areas found.")

            if unknown:
                print("  Centres not in current config (left untouched, needs manual review):")
                for stored_area, centre, count in unknown:
                    print(f"    ? area='{stored_area}' centre='{centre}' ({count} rows)")

        total_rows = sum(f[7] for f in all_fixes)
        print(f"\n{'='*70}")
        print(f"  Total rows to fix: {total_rows}")
        print(f"  Mode: {'*** EXECUTE ***' if execute else 'DRY RUN (no changes)'}")
        print(f"{'='*70}\n")

        if not execute:
            print("DRY RUN complete - no changes made. Run with --execute to apply.\n")
            return

        if not all_fixes:
            print("Nothing to fix.")
            return

        confirm = input(f"Type YES to update area on {total_rows} rows: ").strip()
        if confirm != "YES":
            print("Aborted. No changes made.")
            return

        for label, model, area_attr, centre_attr, stored_area, centre, correct_area, count in all_fixes:
            updated = (
                db.session.query(model)
                .filter(getattr(model, area_attr) == stored_area, getattr(model, centre_attr) == centre)
                .update({area_attr: correct_area}, synchronize_session=False)
            )
            db.session.commit()
            print(f"  [{label}] '{stored_area}' -> '{correct_area}' (centre='{centre}'): {updated} rows updated")

        print("\nDone.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Fix stale area values using each row\'s centre as the source of truth.')
    parser.add_argument('--execute', action='store_true', help='Actually update the rows (default is dry run)')
    args = parser.parse_args()
    run(args.execute)
