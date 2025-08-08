#!/usr/bin/env python3
"""
Telegram Agent - Movie file forwarding from private channel
Integrates with the existing agent system for seamless movie delivery
"""

import os
import json
import logging
import sqlite3
import requests
from typing import Dict, List, Optional, Any
from pathlib import Path
import re
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TelegramAgent:
    def __init__(self):
        """Initialize Telegram Agent"""
        self.name = "Telegram Agent"
        self.description = "Forward movies from private Telegram channel to users"
        self.enabled = True
        self.priority = 1  # High priority for instant delivery
        
        # Load configuration
        self.load_config()
        
        # Initialize database
        self.init_database()
    
    def load_config(self):
        """Load Telegram configuration"""
        try:
            # Try to load from config file first
            config_path = Path("config") / "telegram_config.json"
            if config_path.exists():
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    
                self.bot_token = config.get('bot_token', '')
                self.channel_id = config.get('channel_id', '')
                self.bot_username = config.get('bot_username', 'MoviesAgent123bot')
                self.enabled = config.get('enabled', False)
                self.webhook_url = config.get('webhook_url', '')
                self.auto_add_movies = config.get('auto_add_movies', True)
                self.search_timeout = config.get('search_timeout', 30)
            else:
                # Fallback to environment variables
                self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
                self.channel_id = os.getenv('TELEGRAM_CHANNEL_ID', '')
                self.bot_username = os.getenv('TELEGRAM_BOT_USERNAME', 'MoviesAgent123bot')
                self.enabled = os.getenv('TELEGRAM_ENABLED', 'false').lower() == 'true'
                self.webhook_url = os.getenv('TELEGRAM_WEBHOOK_URL', '')
                self.auto_add_movies = True
                self.search_timeout = 30
            
            # Validate configuration
            if self.enabled and not self.bot_token:
                logger.error("Telegram bot token is required when agent is enabled")
                self.enabled = False
                
            if self.enabled and not self.channel_id:
                logger.error("Telegram channel ID is required when agent is enabled")
                self.enabled = False
            
            self.base_url = f"https://api.telegram.org/bot{self.bot_token}" if self.bot_token else ""
            
        except Exception as e:
            logger.error(f"Error loading Telegram config: {e}")
            self.enabled = False
    
    def save_config(self, config_data: Dict[str, Any]) -> bool:
        """Save Telegram configuration"""
        try:
            config_dir = Path("config")
            config_dir.mkdir(exist_ok=True)
            
            config_path = config_dir / "telegram_config.json"
            
            # Update current config
            self.bot_token = config_data.get('bot_token', self.bot_token)
            self.channel_id = config_data.get('channel_id', self.channel_id)
            self.bot_username = config_data.get('bot_username', self.bot_username)
            self.enabled = config_data.get('enabled', self.enabled)
            self.webhook_url = config_data.get('webhook_url', self.webhook_url)
            self.auto_add_movies = config_data.get('auto_add_movies', self.auto_add_movies)
            self.search_timeout = config_data.get('search_timeout', self.search_timeout)
            
            # Save to file
            config = {
                'bot_token': self.bot_token,
                'channel_id': self.channel_id,
                'bot_username': self.bot_username,
                'enabled': self.enabled,
                'webhook_url': self.webhook_url,
                'auto_add_movies': self.auto_add_movies,
                'search_timeout': self.search_timeout,
                'last_updated': datetime.now().isoformat()
            }
            
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)
            
            # Update base URL
            self.base_url = f"https://api.telegram.org/bot{self.bot_token}" if self.bot_token else ""
            
            logger.info("Telegram configuration saved successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error saving Telegram config: {e}")
            return False
    
    def init_database(self):
        """Initialize SQLite database for movie mappings"""
        try:
            db_path = Path("data") / "telegram_movies.db"
            db_path.parent.mkdir(exist_ok=True)
            
            self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
            
            # Create movies table
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS telegram_movies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    normalized_title TEXT NOT NULL,
                    message_id INTEGER NOT NULL,
                    file_id TEXT,
                    file_type TEXT,
                    file_size INTEGER,
                    year TEXT,
                    quality TEXT,
                    language TEXT,
                    source_url TEXT,
                    added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_accessed TIMESTAMP,
                    access_count INTEGER DEFAULT 0,
                    UNIQUE(message_id)
                )
            ''')
            
            # Create search logs table
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS telegram_search_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    chat_id INTEGER,
                    movie_title TEXT,
                    found BOOLEAN,
                    forwarded BOOLEAN,
                    error_message TEXT,
                    search_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create indexes for better performance
            self.conn.execute('CREATE INDEX IF NOT EXISTS idx_normalized_title ON telegram_movies(normalized_title)')
            self.conn.execute('CREATE INDEX IF NOT EXISTS idx_search_date ON telegram_search_logs(search_date)')
            
            self.conn.commit()
            logger.info("Telegram database initialized successfully")
            
        except Exception as e:
            logger.error(f"Telegram database initialization failed: {e}")
            self.enabled = False
    
    def normalize_title(self, title: str) -> str:
        """Normalize movie title for better matching"""
        # Convert to lowercase
        title = title.lower().strip()
        
        # Remove special characters and extra spaces
        title = re.sub(r'[^\w\s]', ' ', title)
        title = re.sub(r'\s+', ' ', title)
        
        # Remove common words that might interfere with search
        common_words = ['movie', 'film', 'full', 'hd', 'bluray', 'dvdrip', 'webrip', 'the', 'a', 'an']
        words = title.split()
        words = [word for word in words if word not in common_words]
        
        return ' '.join(words).strip()
    
    def search_movies(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """Search for movies in Telegram database (Agent interface method)"""
        if not self.enabled:
            return []
        
        try:
            normalized_query = self.normalize_title(query)
            
            cursor = self.conn.cursor()
            
            # Try exact match first
            cursor.execute('''
                SELECT * FROM telegram_movies 
                WHERE normalized_title = ? 
                ORDER BY access_count DESC, added_date DESC
            ''', (normalized_query,))
            
            results = cursor.fetchall()
            
            # If no exact match, try partial match
            if not results:
                cursor.execute('''
                    SELECT * FROM telegram_movies 
                    WHERE normalized_title LIKE ? OR title LIKE ?
                    ORDER BY access_count DESC, added_date DESC
                    LIMIT 10
                ''', (f'%{normalized_query}%', f'%{query}%'))
                
                results = cursor.fetchall()
            
            # Convert to agent format
            movies = []
            columns = [desc[0] for desc in cursor.description]
            
            for row in results:
                movie_data = dict(zip(columns, row))
                
                # Convert to standard agent format
                movie = {
                    'title': movie_data['title'],
                    'year': movie_data.get('year', 'Unknown'),
                    'quality': movie_data.get('quality', 'Unknown'),
                    'language': movie_data.get('language', 'Unknown'),
                    'source': 'Telegram',
                    'url': f"telegram://message/{movie_data['message_id']}",
                    'detail_url': f"https://t.me/{self.bot_username}?start={movie_data['title'].replace(' ', '_')}",
                    'telegram_message_id': movie_data['message_id'],
                    'telegram_file_id': movie_data.get('file_id'),
                    'file_size': movie_data.get('file_size'),
                    'access_count': movie_data.get('access_count', 0),
                    'agent': 'telegram'
                }
                
                movies.append(movie)
            
            logger.info(f"Telegram agent found {len(movies)} movies for query: {query}")
            return movies
            
        except Exception as e:
            logger.error(f"Error searching Telegram movies: {e}")
            return []
    
    def get_movie_details(self, movie_url: str) -> Dict[str, Any]:
        """Get detailed movie information (Agent interface method)"""
        if not self.enabled or not movie_url.startswith('telegram://'):
            return {}
        
        try:
            # Extract message ID from URL
            message_id = movie_url.split('/')[-1]
            
            cursor = self.conn.cursor()
            cursor.execute('SELECT * FROM telegram_movies WHERE message_id = ?', (message_id,))
            result = cursor.fetchone()
            
            if result:
                columns = [desc[0] for desc in cursor.description]
                movie_data = dict(zip(columns, result))
                
                return {
                    'title': movie_data['title'],
                    'year': movie_data.get('year'),
                    'quality': movie_data.get('quality'),
                    'language': movie_data.get('language'),
                    'file_size': movie_data.get('file_size'),
                    'file_type': movie_data.get('file_type'),
                    'telegram_message_id': movie_data['message_id'],
                    'telegram_file_id': movie_data.get('file_id'),
                    'deep_link': f"https://t.me/{self.bot_username}?start={movie_data['title'].replace(' ', '_')}",
                    'added_date': movie_data.get('added_date'),
                    'access_count': movie_data.get('access_count', 0)
                }
            
            return {}
            
        except Exception as e:
            logger.error(f"Error getting Telegram movie details: {e}")
            return {}
    
    def forward_movie_to_user(self, movie_title: str, chat_id: int, user_id: int = None) -> Dict[str, Any]:
        """Forward movie from channel to user"""
        if not self.enabled:
            return {'success': False, 'error': 'Telegram agent is disabled'}
        
        try:
            # Search for movie
            movies = self.search_movies(movie_title)
            
            if not movies:
                self.log_search(user_id or chat_id, chat_id, movie_title, False, False, "Movie not found")
                return {
                    'success': False,
                    'error': 'Movie not found',
                    'message': f"Sorry, I couldn't find '{movie_title}' in our Telegram collection."
                }
            
            # Get the best match
            best_match = movies[0]
            message_id = best_match['telegram_message_id']
            
            # Forward the message
            forward_result = self.forward_message(chat_id, message_id)
            
            # Update access count
            if forward_result['success']:
                self.update_access_count(message_id)
            
            # Log search activity
            self.log_search(
                user_id or chat_id,
                chat_id,
                movie_title,
                True,
                forward_result['success'],
                forward_result.get('error')
            )
            
            if forward_result['success']:
                return {
                    'success': True,
                    'message': f"Found and sent '{best_match['title']}'!",
                    'movie_info': {
                        'title': best_match['title'],
                        'year': best_match['year'],
                        'quality': best_match['quality'],
                        'language': best_match['language']
                    }
                }
            else:
                return {
                    'success': False,
                    'error': 'Failed to forward movie',
                    'message': f"Found '{best_match['title']}' but couldn't send it. Please try again."
                }
                
        except Exception as e:
            logger.error(f"Error forwarding movie: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': "An error occurred while forwarding the movie."
            }
    
    def forward_message(self, chat_id: int, message_id: int) -> Dict[str, Any]:
        """Forward message from private channel to user"""
        try:
            url = f"{self.base_url}/forwardMessage"
            data = {
                'chat_id': chat_id,
                'from_chat_id': self.channel_id,
                'message_id': message_id
            }
            
            response = requests.post(url, json=data, timeout=self.search_timeout)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get('ok'):
                logger.info(f"Successfully forwarded message {message_id} to chat {chat_id}")
                return {'success': True, 'data': result.get('result')}
            else:
                error_msg = result.get('description', 'Unknown error')
                logger.error(f"Failed to forward message: {error_msg}")
                return {'success': False, 'error': error_msg}
            
        except Exception as e:
            logger.error(f"Error forwarding message: {e}")
            return {'success': False, 'error': str(e)}
    
    def send_message(self, chat_id: int, text: str, parse_mode: str = 'HTML') -> Dict[str, Any]:
        """Send text message to user"""
        try:
            url = f"{self.base_url}/sendMessage"
            data = {
                'chat_id': chat_id,
                'text': text,
                'parse_mode': parse_mode
            }
            
            response = requests.post(url, json=data, timeout=self.search_timeout)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get('ok'):
                return {'success': True, 'data': result.get('result')}
            else:
                return {'success': False, 'error': result.get('description')}
            
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return {'success': False, 'error': str(e)}
    
    def add_movie(self, title: str, message_id: int, file_info: Dict = None) -> bool:
        """Add movie to database"""
        try:
            normalized_title = self.normalize_title(title)
            
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO telegram_movies 
                (title, normalized_title, message_id, file_id, file_type, file_size, year, quality, language, source_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                title,
                normalized_title,
                message_id,
                file_info.get('file_id') if file_info else None,
                file_info.get('file_type') if file_info else None,
                file_info.get('file_size') if file_info else None,
                file_info.get('year') if file_info else None,
                file_info.get('quality') if file_info else None,
                file_info.get('language') if file_info else None,
                file_info.get('source_url') if file_info else None
            ))
            
            self.conn.commit()
            logger.info(f"Added movie to Telegram database: {title} (Message ID: {message_id})")
            return True
            
        except Exception as e:
            logger.error(f"Error adding movie to Telegram database: {e}")
            return False
    
    def update_access_count(self, message_id: int):
        """Update access count for a movie"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                UPDATE telegram_movies 
                SET access_count = access_count + 1, last_accessed = CURRENT_TIMESTAMP
                WHERE message_id = ?
            ''', (message_id,))
            
            self.conn.commit()
            
        except Exception as e:
            logger.error(f"Error updating access count: {e}")
    
    def log_search(self, user_id: int, chat_id: int, movie_title: str, found: bool, forwarded: bool, error_message: str = None):
        """Log search activity"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT INTO telegram_search_logs (user_id, chat_id, movie_title, found, forwarded, error_message)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, chat_id, movie_title, found, forwarded, error_message))
            
            self.conn.commit()
            
        except Exception as e:
            logger.error(f"Error logging search: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get agent statistics (Agent interface method)"""
        try:
            cursor = self.conn.cursor()
            
            # Total movies
            cursor.execute('SELECT COUNT(*) FROM telegram_movies')
            total_movies = cursor.fetchone()[0]
            
            # Recent searches (24 hours)
            cursor.execute('''
                SELECT COUNT(*) FROM telegram_search_logs 
                WHERE search_date >= datetime('now', '-24 hours')
            ''')
            recent_searches = cursor.fetchone()[0]
            
            # Successful forwards (24 hours)
            cursor.execute('''
                SELECT COUNT(*) FROM telegram_search_logs 
                WHERE forwarded = 1 AND search_date >= datetime('now', '-24 hours')
            ''')
            successful_forwards = cursor.fetchone()[0]
            
            # Most popular movies
            cursor.execute('''
                SELECT title, access_count FROM telegram_movies 
                ORDER BY access_count DESC 
                LIMIT 5
            ''')
            popular_movies = cursor.fetchall()
            
            return {
                'agent_name': self.name,
                'enabled': self.enabled,
                'total_movies': total_movies,
                'recent_searches_24h': recent_searches,
                'successful_forwards_24h': successful_forwards,
                'success_rate': (successful_forwards / recent_searches * 100) if recent_searches > 0 else 0,
                'popular_movies': [{'title': row[0], 'access_count': row[1]} for row in popular_movies],
                'bot_username': self.bot_username,
                'channel_configured': bool(self.channel_id)
            }
            
        except Exception as e:
            logger.error(f"Error getting Telegram stats: {e}")
            return {
                'agent_name': self.name,
                'enabled': False,
                'error': str(e)
            }
    
    def test_connection(self) -> Dict[str, Any]:
        """Test Telegram bot connection"""
        if not self.enabled or not self.bot_token:
            return {'success': False, 'error': 'Agent not configured or disabled'}
        
        try:
            # Test bot info
            url = f"{self.base_url}/getMe"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get('ok'):
                bot_info = result.get('result')
                
                # Test channel access if configured
                channel_access = False
                if self.channel_id:
                    channel_url = f"{self.base_url}/getChat"
                    channel_data = {"chat_id": self.channel_id}
                    channel_response = requests.post(channel_url, json=channel_data, timeout=10)
                    
                    if channel_response.status_code == 200:
                        channel_result = channel_response.json()
                        channel_access = channel_result.get('ok', False)
                
                return {
                    'success': True,
                    'bot_info': {
                        'name': bot_info.get('first_name'),
                        'username': bot_info.get('username'),
                        'id': bot_info.get('id')
                    },
                    'channel_access': channel_access,
                    'message': 'Telegram bot connection successful'
                }
            else:
                return {
                    'success': False,
                    'error': result.get('description', 'Unknown error')
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

# Create agent instance
telegram_agent = TelegramAgent()

def get_agent():
    """Get the Telegram agent instance (for agent manager)"""
    return telegram_agent