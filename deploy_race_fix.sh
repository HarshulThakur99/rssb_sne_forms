#!/bin/bash
# Deployment script for race condition fix
# Run on EC2 server as ec2-user

set -e  # Exit on error

echo "========================================="
echo "Race Condition Fix - Deployment Script"
echo "========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. Check if we're in the right directory
if [ ! -f "run.py" ]; then
    echo -e "${RED}Error: run.py not found. Please run this script from /home/ec2-user/rssb_sne_forms${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Correct directory confirmed${NC}"
echo ""

# 2. Check database state
echo "Step 1: Checking database state..."
echo "-----------------------------------"
python3 check_badge_ids.py
echo ""
read -p "Does the above look correct? (y/n) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${RED}Deployment cancelled${NC}"
    exit 1
fi
echo ""

# 3. Backup current code
echo "Step 2: Backing up current code..."
echo "-----------------------------------"
BACKUP_DIR="app_backup_$(date +%Y%m%d_%H%M%S)"
cp -r app "$BACKUP_DIR"
echo -e "${GREEN}✓ Backup created: $BACKUP_DIR${NC}"
echo ""

# 4. Check if files are updated
echo "Step 3: Verifying updated files..."
echo "-----------------------------------"
if grep -q "pg_advisory_xact_lock" app/db_helpers.py; then
    echo -e "${GREEN}✓ app/db_helpers.py contains advisory lock code${NC}"
else
    echo -e "${RED}✗ app/db_helpers.py does not contain advisory lock code${NC}"
    echo -e "${YELLOW}Warning: Files may not be updated!${NC}"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi
echo ""

# 5. Restart service
echo "Step 4: Restarting service..."
echo "-----------------------------------"
sudo systemctl restart rssbsne.service
sleep 3

# Check if service is running
if sudo systemctl is-active --quiet rssbsne.service; then
    echo -e "${GREEN}✓ Service restarted successfully${NC}"
else
    echo -e "${RED}✗ Service failed to start!${NC}"
    echo "Checking logs:"
    sudo journalctl -u rssbsne.service -n 50 --no-pager
    echo ""
    echo -e "${YELLOW}Restoring backup...${NC}"
    sudo systemctl stop rssbsne.service
    rm -rf app
    cp -r "$BACKUP_DIR" app
    sudo systemctl start rssbsne.service
    echo -e "${RED}Deployment failed and rolled back${NC}"
    exit 1
fi
echo ""

# 6. Monitor logs
echo "Step 5: Monitoring logs (Ctrl+C to exit)..."
echo "-----------------------------------"
echo -e "${YELLOW}Watch for:${NC}"
echo "  ✓ 'Generated next SNE badge ID: SNE-AX-XXXXXX'"
echo "  ✓ 'Created SNE form: SNE-AX-XXXXXX'"
echo "  ✗ 'Duplicate badge_id error' (should not appear)"
echo ""
echo "Press Ctrl+C when ready to exit monitoring"
echo ""
sleep 2
sudo journalctl -u rssbsne.service -f

# Script will continue here after Ctrl+C
echo ""
echo "========================================="
echo -e "${GREEN}Deployment complete!${NC}"
echo "========================================="
echo ""
echo "Next steps:"
echo "1. Test form submission through web interface"
echo "2. Check logs: sudo journalctl -u rssbsne.service -f"
echo "3. Run diagnostics: python3 check_badge_ids.py"
echo ""
echo "Rollback command (if needed):"
echo "  sudo systemctl stop rssbsne.service"
echo "  rm -rf app && cp -r $BACKUP_DIR app"
echo "  sudo systemctl start rssbsne.service"
echo ""
