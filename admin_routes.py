#!/usr/bin/env python3
"""
Admin Routes - API endpoints for admin panel configuration
"""

from flask import Blueprint, request, jsonify, render_template
import logging
from config_manager import config_manager

logger = logging.getLogger(__name__)

# Create admin blueprint
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/')
def admin_panel():
    """Render admin panel"""
    return render_template('admin.html')

@admin_bp.route('/api/config', methods=['GET'])
def get_api_config():
    """Get current API configuration"""
    try:
        llm_config = config_manager.load_llm_config()
        together_config = llm_config.get('together_api', {})
        
        # Don't send the actual API key for security
        safe_config = together_config.copy()
        if safe_config.get('api_key'):
            safe_config['api_key'] = '***HIDDEN***'
        
        return jsonify({
            'success': True,
            'config': safe_config
        })
    except Exception as e:
        logger.error(f"Error getting API config: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@admin_bp.route('/api/config', methods=['POST'])
def update_api_config():
    """Update API configuration"""
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400
        
        # Prepare updates
        updates = {}
        
        if 'api_key' in data:
            api_key = data['api_key'].strip()
            if api_key and api_key != '***HIDDEN***':
                updates['api_key'] = api_key
        
        if 'enabled' in data:
            updates['enabled'] = bool(data['enabled'])
        
        if 'model' in data:
            updates['model'] = data['model']
        
        if 'max_tokens' in data:
            try:
                updates['max_tokens'] = int(data['max_tokens'])
            except ValueError:
                return jsonify({
                    'success': False,
                    'error': 'Invalid max_tokens value'
                }), 400
        
        if 'temperature' in data:
            try:
                updates['temperature'] = float(data['temperature'])
            except ValueError:
                return jsonify({
                    'success': False,
                    'error': 'Invalid temperature value'
                }), 400
        
        # Update configuration
        success = config_manager.update_together_config(updates)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Configuration updated successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to save configuration'
            }), 500
            
    except Exception as e:
        logger.error(f"Error updating API config: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@admin_bp.route('/api/test', methods=['POST'])
def test_api():
    """Test API connection"""
    try:
        data = request.get_json()
        api_key = data.get('api_key', '').strip()
        
        if not api_key:
            return jsonify({
                'success': False,
                'error': 'API key is required for testing'
            }), 400
        
        # If API key is hidden, get it from config
        if api_key == '***HIDDEN***':
            api_key = config_manager.get_together_api_key()
            if not api_key:
                return jsonify({
                    'success': False,
                    'error': 'No API key found in configuration'
                }), 400
        
        # Test the API
        result = config_manager.test_together_api(api_key)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error testing API: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@admin_bp.route('/chat/config', methods=['GET'])
def get_chat_config():
    """Get chat configuration for the LLM agent"""
    try:
        config = config_manager.load_llm_config()
        
        return jsonify({
            'success': True,
            'together_enabled': config.get('together_api', {}).get('enabled', False),
            'has_api_key': bool(config_manager.get_together_api_key()),
            'fallback_responses': config.get('fallback_responses', {}),
            'chat_settings': config.get('chat_settings', {})
        })
        
    except Exception as e:
        logger.error(f"Error getting chat config: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def register_admin_routes(app):
    """Register admin routes with Flask app"""
    app.register_blueprint(admin_bp)
    logger.info("Admin routes registered successfully")

if __name__ == "__main__":
    # Test the admin routes
    from flask import Flask
    
    app = Flask(__name__)
    register_admin_routes(app)
    
    print("✅ Admin routes created successfully!")
    print("Available routes:")
    for rule in app.url_map.iter_rules():
        if rule.endpoint.startswith('admin'):
            print(f"  {rule.rule} -> {rule.endpoint}")