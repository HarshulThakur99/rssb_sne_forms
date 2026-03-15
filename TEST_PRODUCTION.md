# Testing Production Server for Race Conditions

## Method 1: Quick Command Line Test

Update and run this command with your production details:

```powershell
python test_concurrent_submissions.py https://your-domain.com 30 blood_camp_user your_production_password
```

**Parameters:**
1. Production URL (with https://)
2. Number of concurrent users to simulate
3. Username
4. Password

**Example:**
```powershell
python test_concurrent_submissions.py https://forms.rssb.org 30 blood_camp_user "MySecurePass123!"
```

---

## Method 2: Using Production Test Script

1. **Edit `test_production.py`** and update:
   ```python
   PRODUCTION_URL = "https://your-actual-domain.com"
   PASSWORD = "your_actual_production_password"
   NUM_USERS = 30
   ```

2. **Run the test:**
   ```powershell
   python test_production.py
   ```

3. **It will ask for confirmation** before submitting to production

---

## Method 3: SSH to Production and Test Locally

This is the **SAFEST** way to test production infrastructure without external dependencies.

### On your local machine:

```powershell
# Copy test scripts to production server
scp test_concurrent_submissions.py ec2-user@your-server:/home/ec2-user/
scp verify_no_duplicates.py ec2-user@your-server:/home/ec2-user/
```

### SSH into production:

```bash
ssh ec2-user@your-server
```

### On the production server:

```bash
# Navigate to app directory
cd /path/to/rssb_sne_forms

# Make sure requests is installed
pip install requests

# Run test against localhost (tests actual Gunicorn setup)
python test_concurrent_submissions.py http://localhost:5000 50 blood_camp_user "your_password"

# Verify no duplicates
python verify_no_duplicates.py
```

**Why this is better:**
- Tests the actual Gunicorn worker setup
- No network latency
- Can test with higher concurrent requests (50-100)
- More realistic production load

---

## What to Look For

### ✅ Success Indicators:
```
📊 TEST RESULTS
Successful: 50
Failed: 0
Success Rate: 100.0%

🆔 ID Generation Check:
  Unique IDs: 50
  Duplicates: 0
  ✅ No duplicates found - race condition fix is working!
```

### ❌ Problem Indicators:
```
⚠️  WARNING: 3 DUPLICATE ID(S) FOUND!
  - BD1234: appeared 2 times
```

---

## Best Practice Test Flow

### 1. **Baseline Test** (Low Load)
```bash
python test_concurrent_submissions.py http://localhost:5000 10 blood_camp_user "password"
```

### 2. **Medium Load Test**
```bash
python test_concurrent_submissions.py http://localhost:5000 30 blood_camp_user "password"
```

### 3. **Stress Test** (Max Load)
```bash
python test_concurrent_submissions.py http://localhost:5000 50 blood_camp_user "password"
```

### 4. **Verify Sheets**
```bash
python verify_no_duplicates.py
```

---

## Cleanup After Testing

### Option 1: Manual Cleanup
1. Open Google Sheets
2. Filter by name containing "ConcurrentTest" or "LoadTest"
3. Delete test rows

### Option 2: Automated Cleanup Script

Create `cleanup_test_data.py`:

```python
from app import utils, config

sheet = utils.get_sheet(
    config.BLOOD_CAMP_SHEET_ID,
    config.BLOOD_CAMP_SERVICE_ACCOUNT_FILE,
    read_only=False
)

all_values = sheet.get_all_values()
rows_to_delete = []

# Find test entries (rows with ConcurrentTest, LoadTest, etc.)
for i, row in enumerate(all_values[1:], start=2):
    if row and len(row) > 3:
        name = row[3]  # Donor name column
        if 'ConcurrentTest' in name or 'LoadTest' in name:
            rows_to_delete.append(i)

# Delete in reverse order to maintain row numbers
for row_num in sorted(rows_to_delete, reverse=True):
    sheet.delete_rows(row_num)
    print(f"Deleted row {row_num}")

print(f"Deleted {len(rows_to_delete)} test entries")
```

---

## Monitoring Production During Test

### Watch Gunicorn Logs

```bash
# If using systemd
sudo journalctl -u rssb-forms -f

# Or tail the log file directly
tail -f /path/to/gunicorn.log
```

### Watch System Resources

```bash
# Monitor CPU and memory
htop

# Or
top
```

### Check for Errors

```bash
# Check for any errors in the last 100 lines
sudo journalctl -u rssb-forms -n 100 | grep ERROR
```

---

## Performance Benchmarks

Based on your Gunicorn setup (3 workers):

| Concurrent Users | Expected Success Rate | Notes |
|------------------|----------------------|--------|
| 10 | 100% | Light load |
| 30 | 95-100% | Normal load |
| 50 | 90-100% | Heavy load |
| 100+ | May see timeouts | Stress test |

If success rate drops below 90%, consider:
- Increasing workers: `--workers 4` or `--workers 5`
- Adding threads: `--threads 2`
- Optimizing Google Sheets API calls

---

## Example: Complete Production Test

```bash
# SSH to production
ssh ec2-user@your-ec2-server

# Navigate to app directory
cd /home/ec2-user/rssb_sne_forms

# Run test with 30 concurrent users
python test_concurrent_submissions.py http://localhost:5000 30 blood_camp_user "ProductionPass123!"

# Expected output:
# ✓ Thread 0: Success! ID=BD4501, Time=0.8s
# ✓ Thread 1: Success! ID=BD4502, Time=0.9s
# ...
# 📊 TEST RESULTS
# Successful: 30
# Success Rate: 100.0%
# ✅ No duplicates found - race condition fix is working!

# Verify sheets
python verify_no_duplicates.py

# Clean up (if needed)
# Manually delete test entries from Google Sheets
```

---

## Troubleshooting

### High Failure Rate
```bash
# Increase timeout
gunicorn --timeout 180 ...

# Increase workers
gunicorn --workers 5 ...
```

### "Connection refused"
- Check Gunicorn is running: `ps aux | grep gunicorn`
- Check firewall: `sudo iptables -L`
- Check nginx is forwarding properly

### Slow Response Times
- Check Google Sheets API quota
- Check EC2 instance resources: `free -m`, `df -h`
- Consider upgrading EC2 instance type

---

## Safety Tips

⚠️ **Before testing production:**
1. Backup critical data
2. Test during low-traffic hours
3. Start with small numbers (10 users)
4. Monitor logs in real-time
5. Have a cleanup plan ready

✓ **Better approach:**
- Test on localhost while SSH'd into production server
- This tests the same infrastructure without external network issues
