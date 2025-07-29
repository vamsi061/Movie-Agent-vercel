#!/usr/bin/env python3
"""
Simple Telegram Agent - Provides direct Telegram links without authentication
No OTP required - just direct links that open in user's Telegram app
"""

import re
import logging
from typing import Dict, List, Any, Optional

class TelegramMovieAgent:
    def __init__(self, config=None):
        """
        Initialize Simple Telegram Movie Agent (no authentication needed)
        """
        self.config = config or {}
        
        # Popular movie bots and channels (no @ symbol for URL creation)
        self.movie_bots = [
            'MoviesFlixBot',
            'HDMoviesBot', 
            'BollyFlixBot',
            'MovieRequestBot',
            'NewMoviesBot',
            'LatestMoviesBot',
            'MovieDownloadBot',
            'FilmSearchBot'
        ]
        
        self.movie_channels = [
            'MoviesAdda4u',
            'HDMoviesHub',
            'BollywoodMovies',
            'HollywoodMovies4u',
            'LatestMovies2024',
            'MovieDownloadHub',
            'CinemaWorld',
            'FilmCollection'
        ]
        
        self.logger = logging.getLogger(__name__)
        self.is_connected = True  # Always connected for direct links
        
    async def initialize(self):
        """Initialize agent (no authentication needed)"""
        self.is_connected = True
        self.logger.info("Telegram agent initialized for direct links")
        return True
    
    async def search_movies(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Create direct Telegram links for movie search (no authentication needed)
        
        Args:
            query: Movie name to search for
            limit: Maximum number of results to return
            
        Returns:
            List of movie dictionaries with direct Telegram links
        """
        movies = []
        
        try:
            # Create direct bot search links
            bot_movies = self._create_bot_search_links(query, limit // 2)
            movies.extend(bot_movies)
            
            # Create direct channel links  
            channel_movies = self._create_channel_links(query, limit // 2)
            movies.extend(channel_movies)
            
            # Limit results
            return movies[:limit]
            
        except Exception as e:
            self.logger.error(f"Error creating Telegram links: {str(e)}")
            return []
    
    def _create_bot_search_links(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """Create direct Telegram bot search links"""
        movies = []
        
        for i, bot_name in enumerate(self.movie_bots[:limit]):
            try:
                # Create direct bot link
                bot_link = f"https://t.me/{bot_name}"
                
                # Create search-specific link if bot supports it
                search_link = f"https://t.me/{bot_name}?start=search"
                
                # Determine likely quality and content based on bot name
                quality = self._guess_quality_from_bot_name(bot_name)
                language = self._guess_language_from_bot_name(bot_name)
                
                movie_data = {
                    'title': f"{query} - via {bot_name}",
                    'quality': quality,
                    'file_size': 'Multiple Sizes Available',
                    'year': '2024',
                    'language': language,
                    'source': 'Telegram Bot',
                    'bot_username': f"@{bot_name}",
                    'url': bot_link,
                    'download_links': [{
                        'url': bot_link,
                        'type': 'telegram_bot',
                        'source': 'Telegram',
                        'text': f'Open {bot_name} and search for "{query}"',
                        'host': 'Telegram',
                        'quality': quality,
                        'service_type': 'Telegram Bot'
                    }],
                    'description': f'Click to open {bot_name} in Telegram and search for "{query}"'
                }
                
                movies.append(movie_data)
                
            except Exception as e:
                self.logger.warning(f"Error creating bot link for {bot_name}: {str(e)}")
                continue
                
        return movies
    
    def _create_channel_links(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """Create direct Telegram channel links"""
        movies = []
        
        for i, channel_name in enumerate(self.movie_channels[:limit]):
            try:
                # Create direct channel link
                channel_link = f"https://t.me/{channel_name}"
                
                # Determine likely content based on channel name
                quality = self._guess_quality_from_channel_name(channel_name)
                language = self._guess_language_from_channel_name(channel_name)
                
                movie_data = {
                    'title': f"{query} - from {channel_name}",
                    'quality': quality,
                    'file_size': 'Various Sizes',
                    'year': '2024',
                    'language': language,
                    'source': 'Telegram Channel',
                    'channel_username': f"@{channel_name}",
                    'url': channel_link,
                    'message_url': channel_link,
                    'download_links': [{
                        'url': channel_link,
                        'type': 'telegram_channel',
                        'source': 'Telegram',
                        'text': f'Browse {channel_name} for "{query}"',
                        'host': 'Telegram',
                        'quality': quality,
                        'service_type': 'Telegram Channel'
                    }],
                    'description': f'Click to open {channel_name} in Telegram and browse for "{query}"'
                }
                
                movies.append(movie_data)
                
            except Exception as e:
                self.logger.warning(f"Error creating channel link for {channel_name}: {str(e)}")
                continue
                
        return movies
    
    def _guess_quality_from_bot_name(self, bot_name: str) -> str:
        """Guess likely quality based on bot name"""
        bot_lower = bot_name.lower()
        if 'hd' in bot_lower:
            return '1080p/720p'
        elif '4k' in bot_lower:
            return '4K/1080p'
        elif 'quality' in bot_lower:
            return 'Multiple Qualities'
        else:
            return '720p/480p'
    
    def _guess_language_from_bot_name(self, bot_name: str) -> str:
        """Guess likely language based on bot name"""
        bot_lower = bot_name.lower()
        if 'bolly' in bot_lower or 'hindi' in bot_lower:
            return 'Hindi'
        elif 'hollywood' in bot_lower:
            return 'English'
        else:
            return 'Multi-Language'
    
    def _guess_quality_from_channel_name(self, channel_name: str) -> str:
        """Guess likely quality based on channel name"""
        channel_lower = channel_name.lower()
        if 'hd' in channel_lower:
            return '1080p/720p'
        elif '4k' in channel_lower:
            return '4K/1080p'
        elif '2024' in channel_lower:
            return 'Latest Quality'
        else:
            return 'Multiple Qualities'
    
    def _guess_language_from_channel_name(self, channel_name: str) -> str:
        """Guess likely language based on channel name"""
        channel_lower = channel_name.lower()
        if 'bollywood' in channel_lower or 'hindi' in channel_lower:
            return 'Hindi'
        elif 'hollywood' in channel_lower:
            return 'English'
        else:
            return 'Multi-Language'
    
    async def disconnect(self):
        """Disconnect (not needed for direct links)"""
        self.is_connected = False
        self.logger.info("Telegram agent disconnected")

# For backward compatibility
if __name__ == "__main__":
    print("Simple Telegram Movie Agent - No Authentication Required!")
    print("Provides direct Telegram links that open in user's Telegram app")
    print("No OTP or verification codes needed!")