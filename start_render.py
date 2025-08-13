#!/usr/bin/env python3
"""
Render startup script
Ensures proper initialization before starting the web server
"""

import os
import sys
import logging
from deploy_config import setup_deployment_environment, get_port

# Setup deployment environment first
setup_deployment_environment()

# Import after environment setup
from web_interface import app

logger = logging.getLogger(__name__)

def initialize_for_render():
    """Initialize application for Render deployment"""
    try:
        # Ensure data directory exists
        os.makedirs('data', exist_ok=True)
        os.makedirs('config', exist_ok=True)
        
        # Initialize database if needed
        try:
            from add_telegram_movies import init_db
            init_db()
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.warning(f"Database initialization warning: {e}")
        
        # Test agent initialization
        try:
            from web_interface import initialize_agents
            agents = initialize_agents()
            enabled_agents = [name for name, agent in zip(
                ['downloadhub', 'moviezwap', 'movierulz', 'skysetx', 'telegram', 'movies4u'],
                agents
            ) if agent is not None]
            logger.info(f"Initialized agents: {enabled_agents}")
        except Exception as e:
            logger.warning(f"Agent initialization warning: {e}")
        
        logger.info("✅ Render initialization complete")
        return True
        
    except Exception as e:
        logger.error(f"❌ Render initialization failed: {e}")
        return False

if __name__ == '__main__':
    # Initialize for Render
    if not initialize_for_render():
        sys.exit(1)
    
    # Start the application
    port = get_port()
    logger.info(f"Starting application on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)