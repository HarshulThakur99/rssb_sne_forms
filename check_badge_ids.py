"""
Quick script to check existing badge IDs in the database
Shows badge ID sequences for each centre in their designated ranges
"""
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from app.models import db, SNEForm
from app.config import SNE_BADGE_CONFIG

app = create_app()

with app.app_context():
    print("\n" + "=" * 90)
    print("🔍 BADGE ID SEQUENCE CHECK - By Centre")
    print("=" * 90)
    
    # Check each area and centre
    for area, centres in SNE_BADGE_CONFIG.items():
        print(f"\n📍 Area: {area}")
        print("-" * 90)
        
        for centre, config in centres.items():
            prefix = config['prefix']
            start = config['start']
            
            # Calculate expected range (assuming 10k per centre)
            range_end = start + 9999
            
            print(f"\n  🏢 Centre: {centre}")
            print(f"     Range: {prefix}{start:06d} to {prefix}{range_end:06d}")
            
            # Get current max for this centre
            max_badge_row = db.session.query(
                SNEForm.badge_id
            ).filter(
                SNEForm.area == area,
                SNEForm.satsang_place == centre,
                SNEForm.badge_id.like(f"{prefix}%")
            ).order_by(SNEForm.badge_id.desc()).first()
            
            if max_badge_row:
                current_max = max_badge_row.badge_id
                current_num = int(current_max.replace(prefix, ''))
                next_num = current_num + 1
                next_badge = f"{prefix}{next_num:06d}"
                
                # Count total badges for this centre
                count = db.session.query(SNEForm).filter(
                    SNEForm.area == area,
                    SNEForm.satsang_place == centre,
                    SNEForm.badge_id.like(f"{prefix}%")
                ).count()
                
                print(f"     Current: {current_max} ({count} total badges)")
                print(f"     Next:    {next_badge}")
                
                # Warn if approaching end of range
                if next_num > range_end - 100:
                    print(f"     ⚠️  WARNING: Approaching end of range!")
            else:
                print(f"     Current: None (no badges yet)")
                print(f"     Next:    {prefix}{start:06d}")
    
    print("\n" + "=" * 90)
    print("🔍 CHECKING FOR ISSUES")
    print("=" * 90)
    
    # Check for badges outside their designated ranges
    print("\n1. Badges outside designated ranges:")
    issues_found = False
    for area, centres in SNE_BADGE_CONFIG.items():
        for centre, config in centres.items():
            prefix = config['prefix']
            start = config['start']
            range_end = start + 9999
            
            # Find badges outside range
            out_of_range = db.session.query(
                SNEForm.badge_id, SNEForm.first_name, SNEForm.last_name
            ).filter(
                SNEForm.area == area,
                SNEForm.satsang_place == centre,
                SNEForm.badge_id.like(f"{prefix}%")
            ).all()
            
            for badge_id, first, last in out_of_range:
                try:
                    num = int(badge_id.replace(prefix, ''))
                    if num < start or num > range_end:
                        print(f"   ⚠️  {badge_id} ({centre}) is outside range {start}-{range_end}")
                        issues_found = True
                except ValueError:
                    pass
    
    if not issues_found:
        print("   ✅ All badges are within their designated ranges")
    
    # Check for duplicate badge IDs
    print("\n2. Duplicate badge IDs (should be none):")
    duplicates = db.session.execute("""
        SELECT badge_id, COUNT(*) as count
        FROM sne_forms
        GROUP BY badge_id
        HAVING COUNT(*) > 1
    """).fetchall()
    
    if duplicates:
        for badge_id, count in duplicates:
            print(f"   ⚠️  {badge_id} appears {count} times")
    else:
        print("   ✅ No duplicate badge IDs found")
    
    print("\n" + "=" * 90)

