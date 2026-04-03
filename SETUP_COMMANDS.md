# PostgreSQL Setup Commands - Step by Step

## Your Database Details

```
Endpoint: rssb-database.cvwce2ik6hx7.ap-south-1.rds.amazonaws.com
Port: 5432
Database: rssbsne
Username: postgres
Password: [Your secure password - not stored in this file]
EC2 Security Group: sg-08ced5f7b590c1f49
RDS Security Group: sg-0d83c1e1af179e7fb
```

---

## Step 1: Test Connection from EC2

```bash
# SSH to your EC2 instance
ssh ec2-user@your-ec2-ip

# Test if database port is reachable using telnet
telnet rssb-database.cvwce2ik6hx7.ap-south-1.rds.amazonaws.com 5432
```

**Expected output if successful:**
```
Trying xxx.xxx.xxx.xxx...
Connected to rssb-database.cvwce2ik6hx7.ap-south-1.rds.amazonaws.com.
Escape character is '^]'.
```

Press **Ctrl+]** then type **quit** and press Enter to exit.

**Alternative - Install and use nc (netcat):**
```bash
# Install netcat
sudo yum install -y nc

# Test connection
nc -zv rssb-database.cvwce2ik6hx7.ap-south-1.rds.amazonaws.com 5432
# Should show: Connection succeeded!
```

---

## Step 2: Install PostgreSQL Client

```bash
# Install PostgreSQL 15 client
sudo yum install -y postgresql15

# Verify installation
psql --version
```

---

## Step 3: Create Database and Test Connection

```bash
# First, connect to the default postgres database
PGSSLMODE=require psql -h rssb-database.cvwce2ik6hx7.ap-south-1.rds.amazonaws.com \
     -U postgres \
     -d postgres

# When prompted, enter your password
```

**Once connected, create the rssbsne database:**

```sql
-- Create the database
CREATE DATABASE rssbsne;

-- Verify it was created
\l

-- Connect to the new database
\c rssbsne

-- You should now see: rssbsne=>

-- Exit
\q
```

**Test connection to the new database:**

```bash
# Connect to rssbsne database
PGSSLMODE=require psql -h rssb-database.cvwce2ik6hx7.ap-south-1.rds.amazonaws.com \
     -U postgres \
     -d rssbsne
```

**Expected output:**
```
Password for user postgres: 
psql (15.x)
SSL connection (protocol: TLSv1.3, cipher: TLS_AES_256_GCM_SHA384, bits: 256)
Type "help" for help.

rssbsne=>
```

**Test it works:**
```sql
SELECT version();
\q
```

---

## Step 4: Set Up Environment Variables

```bash
# Create secure config directory
sudo mkdir -p /etc/rssbsne
cd /etc/rssbsne

# Create .env file with all environment variables
sudo tee /etc/rssbsne/.env > /dev/null << 'EOF'
# PostgreSQL Database Configuration
DB_HOST=rssb-database.cvwce2ik6hx7.ap-south-1.rds.amazonaws.com
DB_PORT=5432
DB_NAME=rssbsne
DB_USER=postgres
DB_PASSWORD=your_actual_password_here

# Flask Application Configuration
SECRET_KEY=your_existing_secret_key
S3_BUCKET_NAME=rssbsne
FLASK_ENV=production

# Google Sheets Configuration (for migration only)
SNE_SHEET_ID=1M9dHOwtVldpruZoBzH23vWIVdcvMlHTdf_fWJGWVmLM
BLOOD_CAMP_SHEET_ID=1fkswOZnDXymKblLsYi79c1_NROn3mMaSua7u5hEKO_E
ATTENDANT_SHEET_ID=13kSQ28X8Gyyba3z3uVJfOqXCYM6ruaw2sIp-nRnqcrM
SNE_SERVICE_ACCOUNT_FILE=/etc/secrets/rssbsneform-credentials.json
BLOOD_CAMP_SERVICE_ACCOUNT_FILE=/etc/secrets/grand-nimbus-credentials.json
ATTENDANT_SERVICE_ACCOUNT_FILE=/etc/secrets/grand-nimbus-credentials.json
EOF

# Secure the file (only owner can read/write)
sudo chown ec2-user:ec2-user /etc/rssbsne/.env
sudo chmod 600 /etc/rssbsne/.env

# Load environment variables (filtering out comments)
export $(grep -v '^#' /etc/rssbsne/.env | xargs)

# Verify variables are loaded
echo "DB_HOST: $DB_HOST"
echo "DB_NAME: $DB_NAME"
echo "DB_USER: $DB_USER"
```

---

## Step 5: Navigate to Project Directory

```bash
# Go to project directory
cd ~/rssb_sne_forms

# Verify you're in the right place
ls -la
# Should see: app/, scripts/, requirements.txt, run.py, etc.
```

---

## Step 6: Install Python Dependencies

```bash
# Install all required packages
pip3 install -r requirements.txt

# Verify critical packages are installed
python3 -c "import psycopg2; print('psycopg2: OK')"
python3 -c "import sqlalchemy; print('SQLAlchemy: OK')"
python3 -c "from flask_sqlalchemy import SQLAlchemy; print('Flask-SQLAlchemy: OK')"
```

---

## Step 7: Check Database Connection

```bash
# Make sure environment variables are loaded
export $(grep -v '^#' /etc/rssbsne/.env | xargs)

# Check if Python can connect to database
python3 scripts/init_db.py --check
```

**Expected output:**
```
============================================================
Database Connection Information
============================================================
Host:     rssb-database.cvwce2ik6hx7.ap-south-1.rds.amazonaws.com
Port:     5432
Database: rssbsne
User:     postgres
============================================================

Checking database connection...
✓ Database connection successful!
Connection check complete.
```

---

## Step 8: Initialize Database Tables

```bash
# Create all database tables
python3 scripts/init_db.py
```

**Expected output:**
```
Creating database tables...
✓ All tables created successfully!

Created tables:
  - sne_forms (SNE registrations)
  - blood_camp_donors (Blood donor records)
  - attendants (Attendant badges)

Current record counts:
  - SNE Forms: 0
  - Blood Donors: 0
  - Attendants: 0

============================================================
Database initialization complete!
============================================================

Next steps:
  1. Run migration script to import data from Google Sheets:
     python scripts/migrate_sheets_to_postgres.py
```

---

## Step 9: Verify Tables Created

```bash
# Connect to database (with SSL)
PGSSLMODE=require psql -h rssb-database.cvwce2ik6hx7.ap-south-1.rds.amazonaws.com \
     -U postgres \
     -d rssbsne

# List all tables
\dt

# Describe sne_forms table structure
\d sne_forms

# Exit
\q
```

**Expected tables:**
- `sne_forms`
- `blood_camp_donors`
- `attendants`

---

## Step 10: Migrate Data from Google Sheets (Dry Run)

```bash
# Test migration without writing to database
python3 scripts/migrate_sheets_to_postgres.py --dry-run
```

**Expected output:**
```
============================================================
Google Sheets to PostgreSQL Migration
============================================================
✓ Database connection successful

============================================================
Migrating SNE Forms
============================================================
Fetching data from Google Sheets...
Found 1250 records in Google Sheets
DRY RUN - No data will be written to database

Sample record:
  Badge ID: DL-VK-RM0001
  First Name: John
  Last Name: Doe
  Area: Delhi
  ...
```

---

## Step 11: Migrate Data (Actual Migration)

### Option A: Migrate All Tables at Once

```bash
# Migrate all data from Google Sheets to PostgreSQL
python3 scripts/migrate_sheets_to_postgres.py
```

### Option B: Migrate One Table at a Time (Safer)

```bash
# Migrate SNE forms only
python3 scripts/migrate_sheets_to_postgres.py --table sne

# Migrate Blood Camp donors only
python3 scripts/migrate_sheets_to_postgres.py --table blood

# Migrate Attendants only
python3 scripts/migrate_sheets_to_postgres.py --table attendant
```

**Expected output:**
```
============================================================
Migrating SNE Forms
============================================================
Fetching data from Google Sheets...
Found 1250 records in Google Sheets
Progress: 100/1250 records migrated
Progress: 200/1250 records migrated
...
Progress: 1200/1250 records migrated

SNE Forms Migration Complete:
  ✓ Migrated: 1250
  - Skipped:  0
  ✗ Errors:   0

============================================================
Migration Summary
============================================================
Total records migrated: 1250

✓ Migration complete!
```

---

## Step 12: Verify Migrated Data

```bash
# Connect to database (with SSL)
PGSSLMODE=require psql -h rssb-database.cvwce2ik6hx7.ap-south-1.rds.amazonaws.com \
     -U postgres \
     -d rssbsne
```

**Run these SQL queries:**

```sql
-- Check record counts
SELECT COUNT(*) as total_sne_forms FROM sne_forms;
SELECT COUNT(*) as total_donors FROM blood_camp_donors;
SELECT COUNT(*) as total_attendants FROM attendants;

-- View sample SNE forms
SELECT badge_id, first_name, last_name, area, satsang_place 
FROM sne_forms 
ORDER BY submission_date DESC 
LIMIT 10;

-- View sample blood donors
SELECT donor_id, name_of_donor, blood_group, status, donation_date
FROM blood_camp_donors
ORDER BY submission_timestamp DESC
LIMIT 10;

-- View sample attendants
SELECT badge_id, name, area, centre, attendant_type
FROM attendants
ORDER BY submission_date DESC
LIMIT 10;

-- Check for duplicate Badge IDs (should return 0 rows)
SELECT badge_id, COUNT(*) 
FROM sne_forms 
GROUP BY badge_id 
HAVING COUNT(*) > 1;

-- Check for duplicate Donor IDs (should return 0 rows)
SELECT donor_id, COUNT(*) 
FROM blood_camp_donors 
GROUP BY donor_id 
HAVING COUNT(*) > 1;

-- Exit
\q
```

---

## Step 13: Create Test Script (Optional)

```bash
# Create a simple test script
cat > ~/test_db.py << 'EOF'
#!/usr/bin/env python3
import os
import psycopg2

DB_HOST = "rssb-database.cvwce2ik6hx7.ap-south-1.rds.amazonaws.com"
DB_PORT = "5432"
DB_NAME = "rssbsne"
DB_USER = "postgres"
DB_PASSWORD = "your_actual_password_here"

try:
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    print("✓ Connection successful!")
    
    cur = conn.cursor()
    
    # Get PostgreSQL version
    cur.execute("SELECT version();")
    version = cur.fetchone()
    print(f"\nPostgreSQL version:\n{version[0]}\n")
    
    # Get record counts
    cur.execute("SELECT COUNT(*) FROM sne_forms;")
    sne_count = cur.fetchone()[0]
    print(f"SNE Forms: {sne_count}")
    
    cur.execute("SELECT COUNT(*) FROM blood_camp_donors;")
    donor_count = cur.fetchone()[0]
    print(f"Blood Donors: {donor_count}")
    
    cur.execute("SELECT COUNT(*) FROM attendants;")
    attendant_count = cur.fetchone()[0]
    print(f"Attendants: {attendant_count}")
    
    cur.close()
    conn.close()
    
except Exception as e:
    print(f"✗ Connection failed: {e}")
EOF

# Make executable
chmod +x ~/test_db.py

# Run test
python3 ~/test_db.py
```

---

## Step 14: Update Systemd Service (To Use PostgreSQL)

```bash
# Edit your Flask app systemd service
sudo systemctl edit rssbsne

# Add this to load environment variables:
[Service]
EnvironmentFile=/etc/rssbsne/.env

# Save and exit (Ctrl+X, Y, Enter)

# Reload systemd
sudo systemctl daemon-reload

# Restart your Flask application
sudo systemctl restart rssbsne

# Check status
sudo systemctl status rssbsne

# View logs
sudo journalctl -u rssbsne -f
```

---

## Troubleshooting Commands

### Connection Issues

```bash
# Test network connectivity to RDS
ping rssb-database.cvwce2ik6hx7.ap-south-1.rds.amazonaws.com

# Test port 5432 specifically (using telnet)
telnet rssb-database.cvwce2ik6hx7.ap-south-1.rds.amazonaws.com 5432
# Press Ctrl+] then type "quit" to exit

# Or install and use nc (netcat)
sudo yum install -y nc
nc -zv rssb-database.cvwce2ik6hx7.ap-south-1.rds.amazonaws.com 5432
```

### View RDS Security Group via CLI

```bash
# Get RDS security groups
aws rds describe-db-instances \
    --db-instance-identifier rssb-database \
    --query 'DBInstances[0].VpcSecurityGroups[*].[VpcSecurityGroupId,Status]' \
    --output table \
    --region ap-south-1

# View security group rules
aws ec2 describe-security-groups \
    --group-ids sg-0d83c1e1af179e7fb \
    --region ap-south-1
```

### Check Database Size

```bash
# Connect to database
psql -h rssb-database.cvwce2ik6hx7.ap-south-1.rds.amazonaws.com \
     -U postgres \
     -d rssbsne

# Check database size
SELECT pg_size_pretty(pg_database_size('rssbsne'));

# Check table sizes
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

# Exit
\q
```

### View Application Logs

```bash
# View Flask app logs (if using systemd)
sudo journalctl -u rssbsne -n 100 --no-pager

# Follow logs in real-time
sudo journalctl -u rssbsne -f

# View only errors
sudo journalctl -u rssbsne -p err
```

### Reload Environment Variables

```bash
# If you update .env file
export $(grep -v '^#' /etc/rssbsne/.env | xargs)

# Verify
echo $DB_HOST
echo $DB_NAME
```

---

## Quick Reference - Connection String

```bash
# PostgreSQL connection URI
postgresql://postgres:YOUR_PASSWORD@rssb-database.cvwce2ik6hx7.ap-south-1.rds.amazonaws.com:5432/rssbsne

# psql command
psql -h rssb-database.cvwce2ik6hx7.ap-south-1.rds.amazonaws.com -U postgres -d rssbsne -p 5432

# Python psycopg2
import psycopg2
conn = psycopg2.connect(
    host="rssb-database.cvwce2ik6hx7.ap-south-1.rds.amazonaws.com",
    port="5432",
    database="rssbsne",
    user="postgres",
    password="TricityAdmin27"
)
```

---

## Backup Commands (Important!)

### Create Manual Snapshot

```bash
# Via AWS CLI
aws rds create-db-snapshot \
    --db-instance-identifier rssb-database \
    --db-snapshot-identifier rssb-database-manual-snapshot-$(date +%Y%m%d-%H%M%S) \
    --region ap-south-1

# List snapshots
aws rds describe-db-snapshots \
    --db-instance-identifier rssb-database \
    --region ap-south-1
```

### Export Data (SQL Dump)

```bash
# Dump entire database
pg_dump -h rssb-database.cvwce2ik6hx7.ap-south-1.rds.amazonaws.com \
        -U postgres \
        -d rssbsne \
        -F c \
        -f rssbsne_backup_$(date +%Y%m%d).dump

# Dump specific table
pg_dump -h rssb-database.cvwce2ik6hx7.ap-south-1.rds.amazonaws.com \
        -U postgres \
        -d rssbsne \
        -t sne_forms \
        -F c \
        -f sne_forms_backup.dump
```

---

## Summary Checklist

- [ ] SSH to EC2 instance
- [ ] Test connection to RDS (port 5432)
- [ ] Install PostgreSQL client
- [ ] Connect to database with psql
- [ ] Create .env file with credentials
- [ ] Load environment variables
- [ ] Install Python dependencies
- [ ] Run `init_db.py --check`
- [ ] Run `init_db.py` to create tables
- [ ] Verify tables created
- [ ] Run migration dry-run
- [ ] Run actual migration
- [ ] Verify data migrated correctly
- [ ] Update systemd service
- [ ] Restart Flask application
- [ ] Test application

---

**All done! Your PostgreSQL database is ready to use. 🎉**
