import os
import sys
import logging

# Add the parent directory to the path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

# Setup environment
os.environ.setdefault('FLASK_ENV', 'production')
os.environ.setdefault('DISABLE_SELENIUM', 'true')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    # Create minimal directories
    os.makedirs('/tmp/data', exist_ok=True)
    os.makedirs('/tmp/config', exist_ok=True)
except:
    pass

# Try to import the original app with error handling
try:
    logger.info("Attempting to import web_interface...")
    from web_interface import app
    logger.info("✅ web_interface imported successfully")
    
    # Try to register admin routes
    try:
        from admin_routes import register_admin_routes
        # Check if admin blueprint is already registered
        if 'admin' not in [bp.name for bp in app.blueprints.values()]:
            register_admin_routes(app)
            logger.info("✅ Admin routes registered")
        else:
            logger.info("✅ Admin routes already registered")
    except Exception as e:
        logger.warning(f"Admin routes registration failed: {e}")
    
except Exception as e:
    logger.error(f"❌ Failed to import web_interface: {e}")
    
    # Create a minimal fallback app
    from flask import Flask, jsonify, render_template
    
    app = Flask(__name__)
    app.secret_key = 'fallback-secret-key'
    
    @app.route('/')
    def index():
        try:
            return render_template('index.html')
        except:
            return """
            <!DOCTYPE html>
            <html>
            <head><title>Movie Search App</title></head>
            <body>
                <h1>🎬 Movie Search App</h1>
                <p>Application is running in fallback mode.</p>
                <p><a href="/health">Health Check</a></p>
                <p>Error: """ + str(e) + """</p>
            </body>
            </html>
            """
    
    @app.route('/health')
    def health():
        return jsonify({
            "status": "fallback",
            "message": "Running in fallback mode",
            "error": str(e)
        })
    
    @app.route('/admin')
    def admin():
        return jsonify({
            "status": "fallback",
            "message": "Admin panel not available in fallback mode"
        })

# This is the entry point for Vercel