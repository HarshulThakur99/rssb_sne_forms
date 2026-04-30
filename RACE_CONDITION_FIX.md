# Race Condition Fix - April 30, 2026

## Problem

Duplicate key errors were occurring when multiple users submitted forms simultaneously:
```
DETAIL: Key (badge_id)=(SNE-AX-150056) already exists.
```

The root cause was a race condition in the badge/donor ID generation logic where:
1. Two concurrent requests would query the database for the maximum ID
2. Both would get the same "next" ID
3. Both would try to insert with the same ID
4. The second one would fail with a duplicate key constraint violation

## Solution Implemented

### 1. Row-Level Locking (SELECT FOR UPDATE)

Modified ID generation functions to use `SELECT FOR UPDATE` to prevent concurrent transactions from reading the same maximum ID:

**Updated Functions:**
- `get_next_sne_badge_id_postgres()` - SNE badge ID generation
- `get_next_donor_id_postgres()` - Blood camp donor ID generation

**Changes:**
```python
# Before: Multiple queries could get same max ID
max_badge = db.session.query(func.max(SNEForm.badge_id)).filter(...).scalar()

# After: Row-level lock prevents race conditions
max_badge_row = db.session.query(SNEForm.badge_id).filter(...).order_by(
    SNEForm.badge_id.desc()
).with_for_update().first()
```

### 2. Enhanced Error Handling

Modified create functions to return detailed error information:

**Updated Functions:**
- `create_sne_form()` - Now returns `(object, success, error_msg)`
- `create_blood_donor()` - Now returns `(object, success, error_msg)`
- `create_attendant()` - Now returns `(object, success, error_msg)`

**Error Types Detected:**
- `DUPLICATE_BADGE_ID` / `DUPLICATE_DONOR_ID` - Retry with new ID
- `DUPLICATE_AADHAAR` - User error, no retry
- `INTEGRITY_ERROR` - Database constraint violation
- `DATABASE_ERROR` - General database error

### 3. Retry Logic

Added retry mechanism in submission routes to handle race conditions gracefully:

**Updated Routes:**
- `app/routes/sne_routes.py` - SNE form submission
- `app/routes/blood_camp_routes.py` - Blood camp submissions (2 locations)
- `app/routes/attendant_routes.py` - Attendant form submission

**Retry Strategy:**
- Maximum 3 attempts to generate unique ID
- If duplicate detected, generate new ID and retry
- Clear error messages if all retries fail
- Proper cleanup of uploaded S3 photos on failure

**Example Flow:**
```
Attempt 1: Generate ID → Insert → DUPLICATE_BADGE_ID error
Attempt 2: Generate new ID → Insert → DUPLICATE_BADGE_ID error
Attempt 3: Generate new ID → Insert → Success!
```

## Files Modified

1. **app/db_helpers.py** - ID generation and create functions
   - `get_next_sne_badge_id_postgres()` - Added SELECT FOR UPDATE
   - `get_next_donor_id_postgres()` - Added SELECT FOR UPDATE
   - `create_sne_form()` - Enhanced error handling
   - `create_blood_donor()` - Enhanced error handling
   - `create_attendant()` - Enhanced error handling

2. **app/routes/sne_routes.py** - SNE submission route
   - Added retry logic for badge ID generation
   - Added retry logic for database insertion
   - Better error messages

3. **app/routes/blood_camp_routes.py** - Blood camp routes
   - Added retry logic in 2 locations (new donor + repeat donation)
   - Better error handling
   - Proper S3 cleanup on failure

4. **app/routes/attendant_routes.py** - Attendant submission route
   - Updated to handle new 3-tuple return
   - Better error messages
   - Proper S3 cleanup on failure

## Benefits

1. **Prevents Duplicate IDs**: Row-level locking ensures unique ID generation
2. **Graceful Failure Recovery**: Retry logic handles race conditions automatically
3. **Better Error Messages**: Users get clear feedback on what went wrong
4. **Audit Trail**: Detailed logging of retry attempts and failures
5. **Resource Cleanup**: S3 photos properly deleted on failed submissions

## Testing

To verify the fix is working:

1. Run the concurrent submission test:
   ```powershell
   python test_concurrent_submissions.py
   ```

2. Check for:
   - 0 duplicate IDs generated
   - 100% success rate
   - No duplicate key errors in logs

3. Use Locust for heavy load testing:
   ```powershell
   locust -f locustfile.py --host=http://localhost:5000
   ```

## Database Transaction Behavior

The SELECT FOR UPDATE lock is held within a transaction:
- Lock acquired when badge ID is generated
- Lock released after successful insert OR rollback on error
- Other transactions wait for the lock to be released
- Prevents phantom reads and ensures serializability

## Performance Impact

Minimal:
- Lock held only during ID generation query
- Transaction is typically very short (< 100ms)
- Waiting transactions resume immediately after lock release
- Retry overhead only occurs in actual race conditions (rare)

## Monitoring

Watch for these log patterns to detect if race conditions still occur:

```
WARNING: Duplicate badge_id {id} detected (attempt {n}), generating new ID...
WARNING: Badge ID generation attempt {n} failed, retrying...
ERROR: Failed to insert after 3 attempts due to duplicate badge IDs
```

If these appear frequently, consider:
- Checking database transaction isolation level
- Verifying SELECT FOR UPDATE is working correctly
- Investigating concurrent load patterns
