#!/usr/bin/env python3
"""
Production Server Testing Script
Tests your production EC2 server for race conditions
"""

import subprocess
import sys

# Production Configuration
PRODUCTION_URL = "https://your-domain.com"  # ⚠️ UPDATE THIS to your actual domain
USERNAME = "blood_camp_user"
PASSWORD = "your_production_password"  # ⚠️ UPDATE THIS to your production password
NUM_USERS = 30  # Number of concurrent users to simulate

print("=" * 70)
print("🌐 PRODUCTION SERVER RACE CONDITION TEST")
print("=" * 70)
print(f"Target: {PRODUCTION_URL}")
print(f"Concurrent Users: {NUM_USERS}")
print(f"Username: {USERNAME}")
print("=" * 70)
print()

# Confirm before proceeding
response = input("⚠️  This will submit test data to PRODUCTION. Continue? (yes/no): ")
if response.lower() != 'yes':
    print("Test cancelled.")
    sys.exit(0)

print()
print("Starting test...")
print()

# Run the test against production
result = subprocess.run([
    sys.executable,
    "test_concurrent_submissions.py",
    PRODUCTION_URL,
    str(NUM_USERS),
    USERNAME,
    PASSWORD
])

print()
print("=" * 70)
print("Test completed!")
print()
print("⚠️  CLEANUP REQUIRED:")
print("1. Login to your production server")
print("2. Check Google Sheets for test entries (look for 'ConcurrentTest' or 'LoadTest' names)")
print("3. Delete the test entries if needed")
print()
print("Or run: python verify_no_duplicates.py (pointing to production sheets)")
print("=" * 70)

sys.exit(result.returncode)
