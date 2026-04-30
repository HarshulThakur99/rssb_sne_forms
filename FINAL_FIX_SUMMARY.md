# FINAL FIX - Badge ID Race Condition

## Problem Statement

**Issue 1**: Lalru and Malikpur Jaula were both getting SNE-AX-171074, 171075, 171076 series

**Issue 2**: Duplicate key errors when multiple users submit forms simultaneously

## Root Cause Analysis

Your system uses a **range-based design** where each centre has a designated range:

```
Mullanpur Garibdass Area (all use prefix SNE-AX-)
├── Lalru:          121001-130999 (10,000 IDs)
├── Malikpur Jaula: 131001-140999 (10,000 IDs)  
└── Zirakpur:       171001-180999 (10,000 IDs)
```

### What Went Wrong (Timeline)

1. **Original Code**: Used area+centre filtering but no proper locking
   - Race condition: Two concurrent users → same ID → duplicate error

2. **First Fix Attempt**: Added locking but removed area+centre filtering
   - Made badge IDs globally unique across all centres
   - Broke range-based design
   - Result: All centres competed for same sequence (171074, 171075...)

3. **Final Fix**: Advisory locks WITH area+centre filtering restored
   - Each centre gets its own independent lock
   - Each centre maintains its own sequence within designated range
   - Different centres can generate IDs concurrently without blocking

## The Solution

### Key Change in app/db_helpers.py

```python
def get_next_sne_badge_id_postgres(area, centre, prefix, start_num):
    # Lock is unique per area+centre+prefix combination
    lock_key = f"{area}|{centre}|{prefix}"
    lock_id = abs(hash(lock_key)) % (2**31)
    
    # Acquire advisory lock (transaction-scoped)
    db.session.execute(text(f"SELECT pg_advisory_xact_lock({lock_id})"))
    
    # Query filters by area+centre to stay within designated range
    max_badge_row = db.session.query(SNEForm.badge_id).filter(
        and_(
            SNEForm.area == area,
            SNEForm.satsang_place == centre,
            SNEForm.badge_id.like(f"{prefix}%")
        )
    ).order_by(SNEForm.badge_id.desc()).first()
    
    # Generate next ID in sequence...
```

### How It Works

**Scenario: Three users submit simultaneously**

```
┌─────────────────────┬──────────────────────┬─────────────────────┐
│   Lalru User        │  Malikpur User       │   Zirakpur User     │
├─────────────────────┼──────────────────────┼─────────────────────┤
│ Lock: Lalru+SNE-AX  │ Lock: Malikpur+SNE-AX│ Lock: Zirakpur+SNE-AX│
│   ✓ Acquired        │   ✓ Acquired         │   ✓ Acquired        │
│                     │                      │                     │
│ Query: area=Mul     │ Query: area=Mul      │ Query: area=Mul     │
│   centre=Lalru      │   centre=Malikpur    │   centre=Zirakpur   │
│   prefix=SNE-AX-    │   prefix=SNE-AX-     │   prefix=SNE-AX-    │
│                     │                      │                     │
│ Max: 121050         │ Max: 131020          │ Max: 171074         │
│ Generate: 121051 ✓  │ Generate: 131021 ✓   │ Generate: 171075 ✓  │
│                     │                      │                     │
│ All three run concurrently without blocking each other!        │
└────────────────────────────────────────────────────────────────┘
```

**Scenario: Two users submit to SAME centre**

```
┌─────────────────────┬─────────────────────┐
│   Lalru User A      │   Lalru User B      │
├─────────────────────┼─────────────────────┤
│ Lock: Lalru+SNE-AX  │ Lock: Lalru+SNE-AX  │
│   ✓ Acquired        │   ⏳ Waiting...      │
│                     │                     │
│ Query max: 121050   │   ⏳ Waiting...      │
│ Generate: 121051    │   ⏳ Waiting...      │
│ INSERT 121051 ✓     │   ⏳ Waiting...      │
│ COMMIT (release)    │   ✓ Lock acquired   │
│                     │ Query max: 121051   │
│                     │ Generate: 121052 ✓  │
│                     │ INSERT 121052 ✓     │
└─────────────────────┴─────────────────────┘
```

## Benefits

1. ✅ **No more duplicate badge IDs** - Advisory locks prevent race conditions
2. ✅ **Each centre has own sequence** - Lalru gets 121xxx, Malikpur gets 131xxx
3. ✅ **Concurrent submissions work** - Different centres don't block each other
4. ✅ **Range-based design preserved** - Each centre stays within designated range
5. ✅ **Zero performance impact** - Locks only serialize same-centre submissions

## Deployment

### On EC2 Server:

```bash
cd /home/ec2-user/rssb_sne_forms

# 1. Check current state
python3 check_badge_ids.py

# 2. Test the fix
python3 test_centre_sequences.py

# 3. Deploy
sudo systemctl restart rssbsne.service

# 4. Monitor
sudo journalctl -u rssbsne.service -f
```

### Verify Success:

After deployment, each centre should generate IDs in its designated range:
- Lalru submissions → 121xxx series
- Malikpur submissions → 131xxx series
- Zirakpur submissions → 171xxx series

## Files Modified

- `app/db_helpers.py` - Advisory lock implementation with area+centre filtering
- `check_badge_ids.py` - NEW: Diagnostic tool showing each centre's range and IDs
- `test_centre_sequences.py` - NEW: Test script to verify ID generation per centre
- `RACE_CONDITION_FIX.md` - Complete technical documentation
- `DEPLOY_NOW.md` - Quick deployment guide

## Testing Commands

```bash
# Check current badge IDs by centre
python3 check_badge_ids.py

# Test ID generation
python3 test_centre_sequences.py

# Monitor logs after deployment
sudo journalctl -u rssbsne.service -f

# Query database directly
psql -U your_user -d your_db -c "
  SELECT badge_id, area, satsang_place 
  FROM sne_forms 
  WHERE badge_id LIKE 'SNE-AX-%' 
  ORDER BY badge_id DESC LIMIT 10;
"
```

## Success Criteria

✅ Lalru generates IDs in 121001-130999 range  
✅ Malikpur Jaula generates IDs in 131001-140999 range  
✅ Zirakpur generates IDs in 171001-180999 range  
✅ No duplicate badge ID errors in logs  
✅ Multiple concurrent submissions all succeed  
✅ Each centre's sequence is independent  

## Troubleshooting

**Q: Still seeing centres share IDs?**  
A: Check `grep "pg_advisory_xact_lock" app/db_helpers.py` - should show advisory lock code  
A: Verify service restarted: `sudo systemctl status rssbsne.service`

**Q: Duplicate badge ID errors?**  
A: Check database: `python3 check_badge_ids.py`  
A: May need to manually fix any out-of-range badges  

**Q: Slow form submissions?**  
A: Normal if many users submit to same centre (serialized for safety)  
A: Different centres submit in parallel (no slowdown)

## Technical Notes

- **Advisory Lock ID**: Computed as `hash(f"{area}|{centre}|{prefix}") % (2^31)`
- **Lock Scope**: Transaction-scoped (automatically released on commit/rollback)
- **Lock Type**: PostgreSQL advisory exclusive lock (`pg_advisory_xact_lock`)
- **Concurrency**: Different centres = parallel, same centre = serialized
- **Badge Format**: `{prefix}{number:06d}` (e.g., SNE-AX-121051)

---

**For complete documentation, see RACE_CONDITION_FIX.md**
