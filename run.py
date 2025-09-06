# This is now app.py
import os
from app import create_app # This import still works correctly

app = create_app()

if __name__ == '__main__':
    # These settings are for local development (python app.py)
    # Gunicorn will use its own settings from the command line
    port = int(os.environ.get('PORT', 5000))
    app.run(host='127.0.0.1', port=port, debug=True)