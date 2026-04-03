# PostgreSQL Migration - Quick Start Guide

## 🚀 Quick Migration in 5 Steps

### Step 1: Install PostgreSQL Dependencies (2 minutes)

```bash
cd /path/to/rssb_sne_forms
pip install -r requirements.txt
```

### Step 2: Set Up AWS RDS PostgreSQL (10 minutes)

**Via AWS Console:**
1. Go to [AWS RDS Console](https://console.aws.amazon.com/rds/)
2. Click "Create database"
3. Choose:
   - Engine: **PostgreSQL 15.x**
   - Template: **Free tier** (or Production)
   - Instance: **db.t3.micro**
   - DB name: **rssbsne**
   - Username: **rssbadmin**
   - Password: [Create strong password]
   - **Same VPC as your EC2**
   - Public access: **No**
4. Wait 5-10 minutes for creation
5. Note the **endpoint** (e.g., rssbsne-db.xxxxx.ap-south-1.rds.amazonaws.com)

**Configure Security Group:**
1. Go to EC2 → Security Groups → [RDS Security Group]
2. Add inbound rule:
   - Type: PostgreSQL
   - Port: 5432
   - Source: [Your EC2 Security Group ID]

### Step 3: Configure Environment Variables (3 minutes)

Create `.env` file in your project root:

```bash
# Database
DB_HOST=rssbsne-db.xxxxx.ap-south-1.rds.amazonaws.com
DB_PORT=5432
DB_NAME=rssbsne
DB_USER=rssbadmin
DB_PASSWORD=your_secure_password

# Existing Config
FLASK_ENV=production
SECRET_KEY=your_existing_secret_key
S3_BUCKET_NAME=rssbsne

# Google Sheets (keep for migration)
SNE_SHEET_ID=1M9dHOwtVldpruZoBzH23vWIVdcvMlHTdf_fWJGWVmLM
BLOOD_CAMP_SHEET_ID=1fkswOZnDXymKblLsYi79c1_NROn3mMaSua7u5hEKO_E
ATTENDANT_SHEET_ID=13kSQ28X8Gyyba3z3uVJfOqXCYM6ruaw2sIp-nRnqcrM
SNE_SERVICE_ACCOUNT_FILE=/etc/secrets/rssbsneform-credentials.json
BLOOD_CAMP_SERVICE_ACCOUNT_FILE=/etc/secrets/grand-nimbus-credentials.json
ATTENDANT_SERVICE_ACCOUNT_FILE=/etc/secrets/grand-nimbus-credentials.json
```

Load environment:
```bash
export $(cat .env | xargs)
```

### Step 4: Initialize Database (2 minutes)

```bash
# Test connection
python scripts/init_db.py --check

# Create tables
python scripts/init_db.py
```

Expected output:
```
✓ Database connection successful!
✓ All tables created successfully!
Created tables:
  - sne_forms (SNE registrations)
  - blood_camp_donors (Blood donor records)
  - attendants (Attendant badges)
```

### Step 5: Migrate Data (5-15 minutes)

```bash
# Dry run first (test without writing)
python scripts/migrate_sheets_to_postgres.py --dry-run

# Migrate all data
python scripts/migrate_sheets_to_postgres.py

# Or migrate one table at a time:
python scripts/migrate_sheets_to_postgres.py --table sne
python scripts/migrate_sheets_to_postgres.py --table blood
python scripts/migrate_sheets_to_postgres.py --table attendant
```

Verify:
```bash
# Connect to database
psql -h $DB_HOST -U $DB_USER -d $DB_NAME

# Check counts
SELECT COUNT(*) FROM sne_forms;
SELECT COUNT(*) FROM blood_camp_donors;
SELECT COUNT(*) FROM attendants;

# Exit
\q
```

---

## ✅ You're Done!

Your data is now in PostgreSQL. Next step: Update your application routes.

---

## 📚 Next Steps

### Update Application Code

See detailed examples in [ROUTE_UPDATE_EXAMPLES.md](ROUTE_UPDATE_EXAMPLES.md)

**Quick pattern:**

Before (Google Sheets):
```python
sheet = utils.get_sheet(config.SNE_SHEET_ID, ...)
data = utils.get_all_sheet_data(...)
```

After (PostgreSQL):
```python
from app.models import SNEForm, db
data = SNEForm.query.filter_by(area=area).all()
```

### Update run.py

```python
from app import create_app
from app.models import db
from app.database import init_db

app = create_app()
init_db(app)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
```

### Deploy to EC2

```bash
# Upload code
scp -r /path/to/project ec2-user@your-ec2-ip:/home/ec2-user/

# SSH to EC2
ssh ec2-user@your-ec2-ip

# Set environment variables
sudo nano /etc/environment
# Add DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD

# Install dependencies
cd /home/ec2-user/rssb_sne_forms
pip3 install -r requirements.txt

# Test
python3 run.py

# Restart service
sudo systemctl restart rssbsne
```

---

## 🧪 Testing

Test these critical features:
- [ ] SNE form submission
- [ ] Badge ID generation (no duplicates)
- [ ] Blood donor registration
- [ ] Donor status updates
- [ ] Attendant creation
- [ ] Photo uploads
- [ ] PDF generation
- [ ] Concurrent submissions

Run existing tests:
```bash
python test_concurrent_submissions.py
python verify_no_duplicates.py
```

---

## 🔧 Troubleshooting

### "Could not connect to server"
```bash
# Check security group allows your EC2 IP
# Test connection
telnet $DB_HOST 5432
```

### "Password authentication failed"
```bash
# Verify password
echo $DB_PASSWORD

# Reset in RDS Console if needed
```

### "Duplicate key violation"
```bash
# Clear and re-migrate
psql -h $DB_HOST -U $DB_USER -d $DB_NAME
TRUNCATE sne_forms, blood_camp_donors, attendants CASCADE;
\q

python scripts/migrate_sheets_to_postgres.py
```

---

## 📖 Full Documentation

- **[POSTGRESQL_MIGRATION_GUIDE.md](POSTGRESQL_MIGRATION_GUIDE.md)** - Complete migration guide
- **[ROUTE_UPDATE_EXAMPLES.md](ROUTE_UPDATE_EXAMPLES.md)** - Code update examples
- **[app/models.py](app/models.py)** - Database schema
- **[app/db_helpers.py](app/db_helpers.py)** - Helper functions

---

## 💰 Cost Estimate

**AWS RDS PostgreSQL:**
- Free tier: $0/month (first 12 months)
- After: $15-30/month (db.t3.micro/small)

**Benefits:**
- 10-100x faster than Google Sheets
- No race conditions
- Better security
- Automated backups
- Unlimited concurrent users

---

## 🆘 Need Help?

1. Check AWS RDS CloudWatch logs
2. Review application logs
3. Verify all environment variables
4. Test database connection manually
5. Check security group rules

**Good luck! 🎉**
