# app.py (Refactored with RBAC and circular import fix)
import os
import datetime
import logging
# from functools import wraps # No longer needed here, moved to decorators.py

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify # Removed abort, using redirect
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user, login_required, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
import boto3

# Import configuration, utilities
import config # Make sure config is imported to access ROLES_PERMISSIONS
import utils
# Import blueprints AFTER app and login_manager are initialized, and User class is defined.
# This helps prevent circular dependencies if blueprints need to import 'app' or 'current_user'.
from sne_routes import sne_bp
from blood_camp_routes import blood_camp_bp
from attendant_routes import attendant_bp
from baal_satsang_routes import baal_satsang_bp

# Import the decorator from the new file
from decorators import permission_required


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
login_manager.login_view = 'login' # Name of the login route
login_manager.login_message = "Please log in to access this page."
login_manager.login_message_category = "warning"

# S3 Client
try:
    if not hasattr(utils, 's3_client') or utils.s3_client is None:
         utils.s3_client = boto3.client('s3')
         logger.info("Initialized Boto3 S3 client in app.py")
except Exception as e:
    logger.critical(f"Failed to initialize Boto3 S3 client: {e}", exc_info=True)

# --- User Authentication & RBAC ---
# Define users with roles. Ensure passwords are changed for production.
users_db = {
    'admin_user': {'password_hash': generate_password_hash('adminpass'), 'id': 'admin_user', 'role': 'admin'},
    'sne_full_user': {'password_hash': generate_password_hash('snepass'), 'id': 'sne_full_user', 'role': 'sne_services_operator'},
    'bs_user': {'password_hash': generate_password_hash('bspass'), 'id': 'bs_user', 'role': 'baal_satsang_operator'},
    'bc_user': {'password_hash': generate_password_hash('bloodpass'), 'id': 'bc_user', 'role': 'blood_camp_operator'}
}

class User(UserMixin):
    """User class for Flask-Login with role and permission checking."""
    def __init__(self, id, password_hash, role):
        self.id = id
        self.password_hash = password_hash
        self.role = role

    @staticmethod
    def get(user_id):
        user_data = users_db.get(user_id)
        if user_data:
            return User(id=user_data['id'],
                        password_hash=user_data['password_hash'],
                        role=user_data.get('role'))
        return None

    def has_permission(self, permission_needed):
        """Checks if the user's role has the required permission."""
        if not self.role:
            return False
        if self.role == 'admin' and 'all_access' in config.ROLES_PERMISSIONS.get('admin', []):
            return True
        role_permissions = config.ROLES_PERMISSIONS.get(self.role, [])
        return permission_needed in role_permissions

@login_manager.user_loader
def load_user(user_id):
    """Flask-Login user loader callback."""
    return User.get(user_id)

# --- Custom Decorator for Permission Checking ---
# MOVED to decorators.py

# --- Context Processor to make ROLES_PERMISSIONS available in templates ---
@app.context_processor
def inject_global_vars():
    """Makes specified variables globally available in all templates."""
    # current_user is already available in templates if Flask-Login is configured.
    # Explicitly adding it here ensures it if there's any doubt or for clarity.
    return dict(ROLES_PERMISSIONS=config.ROLES_PERMISSIONS, current_user=current_user)


# --- Core Routes ---
@app.route('/')
@login_required # Ensures user is logged in to see the home page
def home():
    """Displays the main home/dashboard page."""
    current_year = datetime.date.today().year
    # current_user is available globally due to Flask-Login and context_processor
    return render_template('home.html', current_year=current_year)

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handles user login."""
    if current_user.is_authenticated: # current_user from Flask-Login
        return redirect(url_for('home'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = bool(request.form.get('remember'))

        user_data = users_db.get(username)

        if not user_data or not check_password_hash(user_data['password_hash'], password):
            flash('Invalid username or password.', 'error')
            return redirect(url_for('login'))

        user_obj = User(id=user_data['id'], password_hash=user_data['password_hash'], role=user_data.get('role'))
        login_user(user_obj, remember=remember) # login_user from Flask-Login
        flash('Logged in successfully!', 'success')
        logger.info(f"User {username} logged in successfully. Role: {user_obj.role}")

        next_page = request.args.get('next')
        return redirect(next_page or url_for('home'))

    return render_template('login.html')

@app.route('/logout')
@login_required # Ensures only logged-in users can access logout
def logout():
    """Handles user logout."""
    logger.info(f"User {current_user.id} logging out.") # current_user from Flask-Login
    logout_user() # logout_user from Flask-Login
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/get_centres/<area>')
@login_required # Basic login check
@permission_required('get_centres') # Specific permission check using the imported decorator
def get_centres_for_area(area):
    """Returns a JSON list of centres for a given area based on SNE config."""
    if area in config.SNE_BADGE_CONFIG:
        centres = sorted(list(config.SNE_BADGE_CONFIG[area].keys()))
        return jsonify(centres)
    else:
        logger.warning(f"Area '{area}' not found in SNE_BADGE_CONFIG for /get_centres route.")
        return jsonify([])

# --- Register Blueprints ---
# These should be registered after 'app' is defined.
app.register_blueprint(sne_bp)
app.register_blueprint(blood_camp_bp)
app.register_blueprint(attendant_bp)
app.register_blueprint(baal_satsang_bp)
logger.info("Registered blueprints: SNE, Blood Camp, Attendant, Baal Satsang")

# --- Main Execution ---
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    # For production, debug should ideally be False or controlled by an environment variable.
    debug_mode = os.environ.get('FLASK_DEBUG', 'true').lower() == 'true' # Default to True for dev

    logger.info(f"Starting Flask app on port {port} with debug mode: {debug_mode}")
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
