#!/usr/bin/env python3
"""
Deployment configuration for Render
Handles environment-specific settings and graceful fallbacks
"""

import os
import logging

logger = logging.getLogger(__name__)

def setup_deployment_environment():
    """Setup environment for deployment"""
    
    # Create necessary directories
    os.makedirs('data', exist_ok=True)
    os.makedirs('config', exist_ok=True)
    
    # Set deployment flags
    os.environ.setdefault('FLASK_ENV', 'production')
    os.environ.setdefault('DISABLE_SELENIUM', 'true')
    
    # Configure logging for production
    if os.environ.get('FLASK_ENV') == 'production':
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    logger.info("Deployment environment configured")

def get_port():
    """Get port from environment or default"""
    return int(os.environ.get('PORT', 8080))

def is_production():
    """Check if running in production"""
    return os.environ.get('FLASK_ENV') == 'production'

def selenium_disabled():
    """Check if Selenium is disabled"""
    return os.environ.get('DISABLE_SELENIUM', '').lower() == 'true'

if __name__ == '__main__':
    setup_deployment_environment()
    print("✅ Deployment environment setup complete")