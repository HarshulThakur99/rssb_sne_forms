# run.py
import os
from app import create_app

app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    debug_mode = os.environ.get('FLASK_DEBUG', 'true').lower() == 'true'
    
    # The logger is now configured inside create_app, 
    # but you can add more logging here if needed.
    app.logger.info(f"Starting Flask app on port {port} with debug mode: {debug_mode}")
    app.run(host='0.0.0.0', port=port, debug=debug_mode)