# Race Condition Fix - Deployment Summary

## The Critical Issue

Your logs show the system **keeps generating the same badge ID (SNE-AX-150056)** even though it already exists, causing all 3 retry attempts to fail with duplicate key errors.

## Why You Can Submit But Others Can't

- **You're submitting to different areas/centres** - Your SNE-AH-061060 uses a different prefix (AH vs AX)
- **The other user hits SNE-AX-150056** which already exists in the database
- **The query can't find it** because it was filtering by area+centre, preventing proper max ID detection

## What Was Fixed

### Before (BROKEN):
```python
# Query filtered by area + centre - couldn't find existing IDs
max_badge = query.filter(
    area == 'Mullanpur Garibdass',
    satsang_place == 'Malikpur Jaula', 
    badge_id LIKE 'SNE-AX-15%'
)
# If no match → returns SNE-AX-150056 again → DUPLICATE ERROR
```

### After (FIXED):
```python
# PostgreSQL advisory lock acquired FIRST
SELECT pg_advisory_xact_lock(12345)

# Query only filters by prefix - finds ALL badge IDs globally
max_badge = query.filter(badge_id LIKE 'SNE-AX-15%')
# Finds existing SNE-AX-150056 → returns SNE-AX-150057 ✓
```

## Deploy on EC2 Server NOW

```bash
ssh ec2-user@your-server
cd /home/ec2-user/rssb_sne_forms

# Step 1: Check what badge IDs exist
python3 check_badge_ids.py

# Step 2: Deploy the fix (automated)
chmod +x deploy_race_fix.sh
./deploy_race_fix.sh

# OR deploy manually:
sudo systemctl restart rssbsne.service
sudo journalctl -u rssbsne.service -f
```

## What You'll See After Fix

### ✅ GOOD (Fixed):
```
Generated next SNE badge ID: SNE-AX-150057
Created SNE form: SNE-AX-150057
Successfully added SNE data to PostgreSQL for Badge ID: SNE-AX-150057
```

### ❌ BAD (Still Broken):
```
Generated next SNE badge ID: SNE-AX-150056
Duplicate badge_id error for SNE-AX-150056
```

## Files Modified

| File | What Changed |
|------|--------------|
| `app/db_helpers.py` | ✓ Added PostgreSQL advisory locks<br>✓ Removed area/centre filtering<br>✓ Global badge ID uniqueness |
| `check_badge_ids.py` | ✓ NEW diagnostic tool |
| `deploy_race_fix.sh` | ✓ NEW automated deployment |
| `CRITICAL_FIX_README.md` | ✓ Quick reference guide |
| `RACE_CONDITION_FIX.md` | ✓ Complete documentation |

## Test After Deployment

1. Have the other user try submitting again
2. Check logs: `sudo journalctl -u rssbsne.service -f`
3. Verify: `python3 check_badge_ids.py`

## Why Advisory Locks Work

```
User A submits form          User B submits form
↓                            ↓
Lock acquired (A waits)      Lock acquired (B waits for A)
↓                            ↓
Query: max = 150056          (waiting...)
Generate: 150057             (waiting...)
Insert: 150057 SUCCESS       (waiting...)
Lock released                Lock acquired ✓
                             Query: max = 150057
                             Generate: 150058 ✓
                             Insert: 150058 SUCCESS
                             Lock released
```

**Result**: No duplicates, even with 100 concurrent users!

## Need Help?

- **Full docs**: See RACE_CONDITION_FIX.md
- **Quick start**: See CRITICAL_FIX_README.md  
- **Diagnostic**: Run `python3 check_badge_ids.py`
- **Logs**: Run `sudo journalctl -u rssbsne.service -f`
