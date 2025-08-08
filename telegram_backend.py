#!/usr/bin/env python3
"""
Telegram Backend - Movie file forwarding system
Handles movie search and forwarding from private channel to users
"""

import os
import json
import logging
import asyncio
from typing import Dict, List, Optional, Any
from flask import Flask, request, jsonify, Blueprint
import requests
from datetime import datetime
import sqlite3
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TelegramMovieBot:
    def __init__(self):
        """Initialize Telegram Movie Bot"""
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.channel_id = os.getenv('TELEGRAM_CHANNEL_ID')  # Private channel ID
        self.bot_username = os.getenv('TELEGRAM_BOT_USERNAME', 'MoviesAgent123bot')
        
        if not self.bot_token:
            logger.error("TELEGRAM_BOT_TOKEN not found in environment variables")
            
        if not self.channel_id:
            logger.error("TELEGRAM_CHANNEL_ID not found in environment variables")
            
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        
        # Initialize database
        self.init_database()
        
    def init_database(self):
        """Initialize SQLite database for movie mappings"""
        try:
            db_path = Path("telegram_movies.db")
            self.conn = sqlite3.connect(db_path, check_same_thread=False)
            
            # Create movies table
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS movies (
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
                    added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(message_id)
                )
            ''')
            
            # Create search logs table
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS search_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    chat_id INTEGER,
                    movie_title TEXT,
                    found BOOLEAN,
                    forwarded BOOLEAN,
                    search_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            self.conn.commit()
            logger.info("Database initialized successfully")
            
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
    
    def normalize_title(self, title: str) -> str:
        """Normalize movie title for better matching"""
        import re
        
        # Convert to lowercase
        title = title.lower().strip()
        
        # Remove special characters and extra spaces
        title = re.sub(r'[^\w\s]', ' ', title)
        title = re.sub(r'\s+', ' ', title)
        
        # Remove common words that might interfere with search
        common_words = ['movie', 'film', 'full', 'hd', 'bluray', 'dvdrip', 'webrip']
        words = title.split()
        words = [word for word in words if word not in common_words]
        
        return ' '.join(words).strip()
    
    def add_movie_to_database(self, title: str, message_id: int, file_info: Dict = None):
        """Add movie to database"""
        try:
            normalized_title = self.normalize_title(title)
            
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO movies 
                (title, normalized_title, message_id, file_id, file_type, file_size, year, quality, language)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                title,
                normalized_title,
                message_id,
                file_info.get('file_id') if file_info else None,
                file_info.get('file_type') if file_info else None,
                file_info.get('file_size') if file_info else None,
                file_info.get('year') if file_info else None,
                file_info.get('quality') if file_info else None,
                file_info.get('language') if file_info else None
            ))
            
            self.conn.commit()
            logger.info(f"Added movie to database: {title} (Message ID: {message_id})")
            return True
            
        except Exception as e:
            logger.error(f"Error adding movie to database: {e}")
            return False
    
    def search_movie_in_database(self, query: str) -> List[Dict]:
        """Search for movie in database"""
        try:
            normalized_query = self.normalize_title(query)
            
            cursor = self.conn.cursor()
            
            # Try exact match first
            cursor.execute('''
                SELECT * FROM movies 
                WHERE normalized_title = ? 
                ORDER BY added_date DESC
            ''', (normalized_query,))
            
            results = cursor.fetchall()
            
            # If no exact match, try partial match
            if not results:
                cursor.execute('''
                    SELECT * FROM movies 
                    WHERE normalized_title LIKE ? OR title LIKE ?
                    ORDER BY added_date DESC
                    LIMIT 10
                ''', (f'%{normalized_query}%', f'%{query}%'))
                
                results = cursor.fetchall()
            
            # Convert to list of dictionaries
            columns = [desc[0] for desc in cursor.description]
            movies = []
            
            for row in results:
                movie = dict(zip(columns, row))
                movies.append(movie)
            
            return movies
            
        except Exception as e:
            logger.error(f"Error searching movie in database: {e}")
            return []
    
    def log_search(self, user_id: int, chat_id: int, movie_title: str, found: bool, forwarded: bool):
        """Log search activity"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT INTO search_logs (user_id, chat_id, movie_title, found, forwarded)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, chat_id, movie_title, found, forwarded))
            
            self.conn.commit()
            
        except Exception as e:
            logger.error(f"Error logging search: {e}")
    
    def make_telegram_request(self, method: str, data: Dict) -> Dict:
        """Make request to Telegram Bot API"""
        try:
            url = f"{self.base_url}/{method}"
            response = requests.post(url, json=data, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            
            if not result.get('ok'):
                logger.error(f"Telegram API error: {result.get('description')}")
                return {'success': False, 'error': result.get('description')}
            
            return {'success': True, 'data': result.get('result')}
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error: {e}")
            return {'success': False, 'error': str(e)}
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return {'success': False, 'error': str(e)}
    
    def forward_message(self, chat_id: int, message_id: int) -> Dict:
        """Forward message from private channel to user"""
        try:
            data = {
                'chat_id': chat_id,
                'from_chat_id': self.channel_id,
                'message_id': message_id
            }
            
            result = self.make_telegram_request('forwardMessage', data)
            
            if result['success']:
                logger.info(f"Successfully forwarded message {message_id} to chat {chat_id}")
            else:
                logger.error(f"Failed to forward message: {result.get('error')}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error forwarding message: {e}")
            return {'success': False, 'error': str(e)}
    
    def send_message(self, chat_id: int, text: str, parse_mode: str = 'HTML') -> Dict:
        """Send text message to user"""
        try:
            data = {
                'chat_id': chat_id,
                'text': text,
                'parse_mode': parse_mode
            }
            
            return self.make_telegram_request('sendMessage', data)
            
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return {'success': False, 'error': str(e)}
    
    def search_and_forward_movie(self, movie_title: str, user_chat_id: int, user_id: int = None) -> Dict:
        """Search for movie and forward to user"""
        try:
            # Search for movie in database
            movies = self.search_movie_in_database(movie_title)
            
            if not movies:
                # Log unsuccessful search
                self.log_search(user_id or user_chat_id, user_chat_id, movie_title, False, False)
                
                return {
                    'success': False,
                    'error': 'Movie not found',
                    'message': f"Sorry, I couldn't find '{movie_title}' in our collection."
                }
            
            # Get the best match (first result)
            best_match = movies[0]
            message_id = best_match['message_id']
            
            # Forward the movie file
            forward_result = self.forward_message(user_chat_id, message_id)
            
            # Log search activity
            self.log_search(
                user_id or user_chat_id, 
                user_chat_id, 
                movie_title, 
                True, 
                forward_result['success']
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
            logger.error(f"Error in search_and_forward_movie: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': "An error occurred while searching for the movie."
            }
    
    def handle_start_command(self, chat_id: int, user_id: int, command_args: str = None) -> Dict:
        """Handle /start command with optional movie title"""
        try:
            if command_args:
                # Deep link with movie title
                movie_title = command_args.replace('_', ' ')
                
                # Send initial message
                self.send_message(
                    chat_id, 
                    f"🔍 Searching for '<b>{movie_title}</b>'...\nPlease wait while I look for this movie in our collection."
                )
                
                # Search and forward movie
                result = self.search_and_forward_movie(movie_title, chat_id, user_id)
                
                if result['success']:
                    self.send_message(
                        chat_id,
                        f"✅ {result['message']}\n\n🎬 Enjoy watching!"
                    )
                else:
                    self.send_message(
                        chat_id,
                        f"❌ {result['message']}\n\n💡 Try searching with a different title or check the spelling."
                    )
                
                return result
            else:
                # Regular start command
                welcome_message = """
🎬 <b>Welcome to Movies Agent Bot!</b>

I can help you find and download movies from our collection.

<b>How to use:</b>
• Send me a movie title to search
• Use deep links: https://t.me/MoviesAgent123bot?start=MovieTitle
• I'll forward the movie file directly to you

<b>Example:</b>
Just type: <code>Avengers Endgame</code>

🚀 Start by sending me a movie title!
                """
                
                return self.send_message(chat_id, welcome_message)
                
        except Exception as e:
            logger.error(f"Error handling start command: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_movie_stats(self) -> Dict:
        """Get statistics about movies in database"""
        try:
            cursor = self.conn.cursor()
            
            # Total movies
            cursor.execute('SELECT COUNT(*) FROM movies')
            total_movies = cursor.fetchone()[0]
            
            # Recent searches
            cursor.execute('''
                SELECT COUNT(*) FROM search_logs 
                WHERE search_date >= datetime('now', '-24 hours')
            ''')
            recent_searches = cursor.fetchone()[0]
            
            # Successful forwards
            cursor.execute('''
                SELECT COUNT(*) FROM search_logs 
                WHERE forwarded = 1 AND search_date >= datetime('now', '-24 hours')
            ''')
            successful_forwards = cursor.fetchone()[0]
            
            return {
                'total_movies': total_movies,
                'recent_searches_24h': recent_searches,
                'successful_forwards_24h': successful_forwards,
                'success_rate': (successful_forwards / recent_searches * 100) if recent_searches > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {}

# Initialize bot instance
telegram_bot = TelegramMovieBot()

# Create Flask Blueprint for Telegram routes
telegram_bp = Blueprint('telegram', __name__, url_prefix='/telegram')

@telegram_bp.route('/search-movie', methods=['POST'])
def search_movie_api():
    """API endpoint to search and forward movie"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400
        
        movie_title = data.get('movie_title', '').strip()
        chat_id = data.get('chat_id')
        user_id = data.get('user_id')
        
        if not movie_title:
            return jsonify({
                'success': False,
                'error': 'Movie title is required'
            }), 400
        
        if not chat_id:
            return jsonify({
                'success': False,
                'error': 'Chat ID is required'
            }), 400
        
        # Search and forward movie
        result = telegram_bot.search_and_forward_movie(movie_title, chat_id, user_id)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error in search_movie_api: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@telegram_bp.route('/webhook', methods=['POST'])
def telegram_webhook():
    """Handle Telegram webhook updates"""
    try:
        update = request.get_json()
        
        if not update:
            return jsonify({'success': False}), 400
        
        # Handle message
        if 'message' in update:
            message = update['message']
            chat_id = message['chat']['id']
            user_id = message['from']['id']
            
            if 'text' in message:
                text = message['text']
                
                if text.startswith('/start'):
                    # Handle start command
                    command_parts = text.split(' ', 1)
                    command_args = command_parts[1] if len(command_parts) > 1 else None
                    
                    telegram_bot.handle_start_command(chat_id, user_id, command_args)
                    
                else:
                    # Treat as movie search
                    telegram_bot.send_message(
                        chat_id,
                        f"🔍 Searching for '<b>{text}</b>'...\nPlease wait while I look for this movie."
                    )
                    
                    result = telegram_bot.search_and_forward_movie(text, chat_id, user_id)
                    
                    if result['success']:
                        telegram_bot.send_message(
                            chat_id,
                            f"✅ {result['message']}\n\n🎬 Enjoy watching!"
                        )
                    else:
                        telegram_bot.send_message(
                            chat_id,
                            f"❌ {result['message']}\n\n💡 Try a different title or check spelling."
                        )
        
        return jsonify({'success': True})
        
    except Exception as e:
        logger.error(f"Error in telegram_webhook: {e}")
        return jsonify({'success': False}), 500

@telegram_bp.route('/add-movie', methods=['POST'])
def add_movie_api():
    """API endpoint to add movie to database"""
    try:
        data = request.get_json()
        
        title = data.get('title')
        message_id = data.get('message_id')
        file_info = data.get('file_info', {})
        
        if not title or not message_id:
            return jsonify({
                'success': False,
                'error': 'Title and message_id are required'
            }), 400
        
        success = telegram_bot.add_movie_to_database(title, message_id, file_info)
        
        return jsonify({
            'success': success,
            'message': 'Movie added successfully' if success else 'Failed to add movie'
        })
        
    except Exception as e:
        logger.error(f"Error in add_movie_api: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@telegram_bp.route('/stats', methods=['GET'])
def get_stats_api():
    """Get bot statistics"""
    try:
        stats = telegram_bot.get_movie_stats()
        return jsonify({
            'success': True,
            'stats': stats
        })
        
    except Exception as e:
        logger.error(f"Error in get_stats_api: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@telegram_bp.route('/movies', methods=['GET'])
def list_movies_api():
    """List all movies in database"""
    try:
        cursor = telegram_bot.conn.cursor()
        cursor.execute('''
            SELECT title, year, quality, language, added_date 
            FROM movies 
            ORDER BY added_date DESC 
            LIMIT 100
        ''')
        
        movies = []
        for row in cursor.fetchall():
            movies.append({
                'title': row[0],
                'year': row[1],
                'quality': row[2],
                'language': row[3],
                'added_date': row[4]
            })
        
        return jsonify({
            'success': True,
            'movies': movies,
            'total': len(movies)
        })
        
    except Exception as e:
        logger.error(f"Error in list_movies_api: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def register_telegram_routes(app):
    """Register Telegram routes with Flask app"""
    app.register_blueprint(telegram_bp)
    logger.info("Telegram routes registered successfully")

if __name__ == "__main__":
    # Test the bot functionality
    print("🤖 Telegram Movie Bot initialized")
    print(f"Bot Token: {'✅ Set' if telegram_bot.bot_token else '❌ Missing'}")
    print(f"Channel ID: {'✅ Set' if telegram_bot.channel_id else '❌ Missing'}")
    
    # Test database
    stats = telegram_bot.get_movie_stats()
    print(f"Database: ✅ Connected ({stats.get('total_movies', 0)} movies)")