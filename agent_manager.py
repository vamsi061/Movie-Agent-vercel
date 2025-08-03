#!/usr/bin/env python3
"""
Agent Manager - Manages the configuration and state of all movie agents
"""

import json
import os
import logging
from typing import Dict, Any, Optional, List
from enhanced_downloadhub_agent import EnhancedDownloadHubAgent
from moviezwap_agent import MoviezWapAgent
from skysetx_agent import SkySetXAgent
from movierulz_agent import MovieRulzAgent
from telegram_agent import TelegramMovieAgent

logger = logging.getLogger(__name__)

class AgentManager:
    def __init__(self, config_file: str = 'agent_config.json'):
        self.config_file = config_file
        self.config = {}
        self.agents = {}
        self.load_configuration()
        
    def load_configuration(self):
        """Load agent configuration from file"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    self.config = json.load(f)
            else:
                # Create default configuration
                self.config = {
                    "agents": {
                        "downloadhub": {
                            "name": "Enhanced DownloadHub Agent",
                            "enabled": True,
                            "description": "Searches and extracts download links from DownloadHub"
                        },
                        "moviezwap": {
                            "name": "MoviezWap Agent",
                            "enabled": True,
                            "description": "Searches and extracts download links from MoviezWap"
                        },
                        "movierulz": {
                            "name": "MovieRulz Agent",
                            "enabled": True,
                            "description": "Searches and extracts download links from MovieRulz"
                        },
                        "skysetx": {
                            "name": "SkySetX Agent",
                            "enabled": True,
                            "description": "Searches and extracts download links from SkySetX"
                        },
                        "telegram": {
                            "name": "Telegram Movie Agent",
                            "enabled": False,
                            "description": "Searches movies through Telegram channels"
                        }
                    }
                }
                self.save_configuration()
        except Exception as e:
            logger.error(f"Error loading agent configuration: {str(e)}")
            self.config = {"agents": {}}
    
    def save_configuration(self):
        """Save agent configuration to file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
            logger.info("Agent configuration saved successfully")
        except Exception as e:
            logger.error(f"Error saving agent configuration: {str(e)}")
    
    def get_configuration(self) -> Dict[str, Any]:
        """Get the current agent configuration"""
        return self.config
    
    def is_agent_enabled(self, agent_key: str) -> bool:
        """Check if an agent is enabled"""
        return self.config.get("agents", {}).get(agent_key, {}).get("enabled", False)
    
    def toggle_agent(self, agent_key: str, enabled: bool) -> bool:
        """Toggle an agent's enabled state"""
        try:
            if agent_key in self.config.get("agents", {}):
                self.config["agents"][agent_key]["enabled"] = enabled
                self.save_configuration()
                
                # Reinitialize agents to reflect changes
                self.initialize_agents()
                
                logger.info(f"Agent {agent_key} {'enabled' if enabled else 'disabled'}")
                return True
            else:
                logger.error(f"Agent {agent_key} not found in configuration")
                return False
        except Exception as e:
            logger.error(f"Error toggling agent {agent_key}: {str(e)}")
            return False
    
    def enable_all_agents(self):
        """Enable all agents"""
        try:
            for agent_key in self.config.get("agents", {}):
                self.config["agents"][agent_key]["enabled"] = True
            self.save_configuration()
            self.initialize_agents()
            logger.info("All agents enabled")
        except Exception as e:
            logger.error(f"Error enabling all agents: {str(e)}")
    
    def disable_all_agents(self):
        """Disable all agents"""
        try:
            for agent_key in self.config.get("agents", {}):
                self.config["agents"][agent_key]["enabled"] = False
            self.save_configuration()
            self.initialize_agents()
            logger.info("All agents disabled")
        except Exception as e:
            logger.error(f"Error disabling all agents: {str(e)}")
    
    def initialize_agents(self):
        """Initialize enabled agents"""
        self.agents = {}
        
        try:
            # Initialize DownloadHub Agent
            if self.is_agent_enabled("downloadhub"):
                self.agents["downloadhub"] = EnhancedDownloadHubAgent()
                logger.info("DownloadHub agent initialized")
            
            # Initialize MoviezWap Agent
            if self.is_agent_enabled("moviezwap"):
                self.agents["moviezwap"] = MoviezWapAgent()
                logger.info("MoviezWap agent initialized")
            
            # Initialize MovieRulz Agent
            if self.is_agent_enabled("movierulz"):
                self.agents["movierulz"] = MovieRulzAgent()
                logger.info("MovieRulz agent initialized")
            
            # Initialize SkySetX Agent
            if self.is_agent_enabled("skysetx"):
                self.agents["skysetx"] = SkySetXAgent()
                logger.info("SkySetX agent initialized")
            
            # Initialize Telegram Agent
            if self.is_agent_enabled("telegram"):
                try:
                    # Load Telegram config
                    with open('telegram_config.json', 'r') as f:
                        config = json.load(f)
                        telegram_config = config.get('telegram_settings', {})
                        if telegram_config.get('enabled', False):
                            self.agents["telegram"] = TelegramMovieAgent(telegram_config)
                            logger.info("Telegram agent initialized")
                        else:
                            logger.warning("Telegram agent enabled in agent config but disabled in telegram_config.json")
                except Exception as e:
                    logger.warning(f"Failed to initialize Telegram agent: {str(e)}")
            
        except Exception as e:
            logger.error(f"Error initializing agents: {str(e)}")
    
    def get_enabled_agents(self) -> Dict[str, Any]:
        """Get all enabled and initialized agents"""
        return self.agents
    
    def get_agent(self, agent_key: str) -> Optional[Any]:
        """Get a specific agent if it's enabled and initialized"""
        return self.agents.get(agent_key)
    
    def get_enabled_agent_names(self) -> List[str]:
        """Get list of enabled agent names"""
        return [
            self.config["agents"][key]["name"] 
            for key in self.config.get("agents", {}) 
            if self.config["agents"][key]["enabled"]
        ]
    
    def get_agent_stats(self) -> Dict[str, int]:
        """Get statistics about agents"""
        total_agents = len(self.config.get("agents", {}))
        enabled_agents = sum(1 for agent in self.config.get("agents", {}).values() if agent.get("enabled", False))
        disabled_agents = total_agents - enabled_agents
        
        return {
            "total": total_agents,
            "enabled": enabled_agents,
            "disabled": disabled_agents
        }
    
    def update_agent_url(self, agent_key: str, base_url: str, search_url: str = None) -> bool:
        """Update an agent's URL configuration"""
        try:
            if agent_key in self.config.get("agents", {}):
                self.config["agents"][agent_key]["base_url"] = base_url
                if search_url:
                    self.config["agents"][agent_key]["search_url"] = search_url
                else:
                    # Auto-generate search URL if not provided
                    self.config["agents"][agent_key]["search_url"] = f"{base_url}/?s="
                
                # Update last modified timestamp
                from datetime import datetime
                self.config["agents"][agent_key]["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                self.save_configuration()
                
                # Reinitialize agents to use new URLs
                self.initialize_agents()
                
                logger.info(f"Updated URLs for agent {agent_key}: {base_url}")
                return True
            else:
                logger.error(f"Agent {agent_key} not found in configuration")
                return False
        except Exception as e:
            logger.error(f"Error updating agent URLs for {agent_key}: {str(e)}")
            return False
    
    def get_agent_url(self, agent_key: str) -> Dict[str, str]:
        """Get an agent's URL configuration"""
        agent_config = self.config.get("agents", {}).get(agent_key, {})
        return {
            "base_url": agent_config.get("base_url", ""),
            "search_url": agent_config.get("search_url", ""),
            "last_updated": agent_config.get("last_updated", "")
        }