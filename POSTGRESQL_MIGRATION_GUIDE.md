# PostgreSQL Migration Guide

## Complete Guide to Migrate from Google Sheets to AWS RDS PostgreSQL

---

## Table of Contents
1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Step 1: Set Up AWS RDS PostgreSQL](#step-1-set-up-aws-rds-postgresql)
4. [Step 2: Configure Security Groups](#step-2-configure-security-groups)
5. [Step 3: Initialize Local Environment](#step-3-initialize-local-environment)
6. [Step 4: Initialize Database](#step-4-initialize-database)
7. [Step 5: Migrate Data](#step-5-migrate-data)
8. [Step 6: Update Application Code](#step-6-update-application-code)
9. [Step 7: Deploy to EC2](#step-7-deploy-to-ec2)
10. [Step 8: Testing & Validation](#step-8-testing--validation)
11. [Rollback Plan](#rollback-plan)
12. [Troubleshooting](#troubleshooting)

---

## Overview

This migration will transition your application from Google Sheets to AWS RDS PostgreSQL, providing:

- ✅ **10-100x faster** database operations
- ✅ **ACID compliance** - No more race conditions
- ✅ **Better security** - No service account JSON files
- ✅ **Automated backups** - Point-in-time recovery
- ✅ **Scalability** - Handle thousands of concurrent users
- ✅ **Cost-effective** - Free tier available for 12 months

---

## Prerequisites

### Required Accounts & Access
- AWS Account with EC2 and RDS permissions
- Existing EC2 instance (where your Flask app runs)
- SSH access to EC2 instance
- Google Sheets service account credentials (for migration)

### Required Tools (Local Development)
```bash
# Install PostgreSQL client
sudo apt-get update
sudo apt-get install postgresql-client

# Or on macOS
brew install postgresql
```

---

## Step 1: Set Up AWS RDS PostgreSQL

### Option A: Using AWS Console (Recommended for Beginners)

1. **Go to AWS RDS Console**
   - Navigate to: https://console.aws.amazon.com/rds/
   - Click "Create database"

2. **Choose Database Creation Method**
   - Select: **Standard Create**

3. **Engine Options**
   - Engine type: **PostgreSQL**
   - Version: **PostgreSQL 15.x** (or latest stable)

4. **Templates**
   - For production: **Production**
   - For testing: **Free tier** (if eligible)

5. **Settings**
   ```
   DB instance identifier: rssbsne-db
   Master username: rssbadmin
   Master password: [Generate strong password - SAVE THIS!]
   ```

6. **Instance Configuration**
   - **Free Tier:** db.t3.micro (2 vCPU, 1 GB RAM)
   - **Production:** db.t3.small or db.t3.medium

7. **Storage**
   - Storage type: **General Purpose SSD (gp3)**
   - Allocated storage: **20 GB** (can auto-scale)
   - Enable storage auto-scaling: **Yes** (max 100 GB)

8. **Connectivity**
   - **IMPORTANT:** Select the **same VPC** as your EC2 instance
   - Public access: **No** (more secure - access only from EC2)
   - VPC security group: Create new (we'll configure next)
   - Availability Zone: Same as EC2 for lower latency

9. **Database Authentication**
   - Select: **Password authentication**

10. **Additional Configuration**
    - Initial database name: **rssbsne**
    - Backup retention: **7 days** (or more for production)
    - Enable deletion protection: **Yes** (for production)

11. **Click "Create database"**
    - Wait 5-10 minutes for database to be ready

### Option B: Using AWS CLI (Faster for Advanced Users)

```bash
# Create RDS PostgreSQL instance
aws rds create-db-instance \
    --db-instance-identifier rssbsne-db \
    --db-instance-class db.t3.micro \
    --engine postgres \
    --engine-version 15.4 \
    --master-username rssbadmin \
    --master-user-password "YOUR_SECURE_PASSWORD" \
    --allocated-storage 20 \
    --vpc-security-group-ids sg-xxxxxxxxx \
    --db-subnet-group-name your-subnet-group \
    --backup-retention-period 7 \
    --db-name rssbsne \
    --no-publicly-accessible \
    --storage-encrypted
```

### Save Database Credentials

**IMPORTANT:** Save these details in a secure location (e.g., AWS Secrets Manager):

```
DB Endpoint: rssbsne-db.xxxxxxxxx.ap-south-1.rds.amazonaws.com
Port: 5432
Database Name: rssbsne
Master Username: rssbadmin
Master Password: [Your password]
```

---

## Step 2: Configure Security Groups

### Allow EC2 to Access RDS

1. **Find your RDS Security Group**
   - Go to RDS Console → Your database → Connectivity & Security
   - Note the security group ID (e.g., sg-xxxxxxxxx)

2. **Add Inbound Rule**
   - Go to EC2 Console → Security Groups → [Your RDS Security Group]
   - Click "Edit inbound rules"
   - Add rule:
     ```
     Type: PostgreSQL
     Protocol: TCP
     Port: 5432
     Source: [EC2 Security Group ID] or [EC2 Private IP]/32
     Description: Allow access from Flask app EC2
     ```
   - Click "Save rules"

3. **Verify EC2 Security Group**
   - Ensure your EC2 instance's security group allows outbound traffic on port 5432

---

## Step 3: Initialize Local Environment

### 1. Install Python Dependencies

```bash
# On your development machine or EC2
cd /path/to/rssb_sne_forms
pip install -r requirements.txt
```

### 2. Set Environment Variables

Create a `.env` file in your project root:

```bash
# .env file - DO NOT commit to Git!

# Database Configuration
DB_HOST=rssbsne-db.xxxxxxxxx.ap-south-1.rds.amazonaws.com
DB_PORT=5432
DB_NAME=rssbsne
DB_USER=rssbadmin
DB_PASSWORD=your_secure_password

# Optional: Connection Pool Settings
DB_POOL_SIZE=10
DB_POOL_TIMEOUT=30
DB_POOL_RECYCLE=3600
DB_MAX_OVERFLOW=20

# Flask Configuration
FLASK_ENV=production
SECRET_KEY=your_existing_secret_key

# S3 Configuration (existing)
S3_BUCKET_NAME=rssbsne

# Google Sheets (keep for migration, remove after)
SNE_SHEET_ID=1M9dHOwtVldpruZoBzH23vWIVdcvMlHTdf_fWJGWVmLM
BLOOD_CAMP_SHEET_ID=1fkswOZnDXymKblLsYi79c1_NROn3mMaSua7u5hEKO_E
ATTENDANT_SHEET_ID=13kSQ28X8Gyyba3z3uVJfOqXCYM6ruaw2sIp-nRnqcrM
SNE_SERVICE_ACCOUNT_FILE=/etc/secrets/rssbsneform-credentials.json
BLOOD_CAMP_SERVICE_ACCOUNT_FILE=/etc/secrets/grand-nimbus-credentials.json
ATTENDANT_SERVICE_ACCOUNT_FILE=/etc/secrets/grand-nimbus-credentials.json
```

### 3. Load Environment Variables

```bash
# For development/testing
export $(cat .env | xargs)

# Or use python-dotenv (already in requirements.txt)
# It will auto-load .env file
```

---

## Step 4: Initialize Database

### 1. Test Database Connection

```bash
# Test connection from EC2
psql -h rssbsne-db.xxxxxxxxx.ap-south-1.rds.amazonaws.com \
     -U rssbadmin \
     -d rssbsne \
     -p 5432

# Enter password when prompted
# If successful, you'll see: rssbsne=>
# Type \q to exit
```

### 2. Create Database Tables

```bash
# Initialize database schema
python scripts/init_db.py

# Expected output:
# ============================================================
# Database Connection Information
# ============================================================
# Host:     rssbsne-db.xxxxxxxxx.ap-south-1.rds.amazonaws.com
# Port:     5432
# Database: rssbsne
# User:     rssbadmin
# ============================================================
#
# Checking database connection...
# ✓ Database connection successful!
#
# Creating database tables...
# ✓ All tables created successfully!
#
# Created tables:
#   - sne_forms (SNE registrations)
#   - blood_camp_donors (Blood donor records)
#   - attendants (Attendant badges)
```

### 3. Verify Tables Created

```bash
# Connect to PostgreSQL
psql -h $DB_HOST -U $DB_USER -d $DB_NAME

# List tables
\dt

# Expected output:
#              List of relations
#  Schema |       Name        | Type  |   Owner    
# --------+-------------------+-------+------------
#  public | attendants        | table | rssbadmin
#  public | blood_camp_donors | table | rssbadmin
#  public | sne_forms         | table | rssbadmin

# Describe a table
\d sne_forms

# Exit
\q
```

---

## Step 5: Migrate Data

### 1. Dry Run (Test Migration)

```bash
# Test migration without writing to database
python scripts/migrate_sheets_to_postgres.py --dry-run

# This will:
# - Connect to Google Sheets
# - Fetch all data
# - Show sample records
# - NOT write to database
```

### 2. Migrate Specific Table (Recommended)

Start with one table at a time:

```bash
# Migrate SNE forms
python scripts/migrate_sheets_to_postgres.py --table sne

# Migrate Blood Camp donors
python scripts/migrate_sheets_to_postgres.py --table blood

# Migrate Attendants
python scripts/migrate_sheets_to_postgres.py --table attendant
```

### 3. Migrate All Data

```bash
# Migrate all tables at once
python scripts/migrate_sheets_to_postgres.py

# Expected output:
# ============================================================
# Migrating SNE Forms
# ============================================================
# Fetching data from Google Sheets...
# Found 1250 records in Google Sheets
# Progress: 100/1250 records migrated
# Progress: 200/1250 records migrated
# ...
# SNE Forms Migration Complete:
#   ✓ Migrated: 1250
#   - Skipped:  0
#   ✗ Errors:   0
```

### 4. Verify Data Migration

```bash
# Connect to database
psql -h $DB_HOST -U $DB_USER -d $DB_NAME

# Check record counts
SELECT COUNT(*) FROM sne_forms;
SELECT COUNT(*) FROM blood_camp_donors;
SELECT COUNT(*) FROM attendants;

# Check sample data
SELECT badge_id, first_name, last_name, area FROM sne_forms LIMIT 10;

# Exit
\q
```

---

## Step 6: Update Application Code

### 1. Update `run.py` to Initialize Database

Add this to your `run.py`:

```python
# run.py
import os
from app import create_app
from app.models import db
from app.database import init_db

app = create_app()

# Initialize database
init_db(app)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=(os.environ.get('FLASK_ENV') == 'development'))
```

### 2. Update `app/__init__.py`

Update to initialize database:

```python
# app/__init__.py
from flask import Flask
from flask_login import LoginManager
from app.models import db
from app.database import init_db

def create_app():
    app = Flask(__name__)
    
    # Load config
    from app import config
    app.config.from_object(config)
    
    # Initialize database
    init_db(app)
    
    # Initialize Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'login'
    
    # ... rest of your initialization
    
    return app
```

### 3. Update Routes (See detailed examples in next section)

You'll need to replace Google Sheets calls with PostgreSQL queries. Example:

**Before (Google Sheets):**
```python
sheet = utils.get_sheet(config.SNE_SHEET_ID, config.SNE_SERVICE_ACCOUNT_FILE)
all_data = utils.get_all_sheet_data(...)
```

**After (PostgreSQL):**
```python
from app.models import SNEForm, db

# Query all records
all_data = SNEForm.query.filter_by(area=selected_area).all()

# Add new record
new_sne = SNEForm(badge_id=badge_id, first_name=first_name, ...)
db.session.add(new_sne)
db.session.commit()
```

---

## Step 7: Deploy to EC2

### 1. Upload Code to EC2

```bash
# From your local machine
scp -r /path/to/rssb_sne_forms ec2-user@your-ec2-ip:/home/ec2-user/

# Or use Git
ssh ec2-user@your-ec2-ip
cd /home/ec2-user/rssb_sne_forms
git pull origin main
```

### 2. Set Environment Variables on EC2

```bash
# SSH to EC2
ssh ec2-user@your-ec2-ip

# Set environment variables (add to /etc/environment or ~/.bashrc)
sudo nano /etc/environment

# Add these lines:
DB_HOST=rssbsne-db.xxxxxxxxx.ap-south-1.rds.amazonaws.com
DB_PORT=5432
DB_NAME=rssbsne
DB_USER=rssbadmin
DB_PASSWORD=your_password
SECRET_KEY=your_secret_key
S3_BUCKET_NAME=rssbsne
FLASK_ENV=production

# Save and reload
source /etc/environment
```

### 3. Install Dependencies

```bash
cd /home/ec2-user/rssb_sne_forms
pip3 install -r requirements.txt
```

### 4. Test Application

```bash
# Test run
python3 run.py

# Check if app starts without errors
# Press Ctrl+C to stop
```

### 5. Restart Gunicorn/Service

```bash
# If using systemd service
sudo systemctl restart rssbsne

# If using Gunicorn directly
pkill gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 run:app
```

---

## Step 8: Testing & Validation

### 1. Functional Testing

Test all critical features:

- [ ] SNE Form submission
- [ ] Badge ID generation (check for duplicates)
- [ ] Blood Camp donor registration
- [ ] Donor status updates
- [ ] Attendant badge creation
- [ ] Photo uploads to S3
- [ ] Badge/certificate PDF generation
- [ ] Dashboard data display
- [ ] Search and filter functionality
- [ ] Edit existing records

### 2. Performance Testing

```bash
# Run your existing load tests
python test_concurrent_submissions.py

# Expected: No duplicate IDs, faster response times
```

### 3. Data Integrity Checks

```bash
# Verify no duplicate Badge IDs
python verify_no_duplicates.py

# Check data consistency
psql -h $DB_HOST -U $DB_USER -d $DB_NAME

-- Check for duplicate badge IDs
SELECT badge_id, COUNT(*) 
FROM sne_forms 
GROUP BY badge_id 
HAVING COUNT(*) > 1;

-- Check for duplicate donor IDs
SELECT donor_id, COUNT(*) 
FROM blood_camp_donors 
GROUP BY donor_id 
HAVING COUNT(*) > 1;
```

---

## Rollback Plan

If something goes wrong, you can quickly rollback:

### Option 1: Keep Google Sheets Running (Recommended During Testing)

1. Don't delete Google Sheets integration code immediately
2. Add a feature flag in config:

```python
# app/config.py
USE_POSTGRES = os.environ.get('USE_POSTGRES', 'false').lower() == 'true'
```

3. Toggle between backends:
```bash
# Use PostgreSQL
export USE_POSTGRES=true

# Rollback to Google Sheets
export USE_POSTGRES=false
sudo systemctl restart rssbsne
```

### Option 2: Database Snapshot

AWS RDS automatically creates daily snapshots. To restore:

1. Go to RDS Console → Snapshots
2. Select snapshot → Actions → Restore snapshot
3. Update DB_HOST environment variable to new endpoint

---

## Troubleshooting

### Connection Issues

**Error: "could not connect to server"**
```bash
# Check security group allows EC2 IP
# Check EC2 can reach RDS
telnet rssbsne-db.xxxxxxxxx.rds.amazonaws.com 5432

# Check DNS resolution
nslookup rssbsne-db.xxxxxxxxx.rds.amazonaws.com
```

**Error: "password authentication failed"**
```bash
# Verify password in environment variables
echo $DB_PASSWORD

# Reset master password in RDS Console if needed
```

### Migration Issues

**Error: "Could not connect to Google Sheets"**
- Verify service account JSON files exist
- Check GOOGLE_APPLICATION_CREDENTIALS path

**Error: "Duplicate key violation"**
```bash
# Clear existing data and re-migrate
psql -h $DB_HOST -U $DB_USER -d $DB_NAME

TRUNCATE sne_forms CASCADE;
TRUNCATE blood_camp_donors CASCADE;
TRUNCATE attendants CASCADE;
\q

# Re-run migration
python scripts/migrate_sheets_to_postgres.py
```

### Performance Issues

**Slow queries**
```sql
-- Create additional indexes if needed
CREATE INDEX idx_sne_submission_date ON sne_forms(submission_date);
CREATE INDEX idx_blood_donation_date ON blood_camp_donors(donation_date);

-- Analyze query performance
EXPLAIN ANALYZE SELECT * FROM sne_forms WHERE area = 'Delhi';
```

**Connection pool exhausted**
```bash
# Increase pool size
export DB_POOL_SIZE=20
export DB_MAX_OVERFLOW=40
```

---

## Cost Estimate

### AWS RDS PostgreSQL Pricing (ap-south-1 / Mumbai region)

**Free Tier (First 12 months):**
- db.t3.micro: 750 hours/month (enough for 1 instance 24/7)
- 20 GB storage
- 20 GB backup storage
- **Cost: $0/month**

**After Free Tier (or production setup):**
- db.t3.micro: ~$15/month
- db.t3.small: ~$30/month
- db.t3.medium: ~$60/month
- Storage (20 GB): ~$2.50/month
- Backups: ~$2/month

**Estimated total: $15-65/month** (vs Google Sheets which is free but limited)

---

## Security Best Practices

1. **Use AWS Secrets Manager for database credentials**
   ```bash
   # Store password in Secrets Manager
   aws secretsmanager create-secret \
       --name rssbsne/db/password \
       --secret-string "your_password"
   ```

2. **Enable SSL/TLS connections**
   ```python
   # In database.py connection string
   uri = f"postgresql://{user}:{password}@{host}:{port}/{db}?sslmode=require"
   ```

3. **Regular backups**
   - RDS handles automated backups
   - Manual snapshots before major changes
   - Test restore procedure

4. **Monitor database logs**
   - Enable CloudWatch logs for RDS
   - Set up alarms for connection failures
   - Monitor slow queries

---

## Next Steps After Migration

1. **Remove Google Sheets dependencies** (after 2-4 weeks of stable operation)
   - Remove gspread from requirements.txt
   - Remove service account JSON files
   - Remove Google Sheets related code

2. **Implement database migrations** (for future schema changes)
   ```bash
   pip install Flask-Migrate
   flask db init
   flask db migrate -m "Initial migration"
   ```

3. **Set up monitoring**
   - CloudWatch for RDS metrics
   - Application-level query logging
   - Set up alerts for errors

4. **Optimize performance**
   - Analyze slow queries
   - Add indexes as needed
   - Consider read replicas for reporting

---

## Support

For issues or questions:
1. Check AWS RDS documentation
2. Review PostgreSQL logs in CloudWatch
3. Check application logs on EC2
4. Verify all environment variables are set correctly

---

**Good luck with your migration! 🚀**
