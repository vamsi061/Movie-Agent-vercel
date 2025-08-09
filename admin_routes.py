#!/usr/bin/env python3
"""
Admin Routes - API endpoints for admin panel configuration
"""

from flask import Blueprint, request, jsonify, render_template, Response
import logging
from config_manager import config_manager
from agents.telegram_agent import telegram_agent

logger = logging.getLogger(__name__)

# Create admin blueprint
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# Simple Basic Auth credentials
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'vamsi061'

def check_auth(auth):
    return auth and auth.username == ADMIN_USERNAME and auth.password == ADMIN_PASSWORD

def authenticate():
    return Response(
        'Authentication required', 401,
        {'WWW-Authenticate': 'Basic realm="Admin Panel"'}
    )

@admin_bp.route('/')
def admin_panel():
    """Render admin panel"""
    auth = request.authorization
    if not check_auth(auth):
        return authenticate()
    return render_template('admin.html')

@admin_bp.route('/api/config', methods=['GET'])
def get_api_config():
    auth = request.authorization
    if not check_auth(auth):
        return authenticate()
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
    auth = request.authorization
    if not check_auth(auth):
        return authenticate()
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
    auth = request.authorization
    if not check_auth(auth):
        return authenticate()
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
    auth = request.authorization
    if not check_auth(auth):
        return authenticate()
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
    auth = request.authorization
    if not check_auth(auth):
        return authenticate()
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
    auth = request.authorization
    if not check_auth(auth):
        return authenticate()
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
        
        
        if 'include_plot' in data:
            omdb_updates['include_plot'] = bool(data['include_plot'])
        
        if 'plot_type' in data:
            plot_type = data['plot_type']
            if plot_type in ['short', 'full']:
                omdb_updates['plot_type'] = plot_type
        
        # Prepare search levels updates
        search_levels_updates = {}
        
        if 'level_1_auto_trigger' in data:
            search_levels_updates['level_1_auto_trigger'] = bool(data['level_1_auto_trigger'])
        
        if 'level_2_enabled' in data:
            search_levels_updates['level_2_enabled'] = bool(data['level_2_enabled'])
        
        if 'fallback_to_level_2' in data:
            search_levels_updates['fallback_to_level_2'] = bool(data['fallback_to_level_2'])
        
        if 'level_1_triggers' in data:
            search_levels_updates['level_1_triggers'] = data['level_1_triggers']
        
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
    auth = request.authorization
    if not check_auth(auth):
        return authenticate()
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

@admin_bp.route('/api/telegram/config', methods=['GET'])
def get_telegram_config():
    auth = request.authorization
    if not check_auth(auth):
        return authenticate()
    """Get current Telegram agent configuration"""
    try:
        stats = telegram_agent.get_stats()
        
        return jsonify({
            'success': True,
            'config': {
                'bot_token': telegram_agent.bot_token,
                'channel_id': telegram_agent.channel_id,
                'bot_username': telegram_agent.bot_username,
                'enabled': telegram_agent.enabled,
                'webhook_url': telegram_agent.webhook_url,
                'auto_add_movies': telegram_agent.auto_add_movies,
                'search_timeout': telegram_agent.search_timeout
            },
            'stats': stats
        })
    except Exception as e:
        logger.error(f"Error getting Telegram config: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@admin_bp.route('/api/telegram/config', methods=['POST'])
def update_telegram_config():
    auth = request.authorization
    if not check_auth(auth):
        return authenticate()
    """Update Telegram agent configuration"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400
        
        # Prepare configuration updates
        config_updates = {}
        
        if 'bot_token' in data:
            config_updates['bot_token'] = data['bot_token'].strip()
        
        if 'channel_id' in data:
            config_updates['channel_id'] = data['channel_id'].strip()
        
        if 'bot_username' in data:
            config_updates['bot_username'] = data['bot_username'].strip()
        
        if 'enabled' in data:
            config_updates['enabled'] = bool(data['enabled'])
        
        if 'webhook_url' in data:
            config_updates['webhook_url'] = data['webhook_url'].strip()
        
        if 'auto_add_movies' in data:
            config_updates['auto_add_movies'] = bool(data['auto_add_movies'])
        
        if 'search_timeout' in data:
            try:
                config_updates['search_timeout'] = int(data['search_timeout'])
            except ValueError:
                return jsonify({
                    'success': False,
                    'error': 'Invalid search_timeout value'
                }), 400
        
        # Save configuration
        success = telegram_agent.save_config(config_updates)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Telegram configuration updated successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to save configuration'
            }), 500
            
    except Exception as e:
        logger.error(f"Error updating Telegram config: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@admin_bp.route('/api/telegram/test', methods=['POST'])
def test_telegram_connection():
    auth = request.authorization
    if not check_auth(auth):
        return authenticate()
    """Test Telegram bot connection"""
    try:
        result = telegram_agent.test_connection()
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error testing Telegram connection: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@admin_bp.route('/api/telegram/add-movie', methods=['POST'])
def add_telegram_movie():
    auth = request.authorization
    if not check_auth(auth):
        return authenticate()
    """Add movie to Telegram database"""
    try:
        data = request.get_json()
        
        title = data.get('title', '').strip()
        message_id = data.get('message_id')
        file_info = data.get('file_info', {})
        
        if not title:
            return jsonify({
                'success': False,
                'error': 'Movie title is required'
            }), 400
        
        if not message_id:
            return jsonify({
                'success': False,
                'error': 'Message ID is required'
            }), 400
        
        try:
            message_id = int(message_id)
        except ValueError:
            return jsonify({
                'success': False,
                'error': 'Invalid message ID'
            }), 400
        
        success = telegram_agent.add_movie(title, message_id, file_info)
        
        return jsonify({
            'success': success,
            'message': 'Movie added successfully' if success else 'Failed to add movie'
        })
        
    except Exception as e:
        logger.error(f"Error adding Telegram movie: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@admin_bp.route('/api/telegram/stats', methods=['GET'])
def get_telegram_stats():
    auth = request.authorization
    if not check_auth(auth):
        return authenticate()
    """Get Telegram agent statistics"""
    try:
        stats = telegram_agent.get_stats()
        return jsonify({
            'success': True,
            'stats': stats
        })
        
    except Exception as e:
        logger.error(f"Error getting Telegram stats: {e}")
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