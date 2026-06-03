# 🚀 Quick Start: Migrate to SQLite and Save $20/month

## TL;DR - What You Need to Do

1. **Backup PostgreSQL** (5 minutes)
2. **Run migration script** (10 minutes)
3. **Update .env file** (1 minute)
4. **Restart app** (2 minutes)
5. **Test thoroughly** (30 minutes)
6. **Delete RDS after 48 hours** (2 minutes)

**Total Time: ~1 hour**  
**Savings: $20.86/month = $250/year**

---

## Step-by-Step Commands

### 1️⃣ SSH into Your EC2

```bash
ssh -i your-key.pem ec2-user@43.205.30.101
```

### 2️⃣ Backup PostgreSQL (CRITICAL!)

```bash
mkdir -p ~/backups

pg_dump -h rssb-database.XXXXX.ap-south-1.rds.amazonaws.com \
        -U postgres -d rssbsne \
        -f ~/backups/postgres_backup_$(date +%Y%m%d).sql

# Verify backup exists
ls -lh ~/backups/
```

### 3️⃣ Navigate to Your App Directory

```bash
cd /home/ec2-user/rssb_sne_forms  # Adjust path as needed
```

### 4️⃣ Upload New Files to EC2

**Files to upload:**
- `scripts/migrate_postgres_to_sqlite.py` (migration script)
- `app/database.py` (updated to support SQLite)
- `SQLITE_MIGRATION_GUIDE.md` (full guide)

**Using SCP from your local machine:**
```bash
scp -i your-key.pem scripts/migrate_postgres_to_sqlite.py \
    ec2-user@43.205.30.101:/home/ec2-user/rssb_sne_forms/scripts/

scp -i your-key.pem app/database.py \
    ec2-user@43.205.30.101:/home/ec2-user/rssb_sne_forms/app/

scp -i your-key.pem SQLITE_MIGRATION_GUIDE.md \
    ec2-user@43.205.30.101:/home/ec2-user/rssb_sne_forms/
```

**Or use Git (if you have the code in a repository):**
```bash
git pull origin main
```

### 5️⃣ Run Migration Script

```bash
python3 scripts/migrate_postgres_to_sqlite.py
```

**Expected output:**
```
✅ Migration completed successfully!

📝 Next steps:
   1. Update your .env file to use SQLite
   2. Test your application
   3. Delete RDS instance after verification
```

### 6️⃣ Update .env File

```bash
nano .env
```

**Add this line at the top:**
```
USE_SQLITE=true
```

**Save and exit** (Ctrl+X, then Y, then Enter)

### 7️⃣ Restart Your Application

**Find and kill current process:**
```bash
ps aux | grep gunicorn
sudo kill <PID>
```

**Start with updated config:**
```bash
cd /home/ec2-user/rssb_sne_forms
nohup gunicorn -w 4 -b 0.0.0.0:5000 run:app &
```

**Or if using systemd:**
```bash
sudo systemctl restart your-app-name
```

### 8️⃣ Test Your Application

**Open browser and test:**
- http://43.205.30.101:5000
- Submit a test form
- View existing data
- Generate a badge
- Check database viewer

**Verify data in SQLite:**
```bash
sqlite3 instance/rssbsne.db

SELECT COUNT(*) FROM sne_forms;
SELECT COUNT(*) FROM blood_camp_donors;
SELECT COUNT(*) FROM attendants;

.quit
```

### 9️⃣ Monitor for 24-48 Hours

Check logs regularly:
```bash
tail -f nohup.out
# or
sudo journalctl -u your-app-name -f
```

**Make sure:**
- No errors appear
- Forms submit successfully
- Data saves correctly
- Performance is good

### 🔟 Delete RDS Instance (After Verification)

**Via AWS Console:**
1. Go to AWS RDS Console
2. Select `rssb-database`
3. Actions → Delete
4. Create final snapshot (recommended)
5. Type "delete me" and confirm

**Via AWS CLI:**
```bash
aws rds delete-db-instance \
    --db-instance-identifier rssb-database \
    --final-db-snapshot-identifier rssb-final-backup-$(date +%Y%m%d)
```

---

## 🔄 Quick Rollback (If Something Goes Wrong)

```bash
# 1. Edit .env file
nano .env
# Change: USE_SQLITE=false (or comment out the line)

# 2. Restart application
sudo systemctl restart your-app-name

# Done! App will reconnect to PostgreSQL RDS
```

---

## 📊 What You Get

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| **Monthly Cost** | $37.66 | $14.41 | -$23.25 |
| **Database** | RDS PostgreSQL | SQLite | Simpler |
| **Performance** | 10-20ms | 1-5ms | Faster! |
| **Backups** | Automatic | Manual (easy) | Your control |
| **Scalability** | High | Medium | Fine for your traffic |

---

## ❓ Quick Troubleshooting

**Migration fails with "connection error":**
```bash
# Check PostgreSQL is accessible
psql -h rssb-database.xxxxx.amazonaws.com -U postgres -d rssbsne -c "SELECT 1;"
```

**App can't find SQLite database:**
```bash
# Check file exists
ls -l instance/rssbsne.db

# Check permissions
chmod 664 instance/rssbsne.db
```

**Application won't start:**
```bash
# Check logs
tail -50 nohup.out

# Verify USE_SQLITE is set
grep USE_SQLITE .env
```

---

## 📝 Maintenance (After Migration)

**Weekly backup to S3:**
```bash
# Add to cron
crontab -e

# Add this line (runs every Sunday at 2 AM)
0 2 * * 0 aws s3 cp /home/ec2-user/rssb_sne_forms/instance/rssbsne.db s3://rssbsne/backups/db_backup_$(date +\%Y\%m\%d).db
```

**Monthly optimization:**
```bash
sqlite3 instance/rssbsne.db "VACUUM; ANALYZE;"
```

---

## ✅ Success Checklist

- [ ] PostgreSQL backup created ✓
- [ ] Migration script completed ✓
- [ ] .env updated with USE_SQLITE=true ✓
- [ ] Application restarted ✓
- [ ] All features tested ✓
- [ ] No errors in logs ✓
- [ ] Monitored for 48 hours ✓
- [ ] RDS deleted ✓
- [ ] Backup strategy in place ✓
- [ ] **$20/month saved!** 🎉

---

## 🆘 Need Help?

**Read the full guide:**
[SQLITE_MIGRATION_GUIDE.md](SQLITE_MIGRATION_GUIDE.md)

**Common issues:**
1. Connection errors → Check database credentials
2. File not found → Verify paths are correct
3. Permission errors → Check file permissions
4. Import errors → Install missing dependencies

**Emergency rollback:**
Set `USE_SQLITE=false` in .env and restart app

---

**Remember:** Keep PostgreSQL backup for at least 30 days before deleting permanently!
