# 🎯 Your Exact Migration Commands

**Database Details:**
- **Endpoint**: `rssb-database.cvwce2ik6hx7.ap-south-1.rds.amazonaws.com`
- **Port**: `5432`
- **Database Name**: `postgres`
- **Username**: `postgres`
- **Region**: `ap-south-1` (Mumbai)
- **Instance**: `db.t4g.micro`

**EC2 Instance:**
- **IP**: `43.205.30.101`
- **Instance Type**: `t2.micro`

---

## 🚀 Copy-Paste These Exact Commands

### Step 1: SSH into EC2

```bash
ssh -i your-key.pem ec2-user@43.205.30.101
```
> ⚠️ **Replace `your-key.pem` with your actual SSH key filename**

---

### Step 2: Backup PostgreSQL Database

```bash
# Create backup directory
mkdir -p ~/backups

# Backup database (SQL format)
pg_dump -h rssb-database.cvwce2ik6hx7.ap-south-1.rds.amazonaws.com \
        -U postgres \
        -d postgres \
        -f ~/backups/postgres_backup_$(date +%Y%m%d).sql

# Enter password when prompted
```

**Verify backup:**
```bash
ls -lh ~/backups/
```

**Optional: Create compressed backup (faster restore)**
```bash
pg_dump -h rssb-database.cvwce2ik6hx7.ap-south-1.rds.amazonaws.com \
        -U postgres \
        -d postgres \
        -F c \
        -f ~/backups/postgres_backup_$(date +%Y%m%d).dump
```

---

### Step 3: Update Your .env File

**Check your current database environment variables:**
```bash
cd /home/ec2-user/rssb_sne_forms  # Adjust if your path is different
cat .env | grep DB_
```

**You should see something like:**
```
DB_HOST=rssb-database.cvwce2ik6hx7.ap-south-1.rds.amazonaws.com
DB_PORT=5432
DB_NAME=postgres
DB_USER=postgres
DB_PASSWORD=your_password
```

**If these are NOT set, add them now:**
```bash
nano .env

# Add these lines if missing:
DB_HOST=rssb-database.cvwce2ik6hx7.ap-south-1.rds.amazonaws.com
DB_PORT=5432
DB_NAME=postgres
DB_USER=postgres
DB_PASSWORD=YOUR_ACTUAL_PASSWORD_HERE
```

---

### Step 4: Upload Migration Files to EC2

**From your LOCAL machine (Windows PowerShell)**, upload the new files:

```powershell
# Navigate to your local project folder
cd C:\Users\RST\rssb_sne_forms

# Upload migration script
scp -i your-key.pem scripts/migrate_postgres_to_sqlite.py ec2-user@43.205.30.101:/home/ec2-user/rssb_sne_forms/scripts/

# Upload updated database.py
scp -i your-key.pem app/database.py ec2-user@43.205.30.101:/home/ec2-user/rssb_sne_forms/app/

# Upload guides
scp -i your-key.pem SQLITE_MIGRATION_GUIDE.md ec2-user@43.205.30.101:/home/ec2-user/rssb_sne_forms/
scp -i your-key.pem QUICKSTART_SQLITE.md ec2-user@43.205.30.101:/home/ec2-user/rssb_sne_forms/
```

> ⚠️ **Adjust paths if your EC2 app directory is different**

---

### Step 5: Run Migration Script

**Back on EC2:**
```bash
cd /home/ec2-user/rssb_sne_forms

# Run the migration
python3 scripts/migrate_postgres_to_sqlite.py
```

**When prompted, press Enter to continue**

**Expected output:**
```
✅ Migration completed successfully!

📝 Next steps:
   1. Update your .env file to use SQLite
   2. Test your application thoroughly
   3. Once verified, delete RDS instance
```

---

### Step 6: Enable SQLite Mode

```bash
# Edit .env file
nano .env

# Add this line at the TOP of the file:
USE_SQLITE=true

# Save and exit (Ctrl+X, then Y, then Enter)
```

**Verify it's set:**
```bash
grep USE_SQLITE .env
```

Should show: `USE_SQLITE=true`

---

### Step 7: Restart Your Application

**Find current process:**
```bash
ps aux | grep gunicorn
ps aux | grep python
```

**Kill the process (replace <PID> with actual number):**
```bash
sudo kill <PID>
```

**Or if using systemd:**
```bash
# List services
sudo systemctl list-units --type=service | grep -i rssb

# Restart service (replace with your actual service name)
sudo systemctl restart rssb-sne-forms
```

**Or start manually:**
```bash
cd /home/ec2-user/rssb_sne_forms
nohup gunicorn -w 4 -b 0.0.0.0:5000 run:app > nohup.out 2>&1 &
```

---

### Step 8: Test Your Application

**Open in browser:**
```
http://43.205.30.101:5000
```

**Or with your domain if you have one set up**

**Test these features:**
- [ ] Login works
- [ ] Submit SNE form
- [ ] Submit blood camp form
- [ ] View existing data in database viewer
- [ ] Generate a badge
- [ ] Upload photo

**Check SQLite database directly:**
```bash
cd /home/ec2-user/rssb_sne_forms

# View database
sqlite3 instance/rssbsne.db

# Run queries
SELECT COUNT(*) FROM sne_forms;
SELECT COUNT(*) FROM blood_camp_donors;
SELECT COUNT(*) FROM attendants;

# See sample data
SELECT badge_id, first_name, last_name FROM sne_forms LIMIT 5;

# Exit
.quit
```

---

### Step 9: Monitor Application Logs

```bash
# If using nohup
tail -f nohup.out

# If using systemd
sudo journalctl -u rssb-sne-forms -f

# Check for errors
grep -i error nohup.out
```

**Monitor for 24-48 hours** and ensure everything works correctly.

---

### Step 10: Delete RDS Instance (After Verification)

**Via AWS Console:**
1. Go to: https://console.aws.amazon.com/rds/
2. Select **rssb-database**
3. Click **Actions** → **Delete**
4. Choose **Create final snapshot**
   - Snapshot name: `rssb-database-final-snapshot-20260603`
5. Type `delete me` in the confirmation box
6. Click **Delete DB Instance**

**Via AWS CLI:**
```bash
# Create final snapshot and delete
aws rds delete-db-instance \
    --db-instance-identifier rssb-database \
    --final-db-snapshot-identifier rssb-database-final-snapshot-$(date +%Y%m%d) \
    --region ap-south-1

# Or delete without snapshot (only if you're 100% sure)
aws rds delete-db-instance \
    --db-instance-identifier rssb-database \
    --skip-final-snapshot \
    --region ap-south-1
```

**Verify deletion:**
```bash
aws rds describe-db-instances \
    --db-instance-identifier rssb-database \
    --region ap-south-1
```

---

## 🔄 Rollback Commands (If Needed)

**If something goes wrong, quickly rollback:**

```bash
# 1. Edit .env
nano .env

# 2. Change or comment out:
# USE_SQLITE=false
# or just delete the USE_SQLITE line

# 3. Restart app
sudo systemctl restart rssb-sne-forms
# or
sudo kill <PID> && nohup gunicorn -w 4 -b 0.0.0.0:5000 run:app > nohup.out 2>&1 &

# App will reconnect to PostgreSQL RDS
```

---

## 🧪 Troubleshooting Commands

**Test PostgreSQL connection:**
```bash
psql -h rssb-database.cvwce2ik6hx7.ap-south-1.rds.amazonaws.com \
     -U postgres \
     -d postgres \
     -c "SELECT version();"
```

**Check if migration created SQLite file:**
```bash
ls -lh instance/rssbsne.db
```

**Check SQLite file permissions:**
```bash
chmod 664 instance/rssbsne.db
ls -l instance/rssbsne.db
```

**View environment variables:**
```bash
cat .env | grep -E "DB_|USE_SQLITE"
```

**Check Python can load environment:**
```bash
python3 -c "from dotenv import load_dotenv; import os; load_dotenv(); print('DB_HOST:', os.getenv('DB_HOST')); print('USE_SQLITE:', os.getenv('USE_SQLITE'))"
```

**Test migration script dependencies:**
```bash
python3 -c "import sqlalchemy, psycopg2; print('Dependencies OK')"
```

---

## 📊 Verify Cost Savings

**After deleting RDS, check your AWS bill:**
1. Go to: https://console.aws.amazon.com/billing/
2. Navigate to **Bills** → Current month
3. Look for **Amazon RDS** charges
4. Should drop from ~$21/month to $0

**Expected new monthly cost:**
- EC2 t2.micro: $9.96
- EBS 8GB: $0.73
- IPv4 Address: $3.72
- **Total: ~$14.41/month** (down from $37.66)

**Savings: $23.25/month = $279/year** 🎉

---

## 🔐 Security Reminder

**Your .env file contains sensitive information:**
```bash
# Check file permissions
ls -l .env

# Should be 600 or 644 (not world-readable)
chmod 600 .env
```

**Never commit .env to Git:**
```bash
# Verify .env is in .gitignore
grep -F ".env" .gitignore
```

---

## 📝 Post-Migration Checklist

- [ ] PostgreSQL backup created ✓
- [ ] Migration script completed successfully ✓
- [ ] .env updated with `USE_SQLITE=true` ✓
- [ ] Application restarted ✓
- [ ] All features tested and working ✓
- [ ] No errors in logs for 48 hours ✓
- [ ] RDS instance deleted ✓
- [ ] AWS bill reduced next month ✓
- [ ] SQLite backup strategy implemented ✓

---

## 💾 Ongoing Maintenance

**Weekly SQLite backup to S3:**
```bash
# Manual backup
aws s3 cp instance/rssbsne.db s3://rssbsne/backups/db_backup_$(date +%Y%m%d).db

# Or set up automated backup (add to cron)
crontab -e

# Add this line (runs every Sunday at 2 AM):
0 2 * * 0 cd /home/ec2-user/rssb_sne_forms && aws s3 cp instance/rssbsne.db s3://rssbsne/backups/db_backup_$(date +\%Y\%m\%d).db
```

**Monthly database optimization:**
```bash
cd /home/ec2-user/rssb_sne_forms
sqlite3 instance/rssbsne.db "VACUUM; ANALYZE;"
```

---

## 🆘 Emergency Contacts

**If you need to restore from backup:**
```bash
# Restore from local backup
cp ~/backups/postgres_backup_YYYYMMDD.sql ~/restore.sql

# Or restore to a new RDS instance if needed
# (Follow AWS RDS restore documentation)
```

**Quick health check command:**
```bash
curl http://43.205.30.101:5000/health || echo "App is down!"
```

---

## ✅ You're Done!

**Congratulations!** You've successfully:
- ✅ Migrated from PostgreSQL to SQLite
- ✅ Saved $23.25/month ($279/year)
- ✅ Simplified your infrastructure
- ✅ Maintained full functionality

**Your new AWS cost: $14.41/month** 🎉

Keep the PostgreSQL backup for 30 days, then delete it if everything is working perfectly!
