#!/bin/bash
# PostgreSQL Setup Script for EC2
# Run this after SSHing to your EC2 instance

echo "=========================================="
echo "PostgreSQL Connection Test"
echo "=========================================="
echo ""

# Step 1: Test network connectivity
echo "Step 1: Testing network connectivity to RDS..."
echo "Installing netcat if not present..."
sudo yum install -y nc

echo ""
echo "Testing connection to database..."
nc -zv rssb-database.cvwce2ik6hx7.ap-south-1.rds.amazonaws.com 5432

if [ $? -eq 0 ]; then
    echo "✓ Network connection successful!"
else
    echo "✗ Connection failed! Check security groups."
    exit 1
fi

echo ""
echo "=========================================="
echo "Step 2: Installing PostgreSQL Client"
echo "=========================================="
echo ""

sudo yum install -y postgresql15

echo ""
echo "Checking PostgreSQL version..."
psql --version

echo ""
echo "=========================================="
echo "Step 3: Test Database Connection"
echo "=========================================="
echo ""
echo "You will be prompted for the database password."
echo "Use: TricityAdmin27"
echo ""
echo "Connecting to PostgreSQL..."
echo ""

PGSSLMODE=require psql -h rssb-database.cvwce2ik6hx7.ap-south-1.rds.amazonaws.com \
     -U postgres \
     -d postgres \
     -c "SELECT version();"

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ Database connection successful!"
    echo ""
    echo "Next step: Create the rssbsne database"
    echo "Run: PGSSLMODE=require psql -h rssb-database.cvwce2ik6hx7.ap-south-1.rds.amazonaws.com -U postgres -d postgres"
    echo "Then execute: CREATE DATABASE rssbsne;"
else
    echo ""
    echo "✗ Database connection failed!"
    echo "Check your password and security group settings."
fi
