import os
import sys

# Add the parent directory to the path so we can import from the root
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

# Setup environment for Vercel
os.environ.setdefault('FLASK_ENV', 'production')
os.environ.setdefault('DISABLE_SELENIUM', 'true')

# Setup directories for serverless
try:
    os.makedirs('/tmp/data', exist_ok=True)
    os.makedirs('/tmp/config', exist_ok=True)
except:
    pass

# Import the original Flask app
from web_interface import app

# Register admin routes
try:
    from admin_routes import register_admin_routes
    register_admin_routes(app)
except Exception as e:
    print(f"Warning: Could not register admin routes: {e}")

# This is the entry point for Vercel