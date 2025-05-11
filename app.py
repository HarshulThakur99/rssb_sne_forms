# app.py (Refactored)
import os
import datetime
import logging

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user, login_required, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
import boto3 

# Import configuration, utilities, and blueprints
import config
import utils
from sne_routes import sne_bp
from blood_camp_routes import blood_camp_bp
from attendant_routes import attendant_bp
from baal_satsang_routes import baal_satsang_bp # Import the new blueprint

# --- Flask App Initialization ---
app = Flask(__name__)
app.config['SECRET_KEY'] = config.SECRET_KEY
app.config['MAX_CONTENT_LENGTH'] = config.MAX_CONTENT_LENGTH

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger(__name__) 

# --- Initialize Extensions ---
# Login Manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' 
login_manager.login_message = "Please log in to access this page."
login_manager.login_message_category = "warning"

# S3 Client 
try:
    if not hasattr(utils, 's3_client') or utils.s3_client is None:
         utils.s3_client = boto3.client('s3')
         logger.info("Initialized Boto3 S3 client in app.py")
except Exception as e:
    logger.critical(f"Failed to initialize Boto3 S3 client: {e}", exc_info=True)

# --- User Authentication ---
users_db = {
    'admin': { 'password_hash': generate_password_hash('password123'), 'id': 'admin' }
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
@login_required 
def home():
    """Displays the main home/dashboard page."""
    current_year = datetime.date.today().year
    return render_template('home.html', current_year=current_year)

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handles user login."""
    if current_user.is_authenticated:
        return redirect(url_for('home')) 

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = bool(request.form.get('remember')) 

        user = User.get(username)

        if not user or not check_password_hash(user.password_hash, password):
            flash('Invalid username or password.', 'error')
            return redirect(url_for('login'))

        login_user(user, remember=remember)
        flash('Logged in successfully!', 'success')

        next_page = request.args.get('next')
        return redirect(next_page or url_for('home'))

    return render_template('login.html')

@app.route('/logout')
@login_required 
def logout():
    """Handles user logout."""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/get_centres/<area>')
@login_required
def get_centres_for_area(area):
    """Returns a JSON list of centres for a given area based on SNE config."""
    if area in config.SNE_BADGE_CONFIG:
        centres = sorted(list(config.SNE_BADGE_CONFIG[area].keys()))
        return jsonify(centres)
    else:
        logger.warning(f"Area '{area}' not found in SNE_BADGE_CONFIG for /get_centres route.")
        return jsonify([]) 

# --- Register Blueprints ---
app.register_blueprint(sne_bp)
app.register_blueprint(blood_camp_bp)
app.register_blueprint(attendant_bp)
app.register_blueprint(baal_satsang_bp) # Register the new blueprint
logger.info("Registered blueprints: SNE, Blood Camp, Attendant, Baal Satsang")

# --- Main Execution ---
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080)) 
    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'

    logger.info(f"Starting Flask app on port {port} with debug mode: {debug_mode}")
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
    logger.info("Flask app started successfully.")
    logger.info("Flask app is running.")