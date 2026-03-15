#!/usr/bin/env python3
"""
Verify No Duplicate IDs in Google Sheets
Checks for duplicate Badge IDs and Donor IDs across all sheets
"""

import os
from collections import Counter
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import app utilities
from app import utils, config

def check_blood_camp_duplicates():
    """Check for duplicate Donor IDs in Blood Camp sheet"""
    print("\n" + "=" * 70)
    print("🩸 BLOOD CAMP - Checking for Duplicate Donor IDs")
    print("=" * 70)
    
    try:
        sheet = utils.get_sheet(
            config.BLOOD_CAMP_SHEET_ID,
            config.BLOOD_CAMP_SERVICE_ACCOUNT_FILE,
            read_only=True
        )
        
        if not sheet:
            print("❌ Could not connect to Blood Camp sheet")
            return
        
        all_values = sheet.get_all_values()
        if len(all_values) <= 1:
            print("ℹ️  Sheet is empty or has only headers")
            return
        
        # Get Donor IDs (first column)
        donor_id_col_idx = 0  # "Donor ID" is first column
        donor_ids = [row[donor_id_col_idx].strip() for row in all_values[1:] if row and row[donor_id_col_idx].strip()]
        
        print(f"\nTotal Records: {len(donor_ids)}")
        print(f"Unique IDs: {len(set(donor_ids))}")
        
        # Check for duplicates
        id_counts = Counter(donor_ids)
        duplicates = {donor_id: count for donor_id, count in id_counts.items() if count > 1}
        
        if duplicates:
            print(f"\n⚠️  WARNING: Found {len(duplicates)} duplicate Donor ID(s)!")
            for donor_id, count in sorted(duplicates.items()):
                print(f"  - {donor_id}: appears {count} times")
        else:
            print("✅ No duplicate Donor IDs found!")
        
        # Show ID distribution
        print("\nID Prefix Distribution:")
        prefixes = Counter([donor_id.split('-')[0] if '-' in donor_id else donor_id[:2] for donor_id in donor_ids if donor_id])
        for prefix, count in sorted(prefixes.items()):
            print(f"  {prefix}: {count} records")
        
    except Exception as e:
        print(f"❌ Error checking Blood Camp sheet: {e}")

def check_sne_duplicates():
    """Check for duplicate Badge IDs in SNE sheet"""
    print("\n" + "=" * 70)
    print("👤 SNE MEMBERS - Checking for Duplicate Badge IDs")
    print("=" * 70)
    
    try:
        sheet = utils.get_sheet(
            config.SNE_SHEET_ID,
            config.SNE_SERVICE_ACCOUNT_FILE,
            read_only=True
        )
        
        if not sheet:
            print("❌ Could not connect to SNE sheet")
            return
        
        all_values = sheet.get_all_values()
        if len(all_values) <= 1:
            print("ℹ️  Sheet is empty or has only headers")
            return
        
        # Get Badge IDs (first column)
        badge_id_col_idx = 0  # "Badge ID" is first column
        badge_ids = [row[badge_id_col_idx].strip() for row in all_values[1:] if row and row[badge_id_col_idx].strip()]
        
        print(f"\nTotal Records: {len(badge_ids)}")
        print(f"Unique IDs: {len(set(badge_ids))}")
        
        # Check for duplicates
        id_counts = Counter(badge_ids)
        duplicates = {badge_id: count for badge_id, count in id_counts.items() if count > 1}
        
        if duplicates:
            print(f"\n⚠️  WARNING: Found {len(duplicates)} duplicate Badge ID(s)!")
            for badge_id, count in sorted(duplicates.items()):
                print(f"  - {badge_id}: appears {count} times")
        else:
            print("✅ No duplicate Badge IDs found!")
        
        # Show ID distribution by area/zone
        print("\nID Prefix Distribution:")
        prefixes = Counter([badge_id.split('-')[0] if '-' in badge_id else badge_id[:6] for badge_id in badge_ids if badge_id])
        for prefix, count in sorted(prefixes.items()):
            print(f"  {prefix}: {count} records")
        
    except Exception as e:
        print(f"❌ Error checking SNE sheet: {e}")

def check_attendant_duplicates():
    """Check for duplicate Badge IDs in Attendant sheet"""
    print("\n" + "=" * 70)
    print("👥 ATTENDANTS - Checking for Duplicate Badge IDs")
    print("=" * 70)
    
    try:
        sheet = utils.get_sheet(
            config.ATTENDANT_SHEET_ID,
            config.ATTENDANT_SERVICE_ACCOUNT_FILE,
            read_only=True
        )
        
        if not sheet:
            print("❌ Could not connect to Attendant sheet")
            return
        
        all_values = sheet.get_all_values()
        if len(all_values) <= 1:
            print("ℹ️  Sheet is empty or has only headers")
            return
        
        # Get Badge IDs (first column)
        badge_id_col_idx = 0  # "Badge ID" is first column
        badge_ids = [row[badge_id_col_idx].strip() for row in all_values[1:] if row and row[badge_id_col_idx].strip()]
        
        print(f"\nTotal Records: {len(badge_ids)}")
        print(f"Unique IDs: {len(set(badge_ids))}")
        
        # Check for duplicates
        id_counts = Counter(badge_ids)
        duplicates = {badge_id: count for badge_id, count in id_counts.items() if count > 1}
        
        if duplicates:
            print(f"\n⚠️  WARNING: Found {len(duplicates)} duplicate Badge ID(s)!")
            for badge_id, count in sorted(duplicates.items()):
                print(f"  - {badge_id}: appears {count} times")
        else:
            print("✅ No duplicate Badge IDs found!")
        
    except Exception as e:
        print(f"❌ Error checking Attendant sheet: {e}")

if __name__ == "__main__":
    print("=" * 70)
    print("🔍 DUPLICATE ID VERIFICATION TOOL")
    print("=" * 70)
    print("This tool checks all Google Sheets for duplicate IDs")
    print()
    
    check_blood_camp_duplicates()
    check_sne_duplicates()
    check_attendant_duplicates()
    
    print("\n" + "=" * 70)
    print("✅ Verification Complete!")
    print("=" * 70)
