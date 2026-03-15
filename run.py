import os
from dotenv import load_dotenv
from app import create_app

# Load environment variables from .env file
load_dotenv()

app = create_app()

if __name__ == '__main__':
    # SECURITY: Use Gunicorn in production instead of Flask's built-in server
    # For development only, set FLASK_ENV=development
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_ENV') == 'development'
    
    if debug_mode:
        print("WARNING: Running in debug mode. DO NOT use in production!")
    
    # Bind to 0.0.0.0 to accept external connections
    # Use firewall/security groups to restrict access
    # Enable threaded mode for concurrent request handling
    app.run(host='0.0.0.0', port=port, debug=debug_mode, threaded=True)