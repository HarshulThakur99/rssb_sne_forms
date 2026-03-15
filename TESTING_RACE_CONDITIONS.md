# Race Condition Testing Guide

This guide shows you how to test the concurrent ID generation fix without needing multiple real users.

## Testing Tools Created

1. **`test_concurrent_submissions.py`** - Python threading test (recommended)
2. **`locustfile.py`** - Load testing with Locust (stress test)
3. **`verify_no_duplicates.py`** - Check Google Sheets for duplicate IDs

---

## Method 1: Python Threading Test (Quick & Easy)

This simulates 20 users submitting forms simultaneously using Python threads.

### Run the test:

```powershell
# Make sure your app is running
python run.py

# In another terminal, run the concurrent test
python test_concurrent_submissions.py
```

### What it does:
- Creates 20 threads that all submit forms at the same time
- Each thread logs in and submits a form
- Captures the generated IDs
- **Checks for duplicates automatically**
- Shows response times and success rate

### Expected Output:
```
🔬 CONCURRENT SUBMISSION TEST - BLOOD_CAMP
==================================================================
✓ Thread 0: Success! ID=BD0001, Mobile=9123456789, Time=0.234s
✓ Thread 1: Success! ID=BD0002, Mobile=9123456790, Time=0.245s
...

📊 TEST RESULTS
==================================================================
Total Time: 2.45s
Successful: 20
Failed: 0
Success Rate: 100.0%

🆔 ID Generation Check:
  Total IDs Generated: 20
  Unique IDs: 20
  Duplicates: 0
  ✅ No duplicates found - race condition fix is working!
```

### To test different modules:

Edit `test_concurrent_submissions.py` line 14:
```python
TEST_TYPE = "blood_camp"  # Options: "blood_camp", "sne", "attendant"
```

---

## Method 2: Locust Load Testing (Heavy Stress Test)

Locust simulates hundreds of users making requests.

### Install Locust:

```powershell
pip install locust
```

### Run Locust:

```powershell
# Make sure your app is running
python run.py

# In another terminal, start Locust
locust -f locustfile.py --host=http://localhost:5000
```

### Use the Web UI:

1. Open browser: http://localhost:8089
2. Set:
   - **Number of users**: 50 (simulates 50 concurrent users)
   - **Spawn rate**: 10 (adds 10 users per second)
3. Click "Start swarming"
4. Watch the live statistics

### What to monitor:
- **Requests/s**: How many forms submitted per second
- **Failures**: Should be 0% if race condition is fixed
- **Response times**: Average, min, max

### Stop the test:
- Click "Stop" in the web UI
- Check Google Sheets for any duplicate IDs

---

## Method 3: Verify No Duplicates in Sheets

After running load tests, verify that no duplicate IDs were created.

### Run verification:

```powershell
python verify_no_duplicates.py
```

### What it checks:
- Blood Camp: Duplicate Donor IDs
- SNE Members: Duplicate Badge IDs  
- Attendants: Duplicate Badge IDs

### Sample Output:
```
🔍 DUPLICATE ID VERIFICATION TOOL
==================================================================

🩸 BLOOD CAMP - Checking for Duplicate Donor IDs
==================================================================
Total Records: 156
Unique IDs: 156
✅ No duplicate Donor IDs found!

👤 SNE MEMBERS - Checking for Duplicate Badge IDs
==================================================================
Total Records: 89
Unique IDs: 89
✅ No duplicate Badge IDs found!
```

---

## Testing Recommendations

### 1. **Quick Test** (2 minutes)
```powershell
python test_concurrent_submissions.py
```
- Tests 20 concurrent submissions
- Automatic duplicate detection
- See results immediately

### 2. **Medium Test** (5 minutes)
```powershell
locust -f locustfile.py --host=http://localhost:5000 --headless -u 50 -r 10 --run-time 2m
```
- 50 concurrent users for 2 minutes
- Runs without web UI
- Results shown in terminal

### 3. **Stress Test** (10+ minutes)
```powershell
locust -f locustfile.py --host=http://localhost:5000
```
- Use web UI to control
- Start with 10 users, increase gradually
- Monitor for failures or slowdowns
- Check sheets afterward: `python verify_no_duplicates.py`

---

## What to Look For

### ✅ Race Condition is FIXED if:
- All concurrent requests succeed (100% success rate)
- No duplicate IDs generated
- Each submission gets a unique sequential ID
- Response times are consistent

### ❌ Race Condition EXISTS if:
- Duplicate IDs appear in results
- Some requests fail with ID conflicts
- Verification script shows duplicate IDs in sheets

---

## Troubleshooting

### "Cannot reach server"
```powershell
# Make sure Flask is running
python run.py
```

### "Login failed"
Update credentials in test files:
- `test_concurrent_submissions.py` line 11-12
- `locustfile.py` line 6-7

### "Could not connect to sheet"
Check your `.env` file has correct:
- Google Sheet IDs
- Service account file paths

### Test data cluttering your sheets?
You can:
1. Create a separate test Google Sheet
2. Delete test entries after testing
3. Use a "test" area/centre that you can filter out

---

## Example Test Workflow

```powershell
# 1. Start your app
python run.py

# 2. Open new terminal and run quick test
python test_concurrent_submissions.py

# 3. If no duplicates, try stress test
locust -f locustfile.py --host=http://localhost:5000 --headless -u 100 -r 20 --run-time 3m

# 4. Verify sheets are clean
python verify_no_duplicates.py

# 5. Check app logs for any errors
# Look for INFO/WARNING/ERROR messages
```

---

## Advanced: Customize Tests

### Test more users:
Edit `test_concurrent_submissions.py`:
```python
NUM_CONCURRENT_REQUESTS = 50  # Increase from 20 to 50
```

### Test different scenarios:
```python
# Submit to different centres simultaneously
data["donation_location"] = choice([
    "CHD-I (Sec 27)", 
    "CHD-II (Maloya)", 
    "CHD-III (Khuda Alisher)"
])
```

### Add delays between submissions:
```python
time.sleep(0.1)  # 100ms delay between thread starts
```

---

## Summary

**Fastest way to test**: `python test_concurrent_submissions.py`

This will tell you immediately if your race condition fix is working or not!
