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
        
        # Send the actual API key for UI management
        # Note: This is for admin panel use only
        return jsonify({
            'success': True,
            'config': together_config
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
            if api_key:  # Allow any non-empty API key
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
        
        # If no API key provided, get it from config
        if not api_key:
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
            'omdb_enabled': config.get('omdb_api', {}).get('enabled', False),
            'has_omdb_key': bool(config_manager.get_omdb_api_key()),
            'search_levels': config.get('search_levels', {}),
            'fallback_responses': config.get('fallback_responses', {}),
            'chat_settings': config.get('chat_settings', {})
        })
        
    except Exception as e:
        logger.error(f"Error getting chat config: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@admin_bp.route('/api/omdb/config', methods=['GET'])
def get_omdb_config():
    """Get current OMDB API configuration"""
    try:
        omdb_config = config_manager.get_omdb_config()
        search_levels = config_manager.get_search_levels_config()
        
        return jsonify({
            'success': True,
            'omdb_config': omdb_config,
            'search_levels': search_levels
        })
    except Exception as e:
        logger.error(f"Error getting OMDB config: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@admin_bp.route('/api/omdb/config', methods=['POST'])
def update_omdb_config():
    """Update OMDB API configuration"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400
        
        # Prepare OMDB updates
        omdb_updates = {}
        
        if 'api_key' in data:
            api_key = data['api_key'].strip()
            if api_key:
                omdb_updates['api_key'] = api_key
        
        if 'enabled' in data:
            omdb_updates['enabled'] = bool(data['enabled'])
        
        if 'search_limit' in data:
            try:
                omdb_updates['search_limit'] = int(data['search_limit'])
            except ValueError:
                return jsonify({
                    'success': False,
                    'error': 'Invalid search_limit value'
                }), 400
        
        if 'include_plot' in data:
            omdb_updates['include_plot'] = bool(data['include_plot'])
        
        if 'plot_type' in data:
            plot_type = data['plot_type']
            if plot_type in ['short', 'full']:
                omdb_updates['plot_type'] = plot_type
        
        # Prepare search levels updates
        search_levels_updates = {}
        
        if 'level_1_enabled' in data:
            search_levels_updates['level_1_enabled'] = bool(data['level_1_enabled'])
        
        if 'level_2_enabled' in data:
            search_levels_updates['level_2_enabled'] = bool(data['level_2_enabled'])
        
        if 'level_1_priority' in data:
            search_levels_updates['level_1_priority'] = bool(data['level_1_priority'])
        
        if 'fallback_to_level_2' in data:
            search_levels_updates['fallback_to_level_2'] = bool(data['fallback_to_level_2'])
        
        # Update configurations
        omdb_success = True
        search_success = True
        
        if omdb_updates:
            omdb_success = config_manager.update_omdb_config(omdb_updates)
        
        if search_levels_updates:
            search_success = config_manager.update_search_levels_config(search_levels_updates)
        
        if omdb_success and search_success:
            return jsonify({
                'success': True,
                'message': 'OMDB configuration updated successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to save configuration'
            }), 500
            
    except Exception as e:
        logger.error(f"Error updating OMDB config: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@admin_bp.route('/api/omdb/test', methods=['POST'])
def test_omdb_api():
    """Test OMDB API connection"""
    try:
        data = request.get_json()
        api_key = data.get('api_key', '').strip()
        
        if not api_key:
            return jsonify({
                'success': False,
                'error': 'API key is required for testing'
            }), 400
        
        # Test the OMDB API
        result = config_manager.test_omdb_api(api_key)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error testing OMDB API: {e}")
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