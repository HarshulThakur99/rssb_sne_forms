# app.py (Refactored)
import os
import datetime
import logging

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user, login_required, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
import boto3 # Keep boto3 import here for global client init

# Import configuration, utilities, and blueprints
import config
import utils
from sne_routes import sne_bp
from blood_camp_routes import blood_camp_bp
from attendant_routes import attendant_bp

# --- Flask App Initialization ---
app = Flask(__name__)
app.config['SECRET_KEY'] = config.SECRET_KEY
app.config['MAX_CONTENT_LENGTH'] = config.MAX_CONTENT_LENGTH

# --- Logging Setup ---
# Configure logging level and format
# In production, consider more robust logging (e.g., to file, rotating logs)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger(__name__) # Get logger for app.py

# --- Initialize Extensions ---
# Login Manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' # Route name for the login page
login_manager.login_message = "Please log in to access this page."
login_manager.login_message_category = "warning"

# S3 Client (Initialize once globally)
# Ensure AWS credentials are configured (e.g., via environment variables, IAM role)
try:
    # Use the global client from utils if initialized there, or initialize here
    if not hasattr(utils, 's3_client') or utils.s3_client is None:
         utils.s3_client = boto3.client('s3')
         logger.info("Initialized Boto3 S3 client in app.py")
    # Make S3 client accessible via app context if needed by blueprints/utils
    # app.s3_client = utils.s3_client
except Exception as e:
    logger.critical(f"Failed to initialize Boto3 S3 client: {e}", exc_info=True)
    # Depending on requirements, you might exit or run with S3 features disabled
    # For now, log critical error and continue (S3 dependent features will fail)

# --- User Authentication ---
# Simple in-memory user store (Replace with a database in production)
users_db = {
    'admin': { 'password_hash': generate_password_hash('password123'), 'id': 'admin' }
    # Add more users as needed
}

class User(UserMixin):
    """Basic User class for Flask-Login."""
    def __init__(self, id, password_hash):
        self.id = id
        self.password_hash = password_hash

    @staticmethod
    def get(user_id):
        user_data = users_db.get(user_id)
        if user_data:
            return User(id=user_data['id'], password_hash=user_data['password_hash'])
        return None

@login_manager.user_loader
def load_user(user_id):
    """Flask-Login user loader callback."""
    return User.get(user_id)

# --- Core Routes ---

@app.route('/')
@login_required # Require login for the home page
def home():
    """Displays the main home/dashboard page."""
    current_year = datetime.date.today().year
    # Pass current_user implicitly available in templates when using Flask-Login
    return render_template('home.html', current_year=current_year)

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handles user login."""
    if current_user.is_authenticated:
        return redirect(url_for('home')) # Redirect if already logged in

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = bool(request.form.get('remember')) # Checkbox value

        user = User.get(username)

        # Validate user and password
        if not user or not check_password_hash(user.password_hash, password):
            flash('Invalid username or password.', 'error')
            return redirect(url_for('login'))

        # Log the user in
        login_user(user, remember=remember)
        flash('Logged in successfully!', 'success')

        # Redirect to the originally requested page or home
        next_page = request.args.get('next')
        return redirect(next_page or url_for('home'))

    # Render the login page for GET requests
    return render_template('login.html')

@app.route('/logout')
@login_required # Must be logged in to log out
def logout():
    """Handles user logout."""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

# --- Dynamic Centre Loading Route (Used by SNE & Attendant) ---
@app.route('/get_centres/<area>')
@login_required
def get_centres_for_area(area):
    """Returns a JSON list of centres for a given area based on SNE config."""
    # Uses SNE_BADGE_CONFIG from config.py
    if area in config.SNE_BADGE_CONFIG:
        centres = sorted(list(config.SNE_BADGE_CONFIG[area].keys()))
        return jsonify(centres)
    else:
        logger.warning(f"Area '{area}' not found in SNE_BADGE_CONFIG for /get_centres route.")
        return jsonify([]) # Return empty list if area not found

# --- Register Blueprints ---
app.register_blueprint(sne_bp)
app.register_blueprint(blood_camp_bp)
app.register_blueprint(attendant_bp)
logger.info("Registered blueprints: SNE, Blood Camp, Attendant")

# --- Main Execution ---
if __name__ == '__main__':
    # Use host='0.0.0.0' for deployment environments (like Docker, Cloud Run)
    # Use debug=False for production
    port = int(os.environ.get('PORT', 8080)) # Default to 8080 if PORT env var isn't set
    # Set debug=True only for local development
    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'

    logger.info(f"Starting Flask app on port {port} with debug mode: {debug_mode}")
    # Use waitress or gunicorn for production instead of app.run()
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
