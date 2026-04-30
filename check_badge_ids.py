"""
Quick script to check existing badge IDs in the database
"""
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from app.models import db, SNEForm

app = create_app()

with app.app_context():
    # Check for SNE-AX-15* badge IDs
    prefix = "SNE-AX-15"
    
    print(f"\n🔍 Checking for badge IDs with prefix: {prefix}*")
    print("=" * 70)
    
    results = db.session.query(
        SNEForm.badge_id,
        SNEForm.area,
        SNEForm.satsang_place,
        SNEForm.first_name,
        SNEForm.last_name
    ).filter(
        SNEForm.badge_id.like(f"{prefix}%")
    ).order_by(SNEForm.badge_id.desc()).limit(20).all()
    
    if results:
        print(f"\nFound {len(results)} matching badge IDs:\n")
        for badge_id, area, centre, first, last in results:
            print(f"  {badge_id:20s} | {area:25s} | {centre:25s} | {first} {last}")
        
        max_badge = results[0][0]
        print(f"\n✓ Maximum badge ID: {max_badge}")
        
        try:
            num = int(max_badge.replace(prefix, ''))
            next_num = num + 1
            next_badge = f"{prefix}{next_num:04d}"
            print(f"✓ Next badge ID should be: {next_badge}")
        except ValueError as e:
            print(f"✗ Error parsing badge ID: {e}")
    else:
        print(f"\n✗ No badge IDs found with prefix {prefix}")
        print(f"  First badge ID should be: {prefix}0001")
    
    # Check if SNE-AX-150056 exists
    specific_id = "SNE-AX-150056"
    exists = db.session.query(SNEForm).filter(SNEForm.badge_id == specific_id).first()
    
    print(f"\n🔍 Checking specific badge ID: {specific_id}")
    print("=" * 70)
    
    if exists:
        print(f"\n✓ Badge ID {specific_id} EXISTS in database:")
        print(f"  Area: {exists.area}")
        print(f"  Centre: {exists.satsang_place}")
        print(f"  Name: {exists.first_name} {exists.last_name}")
        print(f"  Aadhaar: {exists.aadhaar_no}")
    else:
        print(f"\n✗ Badge ID {specific_id} does NOT exist in database")
    
    print("\n" + "=" * 70)
