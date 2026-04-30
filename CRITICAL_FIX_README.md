# CRITICAL FIX - Badge ID Duplicate Error

## The Problem

Your logs show that badge ID generation keeps returning **SNE-AX-150056** even though it already exists in the database. The retry logic attempts 3 times but generates the same ID each time, causing all attempts to fail.

## Root Cause

The original fix had **two critical issues**:

1. **Query was filtering by area AND centre**: This prevented the query from finding existing badge IDs if they had different area/centre values
2. **SELECT FOR UPDATE had nothing to lock**: If no rows matched the filter, there was no lock, allowing race conditions

## The Fix

### 1. PostgreSQL Advisory Locks
- Uses transaction-level locks that work even when no rows exist
- Ensures only ONE transaction generates IDs for each prefix at a time
- Automatically released when transaction completes

### 2. Global Badge ID Uniqueness  
- **REMOVED** area/centre filtering from badge ID queries
- Badge IDs are now globally unique across all areas/centres
- Query finds the true maximum badge ID regardless of area

## Quick Deployment (On EC2 Server)

```bash
cd /home/ec2-user/rssb_sne_forms

# 1. Check database state
python3 check_badge_ids.py

# 2. Deploy using automated script
chmod +x deploy_race_fix.sh
./deploy_race_fix.sh

# OR deploy manually:
# sudo systemctl restart rssbsne.service
# sudo journalctl -u rssbsne.service -f
```

## What to Expect After Deployment

### ✅ Success Indicators:
- Log shows: `Generated next SNE badge ID: SNE-AX-150057` (or next available)
- Log shows: `Created SNE form: SNE-AX-150057`
- Form submissions succeed
- No duplicate key errors

### ❌ If Still Failing:
- Check files were updated: `grep "pg_advisory_xact_lock" app/db_helpers.py`
- Check database: `python3 check_badge_ids.py`
- Review deployment steps in RACE_CONDITION_FIX.md

## Files Changed

1. **app/db_helpers.py** - Advisory locks + global badge ID queries
2. **check_badge_ids.py** - NEW: Diagnostic script
3. **deploy_race_fix.sh** - NEW: Automated deployment script
4. **RACE_CONDITION_FIX.md** - Complete documentation

## Why This Happened

Looking at your logs:
1. At 11:19:50 - Admin deleted SNE-AH-061060
2. At 11:19:55 - Admin deleted SNE-AX-011056  
3. At 11:20:30 - User tries to submit, gets SNE-AX-150056 (already exists)
4. System retries 3 times, keeps generating SNE-AX-150056
5. All retries fail because query doesn't find the existing badge_id

The query was looking for:
```sql
badge_id LIKE 'SNE-AX-15%' 
AND area = 'Mullanpur Garibdass' 
AND satsang_place = 'Malikpur Jaula'
```

But SNE-AX-150056 might have different area or satsang_place values, so it wasn't found.

## Testing After Deployment

1. **Try submitting a form** through the web interface
2. **Check logs**: Should see next sequential badge ID (150057 or higher)
3. **Run diagnostic**: `python3 check_badge_ids.py`

## Rollback (if needed)

```bash
sudo systemctl stop rssbsne.service
rm -rf app
cp -r app_backup_YYYYMMDD_HHMMSS app
sudo systemctl start rssbsne.service
```

## Questions?

- See detailed documentation: **RACE_CONDITION_FIX.md**
- Check database state: `python3 check_badge_ids.py`
- Monitor logs: `sudo journalctl -u rssbsne.service -f`
