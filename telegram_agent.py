#!/usr/bin/env python3
"""
Telegram Agent - Movie search and link extraction from Telegram bots and channels
Integrates with popular movie bots and channels for direct download links
"""

import asyncio
import re
import json
import time
import logging
from typing import Dict, List, Any, Optional
from telethon import TelegramClient, events
from telethon.tl.types import Channel, Chat, User
from telethon.errors import SessionPasswordNeededError, FloodWaitError
import requests
from datetime import datetime, timedelta

class TelegramMovieAgent:
    def __init__(self, config=None):
        """
        Initialize Telegram Movie Agent
        
        Args:
            config: Dictionary containing Telegram API credentials
                   {'api_id': int, 'api_hash': str, 'phone': str}
        """
        self.config = config or {}
        self.api_id = self.config.get('api_id')
        self.api_hash = self.config.get('api_hash') 
        self.phone = self.config.get('phone')
        
        # Session file for persistent login
        self.session_name = 'movie_agent_session'
        self.client = None
        self.is_connected = False
        
        # Popular movie bots and channels
        self.movie_bots = [
            '@MoviesFlixBot',
            '@HDMoviesBot', 
            '@BollyFlixBot',
            '@MovieRequestBot',
            '@NewMoviesBot',
            '@LatestMoviesBot'
        ]
        
        self.movie_channels = [
            '@MoviesAdda4u',
            '@HDMoviesHub',
            '@BollywoodMovies',
            '@HollywoodMovies4u',
            '@LatestMovies2024',
            '@MovieDownloadHub'
        ]
        
        # Quality patterns for filtering
        self.quality_patterns = [
            r'4K|2160p',
            r'1080p|FHD',
            r'720p|HD',
            r'480p|SD',
            r'CAM|HDCAM',
            r'DVDRip|BRRip|BluRay|WEBRip'
        ]
        
        # File size patterns
        self.size_patterns = [
            r'(\d+(?:\.\d+)?)\s*(GB|MB|KB)',
            r'Size[:\s]*(\d+(?:\.\d+)?)\s*(GB|MB|KB)',
            r'(\d+(?:\.\d+)?)\s*GB',
            r'(\d+(?:\.\d+)?)\s*MB'
        ]
        
        self.logger = logging.getLogger(__name__)
        
    async def initialize(self):
        """Initialize Telegram client and connect"""
        try:
            if not self.api_id or not self.api_hash:
                self.logger.error("Telegram API credentials not provided")
                return False
                
            self.client = TelegramClient(self.session_name, self.api_id, self.api_hash)
            await self.client.start(phone=self.phone)
            self.is_connected = True
            self.logger.info("Telegram client connected successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Telegram client: {str(e)}")
            return False
    
    async def search_movies(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search for movies across Telegram bots and channels
        
        Args:
            query: Movie name to search for
            limit: Maximum number of results to return
            
        Returns:
            List of movie dictionaries with download information
        """
        if not self.is_connected:
            await self.initialize()
            
        if not self.is_connected:
            return []
            
        movies = []
        
        try:
            # Search in movie bots
            bot_movies = await self._search_movie_bots(query, limit // 2)
            movies.extend(bot_movies)
            
            # Search in movie channels  
            channel_movies = await self._search_movie_channels(query, limit // 2)
            movies.extend(channel_movies)
            
            # Remove duplicates and limit results
            unique_movies = self._remove_duplicates(movies)
            return unique_movies[:limit]
            
        except Exception as e:
            self.logger.error(f"Error searching Telegram movies: {str(e)}")
            return []
    
    async def _search_movie_bots(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """Search for movies using Telegram bots"""
        movies = []
        
        for bot_username in self.movie_bots:
            try:
                # Get bot entity
                bot = await self.client.get_entity(bot_username)
                
                # Send movie search request
                await self.client.send_message(bot, f"/search {query}")
                
                # Wait for response
                await asyncio.sleep(2)
                
                # Get recent messages from bot
                messages = await self.client.get_messages(bot, limit=20)
                
                for message in messages:
                    if message.text and query.lower() in message.text.lower():
                        movie_data = self._parse_bot_message(message.text, bot_username)
                        if movie_data:
                            movies.append(movie_data)
                            
                if len(movies) >= limit:
                    break
                    
            except Exception as e:
                self.logger.warning(f"Error searching bot {bot_username}: {str(e)}")
                continue
                
        return movies
    
    async def _search_movie_channels(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """Search for movies in Telegram channels"""
        movies = []
        
        for channel_username in self.movie_channels:
            try:
                # Get channel entity
                channel = await self.client.get_entity(channel_username)
                
                # Search recent messages in channel
                messages = await self.client.get_messages(channel, limit=100)
                
                for message in messages:
                    if message.text and query.lower() in message.text.lower():
                        movie_data = self._parse_channel_message(message.text, channel_username, message.id)
                        if movie_data:
                            movies.append(movie_data)
                            
                if len(movies) >= limit:
                    break
                    
            except Exception as e:
                self.logger.warning(f"Error searching channel {channel_username}: {str(e)}")
                continue
                
        return movies
    
    def _parse_bot_message(self, text: str, bot_username: str) -> Optional[Dict[str, Any]]:
        """Parse movie information from bot message"""
        try:
            # Extract movie title
            title_patterns = [
                r'🎬\s*([^\n]+)',
                r'Movie[:\s]*([^\n]+)',
                r'Title[:\s]*([^\n]+)',
                r'Name[:\s]*([^\n]+)'
            ]
            
            title = "Unknown"
            for pattern in title_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    title = match.group(1).strip()
                    break
            
            # Extract quality
            quality = self._extract_quality(text)
            
            # Extract file size
            file_size = self._extract_file_size(text)
            
            # Extract year
            year = self._extract_year(text)
            
            # Extract language
            language = self._extract_language(text)
            
            # Look for download links
            download_links = self._extract_download_links(text)
            
            return {
                'title': title,
                'quality': quality,
                'file_size': file_size,
                'year': year,
                'language': language,
                'source': 'Telegram Bot',
                'bot_username': bot_username,
                'download_links': download_links,
                'raw_text': text[:200] + '...' if len(text) > 200 else text
            }
            
        except Exception as e:
            self.logger.error(f"Error parsing bot message: {str(e)}")
            return None
    
    def _parse_channel_message(self, text: str, channel_username: str, message_id: int) -> Optional[Dict[str, Any]]:
        """Parse movie information from channel message"""
        try:
            # Extract movie title (usually in first line or after emoji)
            lines = text.split('\n')
            title = "Unknown"
            
            for line in lines[:3]:  # Check first 3 lines
                # Remove common prefixes and emojis
                clean_line = re.sub(r'^[🎬🎭🎪🎨🎯🎲🎰🎳🎮🎯]+\s*', '', line.strip())
                clean_line = re.sub(r'^(Movie|Film|Title)[:\s]*', '', clean_line, flags=re.IGNORECASE)
                
                if clean_line and len(clean_line) > 3:
                    title = clean_line
                    break
            
            # Extract other information
            quality = self._extract_quality(text)
            file_size = self._extract_file_size(text)
            year = self._extract_year(text)
            language = self._extract_language(text)
            download_links = self._extract_download_links(text)
            
            # Create Telegram message URL
            message_url = f"https://t.me/{channel_username.replace('@', '')}/{message_id}"
            
            return {
                'title': title,
                'quality': quality,
                'file_size': file_size,
                'year': year,
                'language': language,
                'source': 'Telegram Channel',
                'channel_username': channel_username,
                'message_url': message_url,
                'download_links': download_links,
                'raw_text': text[:200] + '...' if len(text) > 200 else text
            }
            
        except Exception as e:
            self.logger.error(f"Error parsing channel message: {str(e)}")
            return None
    
    def _extract_quality(self, text: str) -> str:
        """Extract video quality from text"""
        for pattern in self.quality_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group().upper()
        return "Unknown"
    
    def _extract_file_size(self, text: str) -> str:
        """Extract file size from text"""
        for pattern in self.size_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                if len(match.groups()) >= 2:
                    return f"{match.group(1)}{match.group(2).upper()}"
                else:
                    return match.group().upper()
        return "Unknown"
    
    def _extract_year(self, text: str) -> str:
        """Extract release year from text"""
        year_pattern = r'(19|20)\d{2}'
        match = re.search(year_pattern, text)
        return match.group() if match else "Unknown"
    
    def _extract_language(self, text: str) -> str:
        """Extract language from text"""
        language_patterns = {
            'Hindi': r'\b(Hindi|हिंदी|Bollywood)\b',
            'English': r'\b(English|Hollywood|Eng)\b',
            'Tamil': r'\b(Tamil|தமிழ்|Kollywood)\b',
            'Telugu': r'\b(Telugu|తెలుగు|Tollywood)\b',
            'Malayalam': r'\b(Malayalam|മലയാളം)\b',
            'Kannada': r'\b(Kannada|ಕನ್ನಡ)\b',
            'Bengali': r'\b(Bengali|বাংলা)\b',
            'Punjabi': r'\b(Punjabi|ਪੰਜਾਬੀ)\b'
        }
        
        for language, pattern in language_patterns.items():
            if re.search(pattern, text, re.IGNORECASE):
                return language
        return "Unknown"
    
    def _extract_download_links(self, text: str) -> List[Dict[str, Any]]:
        """Extract download links from text"""
        links = []
        
        # Common download link patterns
        link_patterns = [
            r'https?://[^\s]+',
            r't\.me/[^\s]+',
            r'@[a-zA-Z0-9_]+',  # Bot usernames
        ]
        
        for pattern in link_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                # Skip certain domains
                if any(skip in match.lower() for skip in ['telegram.org', 'telegram.me']):
                    continue
                    
                links.append({
                    'url': match,
                    'type': 'direct' if match.startswith('http') else 'telegram',
                    'source': 'Telegram'
                })
        
        return links
    
    def _remove_duplicates(self, movies: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate movies based on title similarity"""
        unique_movies = []
        seen_titles = set()
        
        for movie in movies:
            title_lower = movie['title'].lower()
            # Simple duplicate detection
            if title_lower not in seen_titles:
                seen_titles.add(title_lower)
                unique_movies.append(movie)
        
        return unique_movies
    
    async def get_movie_details(self, movie_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get detailed information about a specific movie"""
        try:
            if movie_data.get('message_url'):
                # For channel messages, we can get more details
                return await self._get_channel_movie_details(movie_data)
            elif movie_data.get('bot_username'):
                # For bot results, request more details
                return await self._get_bot_movie_details(movie_data)
            else:
                return movie_data
                
        except Exception as e:
            self.logger.error(f"Error getting movie details: {str(e)}")
            return movie_data
    
    async def _get_channel_movie_details(self, movie_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get detailed information from channel message"""
        # Implementation for getting more details from channel
        return movie_data
    
    async def _get_bot_movie_details(self, movie_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get detailed information from bot"""
        # Implementation for getting more details from bot
        return movie_data
    
    async def disconnect(self):
        """Disconnect from Telegram"""
        if self.client and self.is_connected:
            await self.client.disconnect()
            self.is_connected = False
            self.logger.info("Telegram client disconnected")

# Configuration helper
def create_telegram_config():
    """
    Helper function to create Telegram configuration
    Users need to get these from https://my.telegram.org/apps
    """
    return {
        'api_id': 'YOUR_API_ID',  # Get from https://my.telegram.org/apps
        'api_hash': 'YOUR_API_HASH',  # Get from https://my.telegram.org/apps  
        'phone': 'YOUR_PHONE_NUMBER'  # Your phone number with country code
    }

if __name__ == "__main__":
    # Example usage
    async def test_telegram_agent():
        config = create_telegram_config()
        agent = TelegramMovieAgent(config)
        
        try:
            await agent.initialize()
            movies = await agent.search_movies("Avengers", limit=5)
            
            print(f"Found {len(movies)} movies:")
            for movie in movies:
                print(f"- {movie['title']} ({movie['quality']}) - {movie['source']}")
                
        finally:
            await agent.disconnect()
    
    # Run the test
    # asyncio.run(test_telegram_agent())
    print("Telegram Movie Agent created successfully!")
    print("To use this agent, you need to:")
    print("1. Get API credentials from https://my.telegram.org/apps")
    print("2. Update the config with your api_id, api_hash, and phone number")
    print("3. Install required dependencies: pip install telethon")