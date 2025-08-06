#!/usr/bin/env python3
"""
Configuration Manager - Handles API key and configuration management
"""

import json
import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class ConfigManager:
    def __init__(self):
        self.config_dir = os.path.dirname(os.path.abspath(__file__))
        self.llm_config_path = os.path.join(self.config_dir, 'llm_config.json')
        self.agent_config_path = os.path.join(self.config_dir, 'agent_config.json')
        
    def load_llm_config(self) -> Dict[str, Any]:
        """Load LLM configuration from file"""
        try:
            with open(self.llm_config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading LLM config: {e}")
            return self._get_default_llm_config()
    
    def save_llm_config(self, config: Dict[str, Any]) -> bool:
        """Save LLM configuration to file"""
        try:
            with open(self.llm_config_path, 'w') as f:
                json.dump(config, f, indent=2)
            logger.info("LLM configuration saved successfully")
            return True
        except Exception as e:
            logger.error(f"Error saving LLM config: {e}")
            return False
    
    def get_together_api_key(self) -> Optional[str]:
        """Get Together API key from config or environment"""
        # First check config file
        config = self.load_llm_config()
        api_key = config.get('together_api', {}).get('api_key', '')
        
        if api_key and api_key.strip():
            return api_key.strip()
        
        # Fallback to environment variable
        env_key = os.getenv('TOGETHER_API_KEY')
        if env_key and env_key.strip():
            return env_key.strip()
        
        return None
    
    def is_together_api_enabled(self) -> bool:
        """Check if Together API is enabled"""
        config = self.load_llm_config()
        return config.get('together_api', {}).get('enabled', False)
    
    def get_together_config(self) -> Dict[str, Any]:
        """Get complete Together API configuration"""
        config = self.load_llm_config()
        together_config = config.get('together_api', {})
        
        # Add API key from environment if not in config
        if not together_config.get('api_key'):
            env_key = os.getenv('TOGETHER_API_KEY')
            if env_key:
                together_config['api_key'] = env_key
        
        return together_config
    
    def update_together_config(self, updates: Dict[str, Any]) -> bool:
        """Update Together API configuration"""
        try:
            config = self.load_llm_config()
            
            # Update together_api section
            if 'together_api' not in config:
                config['together_api'] = {}
            
            config['together_api'].update(updates)
            config['together_api']['last_updated'] = self._get_current_timestamp()
            
            return self.save_llm_config(config)
        except Exception as e:
            logger.error(f"Error updating Together config: {e}")
            return False
    
    def test_together_api(self, api_key: str) -> Dict[str, Any]:
        """Test Together API connection"""
        try:
            from together import Together
            
            client = Together(api_key=api_key)
            
            # Test with a simple completion
            response = client.chat.completions.create(
                model="mistralai/Mixtral-8x7B-Instruct-v0.1",
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=10,
                temperature=0.1
            )
            
            return {
                "success": True,
                "message": "API connection successful",
                "response_length": len(response.choices[0].message.content)
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"API test failed: {str(e)}"
            }
    
    def _get_default_llm_config(self) -> Dict[str, Any]:
        """Get default LLM configuration"""
        return {
            "together_api": {
                "enabled": False,
                "api_key": "",
                "model": "mistralai/Mixtral-8x7B-Instruct-v0.1",
                "max_tokens": 500,
                "temperature": 0.7,
                "description": "Together API configuration for LLM chat features",
                "last_updated": self._get_current_timestamp()
            },
            "fallback_responses": {
                "no_api_key": "I'm sorry, but the AI chat feature is currently unavailable. You can still search for movies using the main search page!",
                "error_response": "Sorry, I encountered an error. Please try again.",
                "welcome_message": "Hi! I'm your AI movie assistant. Tell me what kind of movie you're in the mood for!"
            },
            "chat_settings": {
                "max_conversation_history": 10,
                "search_result_limit": 10,
                "agent_result_limit": 3,
                "confidence_threshold": 0.3
            }
        }
    
    def _get_current_timestamp(self) -> str:
        """Get current timestamp"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Global instance
config_manager = ConfigManager()

def get_together_api_key() -> Optional[str]:
    """Convenience function to get Together API key"""
    return config_manager.get_together_api_key()

def is_together_api_enabled() -> bool:
    """Convenience function to check if Together API is enabled"""
    return config_manager.is_together_api_enabled()

if __name__ == "__main__":
    # Test the config manager
    cm = ConfigManager()
    
    print("LLM Config:", json.dumps(cm.load_llm_config(), indent=2))
    print("Together API Key:", cm.get_together_api_key())
    print("Together API Enabled:", cm.is_together_api_enabled())