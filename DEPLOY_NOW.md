# Race Condition Fix - Deployment Summary

## The Critical Issue

**Lalru and Malikpur Jaula were both getting SNE-AX-171074, 171075, 171076...**

This happened because each centre should have its **own independent sequence** within a designated range, but they were competing for the same IDs.

## Understanding the Design

Your system uses a **range-based design** where each centre has its own sequence:

```
Area: Mullanpur Garibdass (all use prefix SNE-AX-)
├── Lalru:          121001, 121002, 121003... (range: 121001-130999)
├── Malikpur Jaula: 131001, 131002, 131003... (range: 131001-140999)
└── Zirakpur:       171001, 171002, 171003... (range: 171001-180999)
```

**Each centre must stay in its own range!**

## What Was Wrong

1. **First Issue**: Race conditions - two users submitting simultaneously got the same ID
2. **First Fix Broke It**: Removed area/centre filtering, making all centres share IDs globally
   - Result: Lalru, Malikpur, and Zirakpur all competed for 171074, 171075, etc.
3. **Now Fixed**: Each centre has independent sequence with proper locking

## What Was Fixed

### Before (BROKEN):
```python
# All centres shared IDs globally
max_badge = query.filter(badge_id LIKE 'SNE-AX-%')
# Lalru gets: 171074
# Malikpur gets: 171075  ← WRONG! Should be in 131xxx range
# Zirakpur gets: 171076
```

### After (FIXED):
```python
# Each centre has own lock and sequence
lock_key = f"Mullanpur|Lalru|SNE-AX-"  # Unique lock per centre
max_badge = query.filter(
    area='Mullanpur', 
    centre='Lalru',
    badge_id LIKE 'SNE-AX-%'
)
# Lalru gets: 121074, 121075, 121076...    ✓ Correct range!
# Malikpur gets: 131074, 131075, 131076... ✓ Correct range!
# Zirakpur gets: 171074, 171075, 171076... ✓ Correct range!
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
| `app/db_helpers.py` | ✓ Added PostgreSQL advisory locks per area+centre<br>✓ Restored area/centre filtering (each centre has own sequence)<br>✓ Lock key includes area+centre+prefix for independence |
| `check_badge_ids.py` | ✓ NEW diagnostic tool - shows each centre's range and current IDs |
| `test_centre_sequences.py` | ✓ NEW test script - verifies ID generation per centre |
| `deploy_race_fix.sh` | ✓ NEW automated deployment |
| `CRITICAL_FIX_README.md` | ✓ Quick reference guide |
| `RACE_CONDITION_FIX.md` | ✓ Complete documentation |

## Test After Deployment

### 1. Check current badge sequences:
```bash
python3 check_badge_ids.py
```
Shows each centre's current badge ID and designated range.

### 2. Test ID generation:
```bash
python3 test_centre_sequences.py
```
Verifies each centre generates IDs in its correct range.

### 3. Submit test forms:
- Submit for Lalru → Should get 121xxx
- Submit for Malikpur Jaula → Should get 131xxx
- Submit for Zirakpur → Should get 171xxx

### 4. Verify logs:
```bash
sudo journalctl -u rssbsne.service -f
```
Look for: `Generated next SNE badge ID: SNE-AX-XXXXXX (area=..., centre=...)`

## Expected Results

### ✅ CORRECT (Each centre has own sequence):
```
Lalru User:
  Generated: SNE-AX-121074 (area=Mullanpur Garibdass, centre=Lalru)

Malikpur User (at same time):
  Generated: SNE-AX-131021 (area=Mullanpur Garibdass, centre=Malikpur Jaula)

Zirakpur User (at same time):
  Generated: SNE-AX-171075 (area=Mullanpur Garibdass, centre=Zirakpur)
```

### ❌ WRONG (All sharing same sequence):
```
All three users getting: 171074, 171075, 171076...
```

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
