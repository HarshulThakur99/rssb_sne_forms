# app/__init__.py
import os
import datetime
import logging
import boto3

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user, login_required, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash

# --- Initialize Extensions ---
login_manager = LoginManager()

def create_app():
    """Create and configure an instance of the Flask application."""
    app = Flask(__name__)
    app.config.from_object('app.config') # Load config from config.py

    # --- Logging Setup ---
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s:%(name)s:%(message)s')
    logger = logging.getLogger(__name__)
    
    # --- Initialize Database (PostgreSQL) ---
    use_database = os.environ.get('USE_DATABASE', 'false').lower() == 'true'
    if use_database:
        from app.database import init_db
        init_db(app)
        logger.info("Database (PostgreSQL) initialized")
    else:
        logger.info("Using Google Sheets (Database disabled)")
    
    # --- Initialize Extensions with App Context ---
    login_manager.init_app(app)
    login_manager.login_view = 'login'
    login_manager.login_message = "Please log in to access this page."
    login_manager.login_message_category = "warning"
    
    # S3 Client
    try:
        # It's better to initialize clients within the app factory
        # if they depend on app config or need to be request-specific.
        # For a global client, this is also a good place to do it.
        s3_client = boto3.client('s3')
        app.s3_client = s3_client # You can attach it to the app instance
        logger.info("Initialized Boto3 S3 client")
    except Exception as e:
        logger.critical(f"Failed to initialize Boto3 S3 client: {e}", exc_info=True)

    # --- User Authentication & RBAC ---
    # SECURITY: Passwords are now loaded from environment variables
    # Set these in your environment or .env file (NOT committed to git)
    # Example: ADMIN_PASSWORD=your_secure_password_here
    users_db = {
        'admin': {
            'password_hash': generate_password_hash(os.environ.get('ADMIN_PASSWORD', '')), 
            'id': 'admin', 
            'role': 'admin'
        },
        'sne_full_user': {
            'password_hash': generate_password_hash(os.environ.get('SNE_USER_PASSWORD', '')), 
            'id': 'sne_full_user', 
            'role': 'sne_services_operator'
        },
        'baal_satsang_user': {
            'password_hash': generate_password_hash(os.environ.get('BAAL_SATSANG_PASSWORD', '')), 
            'id': 'baal_satsang_user', 
            'role': 'baal_satsang_operator'
        },
        'sewa_badges_user': {
            'password_hash': generate_password_hash(os.environ.get('SEWA_BADGES_PASSWORD', '')), 
            'id': 'sewa_badges_user', 
            'role': 'sewa_badges_operator'
        },
        'blood_camp_user': {
            'password_hash': generate_password_hash(os.environ.get('BLOOD_CAMP_PASSWORD', '')), 
            'id': 'blood_camp_user', 
            'role': 'blood_camp_operator'
        }
    }
    
    # Warn if any passwords are not set (only in production)
    if os.environ.get('FLASK_ENV') != 'development':
        required_passwords = ['ADMIN_PASSWORD', 'SNE_USER_PASSWORD', 'BAAL_SATSANG_PASSWORD', 
                             'SEWA_BADGES_PASSWORD', 'BLOOD_CAMP_PASSWORD']
        for pwd_env in required_passwords:
            if not os.environ.get(pwd_env):
                logger.warning(f"WARNING: {pwd_env} environment variable not set!")

    class User(UserMixin):
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
            # This is a placeholder for your actual permission logic from config.py
            # Make sure to import config at the top of this file
            from . import config
            if self.role == 'admin' and 'all_access' in config.ROLES_PERMISSIONS.get('admin', []):
                return True
            role_permissions = config.ROLES_PERMISSIONS.get(self.role, [])
            return permission_needed in role_permissions

    @login_manager.user_loader
    def load_user(user_id):
        return User.get(user_id)

    with app.app_context():
        # --- Import and Register Blueprints ---
        from .routes import sne_routes, blood_camp_routes, attendant_routes, baal_satsang_routes, mobile_token_routes, sewa_badges_routes, calling_list_routes, database_viewer_routes

        app.register_blueprint(sne_routes.sne_bp)
        app.register_blueprint(blood_camp_routes.blood_camp_bp)
        app.register_blueprint(attendant_routes.attendant_bp)
        app.register_blueprint(baal_satsang_routes.baal_satsang_bp)
        app.register_blueprint(mobile_token_routes.mobile_token_bp)
        app.register_blueprint(calling_list_routes.calling_list_bp)
        app.register_blueprint(sewa_badges_routes.sewa_badges_bp)
        app.register_blueprint(database_viewer_routes.db_viewer_bp)
        logger.info("Registered blueprints: SNE, Blood Camp, Attendant, Baal Satsang, Mobile Token, Sewa Badges, Calling List, Database Viewer")

        # --- Context Processor ---
        @app.context_processor
        def inject_global_vars():
            from . import config
            return dict(
                ROLES_PERMISSIONS=config.ROLES_PERMISSIONS,
                current_user=current_user,
                ATTENDANT_BADGE_PREFIX_CONFIG_JS=config.ATTENDANT_BADGE_PREFIX_CONFIG
            )

        # --- Core Routes ---
        @app.route('/favicon.ico')
        def favicon():
            """Serve favicon to prevent 404 errors from browser auto-requests"""
            return send_from_directory(
                os.path.join(app.root_path, 'static', 'images'),
                'rssb.jpg',
                mimetype='image/jpeg'
            )
        
        @app.route('/')
        @login_required
        def home():
            current_year = datetime.date.today().year
            return render_template('home.html', current_year=current_year)

        @app.route('/login', methods=['GET', 'POST'])
        def login():
            if current_user.is_authenticated:
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
                login_user(user_obj, remember=remember)
                flash('Logged in successfully!', 'success')
                logger.info(f"User {username} logged in successfully. Role: {user_obj.role}")

                next_page = request.args.get('next')
                return redirect(next_page or url_for('home'))

            return render_template('login.html')

        @app.route('/logout')
        @login_required
        def logout():
            logger.info(f"User {current_user.id} logging out.")
            logout_user()
            flash('You have been logged out.', 'info')
            return redirect(url_for('login'))

        @app.route('/get_centres/<area>')
        @login_required
        def get_centres_for_area(area):
            from . import config
            if area in config.SNE_BADGE_CONFIG:
                centres = sorted(list(config.SNE_BADGE_CONFIG[area].keys()))
                return jsonify(centres)
            else:
                logger.warning(f"Area '{area}' not found in SNE_BADGE_CONFIG for /get_centres route.")
                return jsonify([])
        
        # --- Error Handlers ---
        @app.errorhandler(404)
        def not_found_error(error):
            """Handle 404 Not Found errors with detailed logging"""
            logger.error(f"404 Not Found - URL: {request.url} | Method: {request.method} | IP: {request.remote_addr} | Referrer: {request.referrer}")
            flash('Page not found. Please check the URL or return to the home page.', 'error')
            return redirect(url_for('home')), 404
        
        @app.errorhandler(413)
        def request_entity_too_large(error):
            """Handle file upload size exceeded errors"""
            logger.warning(f"413 Error - Request entity too large from IP: {request.remote_addr}")
            flash('File upload size exceeded! Please ensure photos are under 2MB. Try compressing your images before uploading.', 'error')
            # Return to the referring page or home
            return redirect(request.referrer or url_for('home')), 413
        
        @app.errorhandler(Exception)
        def handle_generic_error(error):
            """Catch-all error handler for unhandled exceptions"""
            # Don't catch 404s here - they have their own handler
            from werkzeug.exceptions import NotFound
            if isinstance(error, NotFound):
                return not_found_error(error)
            logger.error(f"Unhandled exception: {error}", exc_info=True)
            flash('An unexpected error occurred. Please try again or contact support.', 'error')
            return redirect(url_for('home')), 500

    return app