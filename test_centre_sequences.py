"""
Test script to verify each centre gets its own independent badge ID sequence
"""
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from app.models import db
from app.db_helpers import get_next_sne_badge_id_postgres
from app.config import SNE_BADGE_CONFIG

app = create_app()

print("\n" + "=" * 80)
print("🧪 TESTING BADGE ID GENERATION - Independent Sequences")
print("=" * 80)

with app.app_context():
    # Test generating IDs for multiple centres
    test_centres = [
        ("Mullanpur Garibdass", "Lalru"),
        ("Mullanpur Garibdass", "Malikpur Jaula"),
        ("Mullanpur Garibdass", "Zirakpur"),
    ]
    
    print("\n📋 Testing ID generation for 3 different centres:")
    print("-" * 80)
    
    for area, centre in test_centres:
        config = SNE_BADGE_CONFIG[area][centre]
        prefix = config['prefix']
        start = config['start']
        
        print(f"\n🏢 {centre}")
        print(f"   Expected range: {prefix}{start:06d} to {prefix}{start+9999:06d}")
        
        try:
            # Generate next badge ID (within a transaction context)
            db.session.begin_nested()  # Start savepoint
            
            next_id = get_next_sne_badge_id_postgres(area, centre, prefix, start)
            
            db.session.rollback()  # Rollback to not actually create anything
            
            # Extract number from generated ID
            id_num = int(next_id.replace(prefix, ''))
            
            # Check if in correct range
            if start <= id_num <= start + 9999:
                print(f"   ✅ Generated: {next_id} (IN RANGE)")
            else:
                print(f"   ❌ Generated: {next_id} (OUT OF RANGE!)")
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    print("\n" + "=" * 80)
    print("✅ Test complete!")
    print("\nExpected behavior:")
    print("  - Lalru should generate IDs in 121xxx range")
    print("  - Malikpur Jaula should generate IDs in 131xxx range")
    print("  - Zirakpur should generate IDs in 171xxx range")
    print("\nEach centre maintains its own independent sequence.")
    print("=" * 80 + "\n")
