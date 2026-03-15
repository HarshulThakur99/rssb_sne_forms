#!/usr/bin/env python3
"""
Concurrent Submission Test Script
Tests race conditions in ID generation by simulating multiple simultaneous form submissions
Can test both local and production servers
"""

import threading
import time
import requests
from datetime import datetime
from random import randint, choice
import sys

# Configuration
# For production testing, change BASE_URL to your production URL
BASE_URL = "http://localhost:5000"  # Change to https://your-domain.com for production
USERNAME = "blood_camp_user"
PASSWORD = "bloodpass@123!"  # Update this to match your production password
NUM_CONCURRENT_REQUESTS = 10  # Reduced for Flask dev server (use 20+ with Gunicorn)
TEST_TYPE = "blood_camp"  # Options: "blood_camp", "sne", "attendant"

# Override via command line arguments
if len(sys.argv) > 1:
    BASE_URL = sys.argv[1]
if len(sys.argv) > 2:
    NUM_CONCURRENT_REQUESTS = int(sys.argv[2])
if len(sys.argv) > 3:
    USERNAME = sys.argv[3]
if len(sys.argv) > 4:
    PASSWORD = sys.argv[4]

# Store results
results = {
    "success": [],
    "errors": [],
    "response_times": [],
    "generated_ids": []
}
results_lock = threading.Lock()

def login_and_get_session():
    """Create a session and login"""
    session = requests.Session()
    login_data = {
        "username": USERNAME,
        "password": PASSWORD,
        "remember": "y"
    }
    response = session.post(f"{BASE_URL}/login", data=login_data, allow_redirects=True)
    # Check if login was successful (should redirect away from /login)
    if response.status_code != 200:
        print(f"❌ Login failed! Status: {response.status_code}")
        return None
    if "/login" in response.url:
        print(f"❌ Login failed! Still on login page. Check username/password.")
        return None
    return session

def submit_blood_camp_form(thread_id):
    """Submit a blood camp donor registration"""
    session = login_and_get_session()
    if not session:
        return
    
    # Generate unique mobile number using thread ID and timestamp
    timestamp = int(time.time() * 1000000) % 1000000
    mobile = f"9{(thread_id * 1000000 + timestamp) % 1000000000:09d}"
    
    data = {
        "donor_id": "",
        "donor_name": f"ConcurrentTest{thread_id}",
        "father_husband_name": f"Father{thread_id}",
        "dob": "1990-01-01",
        "gender": choice(["Male", "Female"]),
        "occupation": "Tester",
        "house_no": str(randint(1, 999)),
        "sector": f"Sector {randint(1, 50)}",
        "city": "Chandigarh",
        "mobile_no": mobile,
        "allow_call": "Yes",
        "blood_group": choice(["A+", "B+", "O+", "AB+"]),
        "donation_date": datetime.now().strftime("%Y-%m-%d"),
        "donation_location": "CHD-I (Sec 27)"
    }
    
    start_time = time.time()
    try:
        response = session.post(f"{BASE_URL}/blood_camp/submit", data=data)
        elapsed = time.time() - start_time
        
        with results_lock:
            results["response_times"].append(elapsed)
            if response.status_code == 200 or response.status_code == 302:
                # Try to extract Donor ID from response
                if "Donor ID:" in response.text:
                    # Extract the ID from the response
                    import re
                    match = re.search(r'Donor ID:\s*([A-Z0-9-]+)', response.text)
                    if match:
                        donor_id = match.group(1)
                        results["generated_ids"].append(donor_id)
                        results["success"].append({
                            "thread": thread_id,
                            "mobile": mobile,
                            "donor_id": donor_id,
                            "time": elapsed
                        })
                        print(f"✓ Thread {thread_id}: Success! ID={donor_id}, Mobile={mobile}, Time={elapsed:.3f}s")
                    else:
                        results["success"].append({"thread": thread_id, "time": elapsed, "mobile": mobile})
                        print(f"✓ Thread {thread_id}: Success (ID not found in response), Time={elapsed:.3f}s")
                else:
                    results["success"].append({"thread": thread_id, "time": elapsed, "mobile": mobile})
                    print(f"✓ Thread {thread_id}: Success, Time={elapsed:.3f}s")
            else:
                results["errors"].append({"thread": thread_id, "status": response.status_code, "mobile": mobile})
                print(f"✗ Thread {thread_id}: Failed with status {response.status_code}")
    except Exception as e:
        elapsed = time.time() - start_time
        with results_lock:
            results["errors"].append({"thread": thread_id, "error": str(e), "mobile": mobile})
        print(f"✗ Thread {thread_id}: Exception - {str(e)}")

def submit_sne_form(thread_id):
    """Submit an SNE member registration"""
    session = login_and_get_session()
    if not session:
        return
    
    # Generate unique identifiers
    timestamp = int(time.time() * 1000000) % 1000000000
    aadhaar = f"{(thread_id * 1000000000 + timestamp) % 1000000000000:012d}"
    mobile = f"9{(thread_id * 1000000 + timestamp) % 1000000000:09d}"
    
    data = {
        "area": "Chandigarh",
        "centre": "CHD-I (Sec 27)",
        "first_name": f"SNETest{thread_id}",
        "last_name": "Concurrent",
        "father_husband_name": f"Father{thread_id}",
        "gender": choice(["Male", "Female"]),
        "dob": "1950-01-15",
        "blood_group": "A+",
        "aadhaar_no": aadhaar,
        "mobile_no": mobile,
        "physically_challenged": "No",
        "willing_to_attend": "Yes",
        "emergency_contact_name": "Emergency",
        "emergency_contact_number": "9999999999",
        "emergency_contact_relation": "Son",
        "address": "Test Address",
        "state": "Punjab",
        "pincode": "160001"
    }
    
    start_time = time.time()
    try:
        response = session.post(f"{BASE_URL}/sne/submit", data=data)
        elapsed = time.time() - start_time
        
        with results_lock:
            results["response_times"].append(elapsed)
            if response.status_code in [200, 302]:
                # Try to extract Badge ID
                import re
                match = re.search(r'Badge ID:\s*([A-Z0-9-]+)', response.text)
                badge_id = match.group(1) if match else "Unknown"
                if badge_id != "Unknown":
                    results["generated_ids"].append(badge_id)
                results["success"].append({
                    "thread": thread_id,
                    "aadhaar": aadhaar,
                    "mobile": mobile,
                    "badge_id": badge_id,
                    "time": elapsed
                })
                print(f"✓ Thread {thread_id}: Success! Badge={badge_id}, Time={elapsed:.3f}s")
            else:
                results["errors"].append({"thread": thread_id, "status": response.status_code})
                print(f"✗ Thread {thread_id}: Failed with status {response.status_code}")
    except Exception as e:
        with results_lock:
            results["errors"].append({"thread": thread_id, "error": str(e)})
        print(f"✗ Thread {thread_id}: Exception - {str(e)}")

def run_concurrent_test():
    """Run the concurrent submission test"""
    print("=" * 70)
    print(f"🔬 CONCURRENT SUBMISSION TEST - {TEST_TYPE.upper()}")
    print("=" * 70)
    print(f"Base URL: {BASE_URL}")
    print(f"Concurrent Requests: {NUM_CONCURRENT_REQUESTS}")
    print(f"Test Type: {TEST_TYPE}")
    print("=" * 70)
    print()
    
    # Choose the test function
    test_func = submit_blood_camp_form if TEST_TYPE == "blood_camp" else submit_sne_form
    
    threads = []
    print(f"⏱️  Starting {NUM_CONCURRENT_REQUESTS} concurrent submissions...")
    start_time = time.time()
    
    # Launch all threads at once
    for i in range(NUM_CONCURRENT_REQUESTS):
        thread = threading.Thread(target=test_func, args=(i,))
        threads.append(thread)
        thread.start()
        time.sleep(0.01)  # Small stagger to avoid overwhelming the system
    
    # Wait for all threads to complete
    for thread in threads:
        thread.join()
    
    total_time = time.time() - start_time
    
    # Print results
    print()
    print("=" * 70)
    print("📊 TEST RESULTS")
    print("=" * 70)
    print(f"Total Time: {total_time:.2f}s")
    print(f"Successful: {len(results['success'])}")
    print(f"Failed: {len(results['errors'])}")
    print(f"Success Rate: {len(results['success']) / NUM_CONCURRENT_REQUESTS * 100:.1f}%")
    
    if results["response_times"]:
        avg_time = sum(results["response_times"]) / len(results["response_times"])
        min_time = min(results["response_times"])
        max_time = max(results["response_times"])
        print(f"\nResponse Times:")
        print(f"  Average: {avg_time:.3f}s")
        print(f"  Min: {min_time:.3f}s")
        print(f"  Max: {max_time:.3f}s")
    
    # Check for duplicate IDs
    if results["generated_ids"]:
        unique_ids = set(results["generated_ids"])
        duplicates = len(results["generated_ids"]) - len(unique_ids)
        
        print(f"\n🆔 ID Generation Check:")
        print(f"  Total IDs Generated: {len(results['generated_ids'])}")
        print(f"  Unique IDs: {len(unique_ids)}")
        print(f"  Duplicates: {duplicates}")
        
        if duplicates > 0:
            print(f"\n⚠️  WARNING: {duplicates} DUPLICATE ID(S) FOUND!")
            print("  This indicates a race condition issue!")
            # Show which IDs were duplicated
            from collections import Counter
            id_counts = Counter(results["generated_ids"])
            for donor_id, count in id_counts.items():
                if count > 1:
                    print(f"    - {donor_id}: appeared {count} times")
        else:
            print("  ✅ No duplicates found - race condition fix is working!")
    
    if results["errors"]:
        print(f"\n❌ Errors:")
        for error in results["errors"][:5]:  # Show first 5 errors
            print(f"  {error}")
    
    print("=" * 70)

if __name__ == "__main__":
    # Make sure the server is running
    try:
        response = requests.get(BASE_URL, timeout=5)
        print(f"✓ Server is reachable at {BASE_URL}")
    except:
        print(f"❌ Cannot reach server at {BASE_URL}")
        print("Make sure your Flask app is running: python run.py")
        exit(1)
    
    run_concurrent_test()
