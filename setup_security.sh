#!/bin/bash
# Quick Setup Script for RSSB SNE Forms Security
# Run this on your EC2 server after uploading the code

echo "========================================="
echo " RSSB SNE Forms - Security Setup"
echo "========================================="
echo ""

# Check if running with proper user permissions
if [ "$EUID" -eq 0 ]; then 
   echo "Don't run this as root. Run as your application user."
   exit 1
fi

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "✓ .env file created"
    echo ""
    echo "⚠️  IMPORTANT: Edit .env file and set all required values:"
    echo "   nano .env"
    echo ""
else
    echo ".env file already exists"
fi

# Generate SECRET_KEY if not set
if ! grep -q "SECRET_KEY=.*[a-f0-9]" .env; then
    echo "Generating SECRET_KEY..."
    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    sed -i "s|SECRET_KEY=.*|SECRET_KEY=$SECRET_KEY|" .env
    echo "✓ SECRET_KEY generated"
fi

# Generate passwords if not set
echo ""
echo "Generating secure passwords..."
for user in ADMIN SNE_USER BAAL_SATSANG SEWA_BADGES BLOOD_CAMP; do
    if ! grep -q "${user}_PASSWORD=.*[A-Za-z0-9]" .env; then
        PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
        sed -i "s|${user}_PASSWORD=.*|${user}_PASSWORD=$PASSWORD|" .env
        echo "✓ ${user}_PASSWORD generated"
    fi
done

# Set proper permissions
chmod 600 .env
echo ""
echo "✓ Set .env permissions to 600"

# Check for service account files
echo ""
echo "Checking service account files..."
if [ ! -d "/etc/secrets" ]; then
    echo "⚠️  /etc/secrets directory doesn't exist"
    echo "   You need to create it with: sudo mkdir -p /etc/secrets"
    echo "   Then upload your Google Cloud service account JSON files there"
else
    echo "✓ /etc/secrets directory exists"
fi

echo ""
echo "========================================="
echo " Setup Complete!"
echo "========================================="
echo ""
echo "Next Steps:"
echo "1. Review and edit .env file if needed: nano .env"
echo "2. Save your passwords from .env to a password manager"
echo "3. Upload Google service account JSON files to /etc/secrets/"
echo "4. Install requirements: pip install -r requirements.txt"
echo "5. Test the application: python run.py"
echo "6. Set up Gunicorn and NGINX (see SECURITY_SETUP.md)"
echo ""
echo "Your login credentials are in the .env file."
echo "Example: admin user password is in ADMIN_PASSWORD variable"
echo ""
