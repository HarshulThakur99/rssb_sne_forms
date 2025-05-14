# decorators.py
from functools import wraps
from flask import flash, redirect, url_for, request # Added request for 'next' URL
from flask_login import current_user
# Note: We don't import 'app' or 'login_manager' here to avoid new circular dependencies.
# login_manager.unauthorized() is typically called by Flask-Login itself if @login_required is used.

def permission_required(permission):
    """
    Custom decorator to check if the logged-in user has the required permission.
    This decorator should be placed *after* @login_required.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # The @login_required decorator should handle unauthenticated users.
            # This is an additional safeguard.
            if not current_user.is_authenticated:
                flash("Please log in to access this page.", "warning")
                # 'login' should be the name of your login route in app.py
                return redirect(url_for('login', next=request.path)) 

            # Check if current_user has the 'has_permission' method and the permission
            if not hasattr(current_user, 'has_permission') or not current_user.has_permission(permission):
                # Consider logging this attempt for security auditing if desired
                # import logging
                # logger = logging.getLogger(__name__) # Or get app's logger
                # logger.warning(f"User {current_user.id} (Role: {getattr(current_user, 'role', 'N/A')}) "
                #                f"attempted to access '{permission}' without permission.")
                
                flash(f"You do not have permission to access this page. (Required: {permission})", "error")
                # 'home' should be the name of your main/home route in app.py
                return redirect(url_for('home')) 
            return f(*args, **kwargs)
        return decorated_function
    return decorator
