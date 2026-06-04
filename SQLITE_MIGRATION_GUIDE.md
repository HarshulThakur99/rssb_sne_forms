# RDS PostgreSQL to SQLite Migration Guide

## 💰 Cost Savings: $18.24/month → $0 (Eliminate RDS costs)

This guide will help you migrate from AWS RDS PostgreSQL to SQLite, reducing your monthly AWS bill from $37.66 to ~$13-15.

---

## 📋 Pre-Migration Checklist

- [ ] Current RDS database is accessible
- [ ] You have SSH access to your EC2 instance
- [ ] All environment variables are documented
- [ ] You have at least 1GB free disk space on EC2
- [ ] Application is tested and working on current PostgreSQL setup

---

## 🚀 Migration Steps

### **Step 1: Backup PostgreSQL Database (CRITICAL)**

#### On your local machine or EC2:

```bash
# SSH into your EC2 instance
ssh -i your-key.pem ec2-user@43.205.30.101

# Create backups directory
mkdir -p ~/backups

# Backup PostgreSQL database (plain SQL format)
pg_dump -h rssb-database.cvwce2ik6hx7.ap-south-1.rds.amazonaws.com -U postgres -d postgres -F p -f ~/backups/postgres_backup_$(date +%Y%m%d_%H%M%S).sql

# Also backup as compressed format (recommended for faster restore)
pg_dump -h rssb-database.cvwce2ik6hx7.ap-south-1.rds.amazonaws.com -U postgres -d postgres -F c -f ~/backups/postgres_backup_$(date +%Y%m%d_%H%M%S).dump

# Verify backup was created
ls -lh ~/backups/

# When prompted, enter your PostgreSQL password
```

#### Optional: Download backup to your local machine
```bash
# From your local machine
scp -i your-key.pem ec2-user@43.205.30.101:~/backups/*.sql ~/local-backups/
```

---

### **Step 2: Update Your Application Code**

#### On EC2, pull the latest code with migration script:

```bash
cd /path/to/rssb_sne_forms

# Pull the latest changes (with migration script)
git pull origin main

# Or if you're uploading manually, ensure these files are updated:
# - scripts/migrate_postgres_to_sqlite.py
# - app/database.py
```

---

### **Step 3: Run Migration Script**

```bash
cd /path/to/rssb_sne_forms

# Ensure your .env file has PostgreSQL credentials
# The script will read from these environment variables

# Run the migration script
python3 scripts/migrate_postgres_to_sqlite.py
```

**The script will:**
1. Connect to PostgreSQL
2. Create SQLite database in `instance/rssbsne.db`
3. Copy all data from PostgreSQL to SQLite
4. Verify data integrity
5. Show migration summary

**Expected output:**
```
======================================================================
PostgreSQL to SQLite Migration Script
======================================================================

📊 Source: PostgreSQL (RDS)
📊 Target: /path/to/instance/rssbsne.db

🔌 Connecting to databases...
   ✅ Connected to PostgreSQL
   ✅ Connected to SQLite

🏗️  Creating SQLite schema...
   ✅ Schema created successfully

🚀 Starting data migration...

📋 Migrating SNE Forms...
   Found 150 records in PostgreSQL
   ✅ Successfully migrated 150 records

📋 Migrating Blood Camp Donors...
   Found 89 records in PostgreSQL
   ✅ Successfully migrated 89 records

📋 Migrating Attendants...
   Found 45 records in PostgreSQL
   ✅ Successfully migrated 45 records

🔍 Verifying migration...
   ✅ SNEForm: 150 records match
   ✅ BloodCampDonor: 89 records match
   ✅ Attendant: 45 records match

======================================================================
MIGRATION SUMMARY
======================================================================
✅ SNE Forms: 150 / 150 records
✅ Blood Camp Donors: 89 / 89 records
✅ Attendants: 45 / 45 records

======================================================================
✅ Migration completed successfully!

📝 Next steps:
   1. Update your .env file to use SQLite:
      Add: USE_SQLITE=true
   2. Test your application thoroughly
   3. Once verified, delete RDS instance to save $18/month
   4. Keep PostgreSQL backup for rollback if needed
======================================================================
```

---

### **Step 4: Update Environment Variables**

Edit your `.env` file on EC2:

```bash
nano .env
```

**Add this line at the top:**
```bash
USE_SQLITE=true
```

**Your .env should now look like:**
```bash
USE_SQLITE=true

# Keep these for reference (not used when USE_SQLITE=true)
# DB_HOST=rssb-database.xxxxx.ap-south-1.rds.amazonaws.com
# DB_PORT=5432
# DB_NAME=rssbsne
# DB_USER=postgres
# DB_PASSWORD=your_password

# Other existing variables
SECRET_KEY=your_secret_key
S3_BUCKET_NAME=rssbsne
# ... etc
```

---

### **Step 5: Restart Your Application**

```bash
# Find your Gunicorn process
ps aux | grep gunicorn

# Kill the process (replace <PID> with actual process ID)
sudo kill <PID>

# Or if using systemd
sudo systemctl restart your-app-name

# Or restart manually
cd /path/to/rssb_sne_forms
gunicorn -w 4 -b 0.0.0.0:5000 run:app
```

---

### **Step 6: Test Your Application**

Open your browser and test all functionality:

- [ ] Login works
- [ ] SNE form submission works
- [ ] Blood camp form submission works
- [ ] Attendant form submission works
- [ ] Badge generation works
- [ ] Database viewer shows data
- [ ] Photo uploads work (S3)
- [ ] All existing data is visible

**Run some test queries:**
```bash
# SSH into EC2
cd /path/to/rssb_sne_forms

# Open SQLite database
sqlite3 instance/rssbsne.db

# Check record counts
SELECT COUNT(*) FROM sne_forms;
SELECT COUNT(*) FROM blood_camp_donors;
SELECT COUNT(*) FROM attendants;

# Check sample data
SELECT badge_id, first_name, last_name FROM sne_forms LIMIT 5;

# Exit SQLite
.quit
```

---

### **Step 7: Monitor for 24-48 Hours**

Keep your application running on SQLite for 1-2 days while monitoring:

- [ ] No errors in application logs
- [ ] Forms are submitting successfully
- [ ] Data is being saved correctly
- [ ] No performance issues
- [ ] All features working as expected

**Check logs:**
```bash
# If using systemd
sudo journalctl -u your-app-name -f

# Or check application logs
tail -f /var/log/your-app/app.log
```

---

### **Step 8: Delete RDS Instance (Save $18.24/month)**

⚠️ **ONLY DO THIS AFTER CONFIRMING SQLITE IS WORKING PERFECTLY**

#### Option A: Create Final Snapshot (Recommended)

```bash
# Using AWS CLI
aws rds create-db-snapshot \
    --db-instance-identifier rssb-database \
    --db-snapshot-identifier rssb-database-final-snapshot-$(date +%Y%m%d)

# Wait for snapshot to complete
aws rds describe-db-snapshots \
    --db-snapshot-identifier rssb-database-final-snapshot-$(date +%Y%m%d)
```

#### Option B: Delete Without Snapshot (After you're 100% confident)

```bash
# Delete RDS instance
aws rds delete-db-instance \
    --db-instance-identifier rssb-database \
    --skip-final-snapshot

# Confirm deletion
aws rds describe-db-instances --db-instance-identifier rssb-database
```

#### Via AWS Console:
1. Go to AWS RDS Console
2. Select `rssb-database`
3. Click **Actions** → **Delete**
4. Choose whether to create final snapshot
5. Type "delete me" to confirm
6. Click **Delete**

---

## 📊 Expected Cost Savings

| Item | Before (PostgreSQL) | After (SQLite) | Savings |
|------|---------------------|----------------|---------|
| **RDS db.t4g.micro** | $18.24/month | $0 | $18.24 |
| **RDS Storage 20GB** | $2.62/month | $0 | $2.62 |
| **EC2 t2.micro** | $9.96/month | $9.96/month | $0 |
| **EBS 8GB** | $0.73/month | $0.73/month | $0 |
| **IPv4 Address** | $3.72/month | $3.72/month | $0 |
| **TOTAL** | **$35.27/month** | **$14.41/month** | **$20.86/month** |

**Annual Savings: $250.32/year**

---

## 🔄 Rollback Plan (If Something Goes Wrong)

### Option 1: Quick Rollback (Use PostgreSQL Backup)

```bash
# SSH into EC2
cd /path/to/rssb_sne_forms

# Update .env to use PostgreSQL again
nano .env
# Change: USE_SQLITE=false (or remove the line)

# Restart application
sudo systemctl restart your-app-name

# Your PostgreSQL RDS should still be running
# Application will reconnect to RDS
```

### Option 2: Restore from Snapshot

```bash
# Restore RDS from snapshot
aws rds restore-db-instance-from-db-snapshot \
    --db-instance-identifier rssb-database-restored \
    --db-snapshot-identifier rssb-database-final-snapshot-YYYYMMDD

# Update .env with new RDS endpoint
# Change USE_SQLITE=false
# Restart application
```

### Option 3: Import Backup to New RDS

```bash
# Create new RDS instance
# Restore from .sql backup file
psql -h new-rds-endpoint -U postgres -d rssbsne -f ~/backups/postgres_backup_YYYYMMDD.sql

# Update .env with new RDS endpoint
# Restart application
```

---

## 📝 SQLite Maintenance Tips

### **1. Regular Backups**

Create a cron job to backup SQLite database:

```bash
# Edit crontab
crontab -e

# Add daily backup at 2 AM
0 2 * * * cd /path/to/rssb_sne_forms && cp instance/rssbsne.db ~/backups/rssbsne_backup_$(date +\%Y\%m\%d).db

# Keep only last 30 days of backups
0 3 * * * find ~/backups/ -name "rssbsne_backup_*.db" -mtime +30 -delete
```

### **2. Optimize Database Periodically**

```bash
# Run monthly (improves performance)
sqlite3 instance/rssbsne.db "VACUUM;"
sqlite3 instance/rssbsne.db "ANALYZE;"
```

### **3. Monitor Disk Space**

```bash
# Check database size
ls -lh instance/rssbsne.db

# Check EC2 disk space
df -h
```

### **4. Upload Backups to S3 (Optional)**

```bash
# Upload daily backup to S3
aws s3 cp instance/rssbsne.db s3://rssbsne/backups/db_backup_$(date +%Y%m%d).db

# Or add to cron for automatic backups
0 2 * * * aws s3 cp /path/to/instance/rssbsne.db s3://rssbsne/backups/db_backup_$(date +\%Y\%m\%d).db
```

---

## ❓ Troubleshooting

### **Issue: Migration script fails with connection error**

**Solution:**
```bash
# Check PostgreSQL connection
psql -h rssb-database.cvwce2ik6hx7.ap-south-1.rds.amazonaws.com -U postgres -d postgres -c "SELECT version();"

# Verify environment variables
echo $DB_HOST
echo $DB_NAME
echo $DB_USER

# Check if .env file is loaded
python3 -c "from dotenv import load_dotenv; import os; load_dotenv(); print(os.environ.get('DB_HOST'))"
```

### **Issue: Application can't find SQLite database**

**Solution:**
```bash
# Check if database file exists
ls -l instance/rssbsne.db

# Check permissions
chmod 664 instance/rssbsne.db
chown your-user:your-group instance/rssbsne.db

# Verify USE_SQLITE is set
grep USE_SQLITE .env
```

### **Issue: Some data is missing after migration**

**Solution:**
```bash
# Re-run migration script
python3 scripts/migrate_postgres_to_sqlite.py

# Or restore specific table from PostgreSQL
python3 -c "
from sqlalchemy import create_engine
from app.models import SNEForm, db

# Connect to both databases
pg_engine = create_engine('postgresql://...')
sqlite_engine = create_engine('sqlite:///instance/rssbsne.db')

# Migrate specific model
# ... (truncate and re-import)
"
```

### **Issue: Application slower after migration**

**Solution:**
```bash
# Optimize SQLite database
sqlite3 instance/rssbsne.db "VACUUM;"
sqlite3 instance/rssbsne.db "ANALYZE;"

# Check indexes
sqlite3 instance/rssbsne.db ".indexes"

# Enable WAL mode for better concurrency
sqlite3 instance/rssbsne.db "PRAGMA journal_mode=WAL;"
```

---

## ✅ Post-Migration Checklist

- [ ] Migration completed successfully
- [ ] All data verified in SQLite
- [ ] Application tested thoroughly
- [ ] No errors in logs
- [ ] Performance is acceptable
- [ ] Backup strategy implemented
- [ ] RDS instance deleted (after confirmation period)
- [ ] Final PostgreSQL backup stored safely
- [ ] Cost savings confirmed in next AWS bill
- [ ] Documentation updated

---

## 🎯 Summary

By migrating from RDS PostgreSQL to SQLite, you will:

✅ **Save $20.86/month ($250/year)**  
✅ **Simplify infrastructure** (no external database)  
✅ **Maintain all functionality** (SQLite handles your traffic easily)  
✅ **Keep data secure** (regular backups to S3)  
✅ **Retain rollback option** (PostgreSQL backups)  

For your use case (1-2 users/day, occasional spikes), SQLite is the perfect solution.

---

## 📞 Need Help?

If you encounter any issues during migration:
1. Check the troubleshooting section above
2. Review application logs
3. Verify environment variables
4. Test database connection manually
5. If needed, rollback to PostgreSQL immediately

**Remember:** Keep PostgreSQL backup for at least 30 days before deleting permanently!
