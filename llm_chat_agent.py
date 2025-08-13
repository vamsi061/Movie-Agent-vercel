#!/usr/bin/env python3
"""
Enhanced LLM Chat Agent - Intelligent assistant with automatic movie search
Handles personal questions and movie requests with integrated multi-source search
"""

import os
import json
import re
import logging
import difflib
from typing import Dict, List, Optional, Any
from together import Together
import requests
from session_manager import session_manager
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EnhancedLLMChatAgent:
    def __init__(self, api_key: str = None):
        """Initialize Enhanced LLM Chat Agent with Together API and movie search agents"""
        # Import config manager
        try:
            from config_manager import config_manager
            self.config_manager = config_manager
            
            # Get API key from config manager or parameter
            if api_key:
                self.api_key = api_key
            else:
                self.api_key = self.config_manager.get_together_api_key()
            
            self.has_api_key = bool(self.api_key)
            
            # Get Together API configuration
            self.together_config = self.config_manager.get_together_config()
            
        except ImportError:
            # Fallback if config manager is not available
            self.api_key = api_key or os.getenv('TOGETHER_API_KEY')
            self.has_api_key = bool(self.api_key)
            self.config_manager = None
            self.together_config = {}
        
        if self.has_api_key:
            self.client = Together(api_key=self.api_key)
            self.model = "mistralai/Mixtral-8x7B-Instruct-v0.1"
        else:
            self.client = None
            logger.warning("No Together API key provided. Using basic functionality only.")
        
        # Initialize movie search agents
        self.movie_agents = {}
        self._init_movie_agents()
        
        # Movie genres and categories
        self.movie_genres = [
            "action", "adventure", "comedy", "drama", "horror", "thriller", 
            "sci-fi", "fantasy", "romance", "animation", "documentary", 
            "crime", "mystery", "war", "western", "musical", "biography"
        ]
        
        self.conversation_history = []
        
        # Personal context for better responses
        self.agent_personality = {
            "name": "AI Movie Assistant",
            "role": "intelligent movie search and recommendation assistant",
            "traits": ["friendly", "knowledgeable", "efficient", "enthusiastic about movies"]
        }
        
    def analyze_user_intent(self, user_message: str, conversation_context: str = "") -> Dict[str, Any]:
        """Analyze user intent to determine response type"""
        # If no API key, use fallback analysis
        if not self.has_api_key:
            return self._fallback_intent_analysis(user_message)
        
        try:
            system_prompt = """You are an intelligent assistant that analyzes user messages to understand their intent.

CRITICAL: When users ask for movie recommendations (like "good action movies", "best comedies", "latest movies"), you MUST populate the movie_titles array with specific movie names.

ANALYZE THE USER'S MESSAGE CAREFULLY and determine:
1. Intent type: "personal", "movie_request", "general_chat", "greeting", "information_request", or "date_time"
2. If they mention a specific movie, research and provide complete details
3. If they ask for movie recommendations, provide 3-5 specific movie titles in the movie_titles array

INTENT CATEGORIES:
- "date_time": Questions about current date, time, day, etc.
- "information_request": General knowledge questions, facts, explanations
- "personal": Questions about the assistant (how are you, who are you, etc.)
- "movie_request": Anything related to finding, downloading, or discussing movies
- "greeting": Simple greetings and hellos
- "general_chat": Other conversational messages

FOR MOVIE RECOMMENDATIONS (like "good action movies", "best comedies", "latest movies"):
- Set intent_type to "movie_request"
- ALWAYS populate movie_titles with 3-5 specific movie names
- These titles will become clickable buttons for the user
- Example: "good action movies" → movie_titles: ["The Dark Knight", "Mad Max: Fury Road", "Inception", "John Wick", "Mission: Impossible"]

FOR SPECIFIC MOVIE REQUESTS (like "rrr movie", "avatar", "john wick"):
- Research the movie thoroughly
- Provide the correct full title, year, and key details
- Handle common abbreviations and alternate names

Respond in JSON format:
{
    "intent_type": "movie_request",
    "confidence": 0.9,
    "movie_details": {
        "movie_titles": ["The Dark Knight", "Mad Max: Fury Road", "Inception", "John Wick", "Mission: Impossible"],
        "genres": ["action"],
        "years": [],
        "actors": [],
        "directors": [],
        "language": "",
        "movie_research": {
            "full_title": "",
            "release_year": "",
            "alternate_names": [],
            "key_details": ""
        },
        "search_query": "action movies",
        "search_variations": ["action films", "action movies", "thriller movies"]
    },
    "user_intent_analysis": {
        "what_they_want": "action movie recommendations",
        "is_specific_movie": false,
        "confidence_in_movie_match": "medium"
    }
}

EXAMPLES:
- "good action movies" → movie_titles: ["The Dark Knight", "Mad Max: Fury Road", "Inception", "John Wick", "Mission: Impossible"]
- "best comedies" → movie_titles: ["The Hangover", "Superbad", "Anchorman", "Dumb and Dumber", "Borat"]
- "latest Marvel movies" → movie_titles: ["Avengers: Endgame", "Spider-Man: No Way Home", "Black Widow", "Shang-Chi", "Eternals"]
- "horror movies" → movie_titles: ["The Conjuring", "Hereditary", "Get Out", "A Quiet Place", "It"]

REMEMBER: Always populate movie_titles array for any movie recommendation request!"""

            # Attach recent session context to help handle follow-ups like "yes"/"no"
            if conversation_context:
                system_prompt += f"\n\nConversation context (for reference):\n{conversation_context[:1500]}"

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ]
            
            # Validate parameters before API call
            if not self.model or not isinstance(self.model, str):
                logger.error(f"Invalid model for intent analysis: {self.model}")
                return self._fallback_intent_analysis(user_message)
            
            if not messages or len(messages) == 0:
                logger.error("No messages for intent analysis")
                return self._fallback_intent_analysis(user_message)
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.3
            )
            
            response_text = response.choices[0].message.content
            logger.debug(f"LLM response: {response_text}")
            
            # Try to parse JSON response with multiple strategies
            try:
                # Strategy 1: Try to parse the entire response as JSON
                intent = json.loads(response_text.strip())
                logger.info(f"Analyzed intent (full parse): {intent}")
                return intent
            except json.JSONDecodeError:
                pass
            
            try:
                # Strategy 2: Extract JSON from response using regex
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    intent = json.loads(json_match.group())
                    logger.info(f"Analyzed intent (regex parse): {intent}")
                    return intent
            except json.JSONDecodeError:
                pass
            
            try:
                # Strategy 3: Look for JSON between code blocks
                code_block_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
                if code_block_match:
                    intent = json.loads(code_block_match.group(1))
                    logger.info(f"Analyzed intent (code block parse): {intent}")
                    return intent
            except json.JSONDecodeError:
                pass
            
            # If all parsing strategies fail, log the response and use fallback
            logger.warning(f"Could not parse LLM response as JSON. Response was: {response_text[:500]}...")
            return self._fallback_intent_analysis(user_message)
                
        except Exception as e:
            logger.error(f"Error analyzing user intent: {str(e)}")
            return self._fallback_intent_analysis(user_message)
    
    def _fallback_intent_analysis(self, user_message: str) -> Dict[str, Any]:
        """Enhanced fallback method for intent analysis when LLM fails"""
        message_lower = user_message.lower()
        
        # Check for date/time questions
        date_time_keywords = ['date', 'time', 'today', 'now', 'current', 'what day', 'what time', 'clock', 'calendar']
        if any(keyword in message_lower for keyword in date_time_keywords):
            return {
                "intent_type": "date_time",
                "confidence": 0.9,
                "response_style": "informative",
                "information_context": {"topic": "date_time", "requires_current_info": True}
            }
        
        # Check for general information requests
        info_keywords = ['what is', 'what are', 'how does', 'explain', 'define', 'meaning', 'why', 'where', 'when']
        question_indicators = ['?', 'what', 'how', 'why', 'where', 'when', 'who']
        if (any(keyword in message_lower for keyword in info_keywords) or 
            any(indicator in message_lower for indicator in question_indicators)):
            # But exclude movie and personal questions
            if not any(word in message_lower for word in ['movie', 'film', 'how are you', 'who are you']):
                return {
                    "intent_type": "information_request",
                    "confidence": 0.8,
                    "response_style": "informative",
                    "information_context": {"topic": "general_knowledge", "requires_explanation": True}
                }
        
        # Check for greetings
        greetings = ['hello', 'hi', 'hey', 'good morning', 'good evening', 'good afternoon']
        if any(greeting in message_lower for greeting in greetings):
            return {
                "intent_type": "greeting",
                "confidence": 0.8,
                "response_style": "conversational",
                "personal_context": {"topic": "greeting", "conversation_starter": True}
            }
        
        # Check for personal questions
        personal_keywords = ['how are you', 'what are you', 'who are you', 'tell me about yourself', 'feeling', 'mood']
        if any(keyword in message_lower for keyword in personal_keywords):
            return {
                "intent_type": "personal",
                "confidence": 0.7,
                "personal_context": {"topic": "personal_question", "requires_empathy": True},
                "response_style": "empathetic"
            }
        
        # ENHANCED SPECIFIC MOVIE DETECTION
        specific_movies = self._detect_specific_movie(user_message)
        if specific_movies:
            return specific_movies
        
        # Enhanced movie keyword detection for general requests
        movie_keywords = ['movie', 'film', 'watch', 'download', 'stream', 'cinema', 'bollywood', 'hollywood', 'show', 'series']
        mood_keywords = ['exciting', 'funny', 'romantic', 'scary', 'thrilling', 'action-packed', 'laugh', 'cry']
        theme_keywords = ['superhero', 'space', 'war', 'family', 'crime', 'zombie', 'vampire', 'magic', 'marvel', 'dc', 'disney']
        franchise_keywords = ['marvel', 'dc', 'disney', 'pixar', 'star wars', 'harry potter', 'fast and furious', 'john wick']
        
        if any(keyword in message_lower for keyword in movie_keywords + mood_keywords + theme_keywords + franchise_keywords):
            # Extract detailed movie preferences
            genres = [genre for genre in self.movie_genres if genre in message_lower]
            years = re.findall(r'\b(19|20)\d{2}\b', user_message)
            themes = [theme for theme in theme_keywords if theme in message_lower]
            franchises = [franchise for franchise in franchise_keywords if franchise in message_lower]
            
            # Detect mood from keywords
            mood = "any"
            if any(word in message_lower for word in ['exciting', 'action-packed', 'thrilling']):
                mood = "exciting"
                if 'action' not in genres:
                    genres.append('action')
            elif any(word in message_lower for word in ['funny', 'laugh', 'comedy']):
                mood = "funny"
                if 'comedy' not in genres:
                    genres.append('comedy')
            elif any(word in message_lower for word in ['romantic', 'romance', 'love']):
                mood = "romantic"
                if 'romance' not in genres:
                    genres.append('romance')
            elif any(word in message_lower for word in ['scary', 'horror', 'fear']):
                mood = "scary"
                if 'horror' not in genres:
                    genres.append('horror')
            
            # Detect language preferences
            language = "any"
            if any(word in message_lower for word in ['hindi', 'bollywood']):
                language = "hindi"
            elif any(word in message_lower for word in ['english', 'hollywood']):
                language = "english"
            elif any(word in message_lower for word in ['tamil', 'telugu', 'malayalam']):
                language = next(word for word in ['tamil', 'telugu', 'malayalam'] if word in message_lower)
            
            # Build intelligent search query
            search_parts = []
            
            # Prioritize franchises for specific searches
            if franchises:
                # For Marvel, DC, etc., use the franchise name as primary search term
                search_parts.extend(franchises[:1])
                # Add specific recent years if "latest", "new", or "recent" is mentioned
                if 'latest' in message_lower or 'new' in message_lower or 'recent' in message_lower:
                    # Add current year and previous year for truly latest movies
                    from datetime import datetime
                    current_year = datetime.now().year
                    search_parts.extend([str(current_year), str(current_year - 1)])  # 2025, 2024
            
            if language != "any":
                search_parts.append(language)
            if genres:
                search_parts.extend(genres[:2])
            if themes and not franchises:  # Don't add themes if we already have franchises
                search_parts.extend(themes[:1])
            if years:
                search_parts.extend(years[:1])
            
            search_query = " ".join(search_parts) if search_parts else user_message
            
            return {
                "intent_type": "movie_request",
                "confidence": 0.8,
                "movie_details": {
                    "movie_titles": [],
                    "genres": genres,
                    "years": years,
                    "themes": themes,
                    "franchises": franchises,
                    "mood": mood,
                    "language": language,
                    "search_query": search_query,
                    "search_variations": self._build_search_variations(search_query, franchises, message_lower)
                },
                "user_intent_analysis": {
                    "what_they_want": f"{franchises[0]} movies" if franchises else "general movie recommendations",
                    "is_specific_movie": False,
                    "confidence_in_movie_match": "medium"
                },
                "response_style": "informative"
            }
        
        # Default to general chat
        return {
            "intent_type": "general_chat",
            "confidence": 0.5,
            "response_style": "conversational"
        }
    
    def _detect_specific_movie(self, user_message: str) -> Optional[Dict[str, Any]]:
        """Detect and research specific movie requests in fallback mode"""
        import difflib
        
        message_lower = user_message.lower().strip()
        
        # Known movie database (fallback when LLM API fails)
        known_movies = {
            "rrr": {
                "full_title": "RRR",
                "release_year": "2022",
                "alternate_names": ["RRR (Rise Roar Revolt)", "Roudram Ranam Rudhiram"],
                "key_details": "Telugu epic action film by S.S. Rajamouli starring Ram Charan and Jr. NTR",
                "language": "telugu",
                "genres": ["action", "drama"],
                "search_variations": ["RRR", "RRR 2022", "RRR movie", "RRR telugu"]
            },
            "avatar": {
                "full_title": "Avatar",
                "release_year": "2009",
                "alternate_names": ["Avatar: The Way of Water (2022 sequel)"],
                "key_details": "James Cameron sci-fi film starring Sam Worthington",
                "language": "english",
                "genres": ["sci-fi", "action"],
                "search_variations": ["Avatar", "Avatar 2009", "Avatar James Cameron"]
            },
            "john wick": {
                "full_title": "John Wick",
                "release_year": "2014",
                "alternate_names": ["John Wick Chapter series"],
                "key_details": "Action thriller starring Keanu Reeves",
                "language": "english",
                "genres": ["action", "thriller"],
                "search_variations": ["John Wick", "John Wick 2014", "John Wick movie"]
            },
            "avengers endgame": {
                "full_title": "Avengers: Endgame",
                "release_year": "2019",
                "alternate_names": ["Endgame"],
                "key_details": "Marvel superhero film, final Infinity Saga movie",
                "language": "english",
                "genres": ["action", "adventure"],
                "search_variations": ["Avengers Endgame", "Avengers: Endgame", "Endgame"]
            },
            "kgf": {
                "full_title": "K.G.F: Chapter 1",
                "release_year": "2018",
                "alternate_names": ["KGF", "K.G.F Chapter 2 (2022)"],
                "key_details": "Kannada action film starring Yash",
                "language": "kannada",
                "genres": ["action", "drama"],
                "search_variations": ["KGF", "K.G.F", "KGF Chapter 1"]
            },
            "pushpa": {
                "full_title": "Pushpa: The Rise",
                "release_year": "2021",
                "alternate_names": ["Pushpa Part 1"],
                "key_details": "Telugu action drama starring Allu Arjun",
                "language": "telugu",
                "genres": ["action", "drama"],
                "search_variations": ["Pushpa", "Pushpa The Rise", "Pushpa movie"]
            }
        }
        
        # Enhanced matching code using difflib
        known_titles = list(known_movies.keys())
        close = difflib.get_close_matches(message_lower, known_titles, n=1, cutoff=0.6)
        if close:
            movie_key = close[0]
            movie_data = known_movies[movie_key]
            
            return {
                "intent_type": "movie_request",
                "confidence": 0.9,
                "movie_details": {
                    "movie_titles": [movie_data["full_title"]],
                    "genres": movie_data["genres"],
                    "years": [movie_data["release_year"]],
                    "language": movie_data["language"],
                    "movie_research": movie_data,
                    "search_query": f"{movie_data['full_title']} {movie_data['release_year']}",
                    "search_variations": movie_data["search_variations"]
                },
                "user_intent_analysis": {
                    "what_they_want": f"the specific movie {movie_data['full_title']} ({movie_data['release_year']})",
                    "is_specific_movie": True,
                    "confidence_in_movie_match": "high"
                },
                "response_style": "informative"
            }
        
        # Clean the message for matching
        clean_message = re.sub(r'\b(movie|film|watch|download)\b', '', message_lower).strip()
        
        # Check for exact matches or close matches
        for movie_key, movie_data in known_movies.items():
            if (movie_key in clean_message or 
                clean_message in movie_key or
                any(alt.lower() in clean_message for alt in movie_data["alternate_names"])):
                
                return {
                    "intent_type": "movie_request",
                    "confidence": 0.9,
                    "movie_details": {
                        "movie_titles": [movie_data["full_title"]],
                        "genres": movie_data["genres"],
                        "years": [movie_data["release_year"]],
                        "language": movie_data["language"],
                        "movie_research": movie_data,
                        "search_query": f"{movie_data['full_title']} {movie_data['release_year']}",
                        "search_variations": movie_data["search_variations"]
                    },
                    "user_intent_analysis": {
                        "what_they_want": f"the specific movie {movie_data['full_title']} ({movie_data['release_year']})",
                        "is_specific_movie": True,
                        "confidence_in_movie_match": "high"
                    },
                    "response_style": "informative"
                }
        
        return None
    
    def _build_search_variations(self, search_query: str, franchises: List[str], message_lower: str) -> List[str]:
        """Build multiple search variations for better movie finding, especially for latest requests"""
        variations = [search_query]
        
        if franchises:
            franchise = franchises[0]
            variations.append(franchise)
            
            # For latest requests, create year-specific variations
            if 'latest' in message_lower or 'new' in message_lower or 'recent' in message_lower:
                from datetime import datetime
                current_year = datetime.now().year
                
                # Add variations with specific years
                variations.extend([
                    f"{franchise} {current_year}",      # "marvel 2025"
                    f"{franchise} {current_year - 1}",  # "marvel 2024"
                    f"{franchise} movies {current_year}",
                    f"{franchise} movies {current_year - 1}",
                    f"new {franchise} movies",
                    f"latest {franchise}",
                    f"recent {franchise} movies"
                ])
        
        # Remove duplicates while preserving order
        seen = set()
        unique_variations = []
        for var in variations:
            if var not in seen:
                seen.add(var)
                unique_variations.append(var)
        
        return unique_variations
    
    def _looks_like_movie_title(self, text: str) -> bool:
        """Heuristic to decide if a short user input likely refers to a movie title.
        Examples: 'rrr', 'constable kanakam', 'pushpa', 'john wick 4'
        """
        if not text:
            return False
        t = text.strip()
        # Must contain letters
        if not re.search(r"[A-Za-z]", t):
            return False
        # Too long sentences are unlikely to be titles
        if len(t) > 60:
            return False
        # Token-based checks
        tokens = re.split(r"\s+", t)
        if len(tokens) > 6:
            return False
        # Avoid typical greeting/personal starters
        lowered = t.lower()
        bad_starts = ("hello", "hi ", "hey ", "how are", "what is", "who are", "i want", "i need", "suggest")
        if any(lowered.startswith(bs) for bs in bad_starts):
            return False
        # Avoid sentences ending with question mark (likely not just a title)
        if lowered.endswith('?'):
            return False
        # Avoid containing URL-like patterns
        if 'http://' in lowered or 'https://' in lowered:
            return False
        return True
    
    def _init_movie_agents(self):
        """Initialize movie search agents safely using AgentManager"""
        try:
            from agent_manager import AgentManager
            self.agent_manager = AgentManager()
            self.agent_manager.initialize_agents()
            
            # Get only enabled agents from the agent manager
            enabled_agents = self.agent_manager.get_enabled_agents()
            self.movie_agents = enabled_agents
            
            logger.info(f"Initialized {len(self.movie_agents)} enabled movie search agents: {list(self.movie_agents.keys())}")
            
            if not self.movie_agents:
                logger.warning("No movie agents are enabled! Please enable at least one agent in the admin panel.")
            
        except Exception as e:
            logger.error(f"Failed to initialize movie agents through AgentManager: {e}")
            # Fallback to manual initialization (old behavior) if AgentManager fails
            self._init_movie_agents_fallback()
    
    def _init_movie_agents_fallback(self):
        """Fallback method to initialize movie agents manually (old behavior)"""
        logger.warning("Using fallback agent initialization - agents may not respect enabled/disabled settings")
        try:
            from agents.movierulz_agent import MovieRulzAgent
            self.movie_agents['movierulz'] = MovieRulzAgent()
            logger.info("MovieRulz agent initialized (fallback)")
        except Exception as e:
            logger.error(f"Failed to initialize MovieRulz agent: {e}")
        
        try:
            from agents.moviezwap_agent import MoviezWapAgent
            self.movie_agents['moviezwap'] = MoviezWapAgent()
            logger.info("MoviezWap agent initialized (fallback)")
        except Exception as e:
            logger.error(f"Failed to initialize MoviezWap agent: {e}")
        
        try:
            from agents.enhanced_downloadhub_agent import EnhancedDownloadHubAgent
            self.movie_agents['downloadhub'] = EnhancedDownloadHubAgent()
            logger.info("DownloadHub agent initialized (fallback)")
        except Exception as e:
            logger.error(f"Failed to initialize DownloadHub agent: {e}")
        
        logger.info(f"Fallback initialization completed: {len(self.movie_agents)} agents: {list(self.movie_agents.keys())}")
    
    def refresh_agents(self):
        """Refresh movie agents based on current configuration"""
        logger.info("Refreshing movie agents based on current configuration...")
        self._init_movie_agents()
    
    def get_enabled_agent_names(self) -> List[str]:
        """Get list of currently enabled agent names"""
        if hasattr(self, 'agent_manager') and self.agent_manager:
            return self.agent_manager.get_enabled_agent_names()
        else:
            # Fallback: return names of initialized agents
            return [agent_name.title() + " Agent" for agent_name in self.movie_agents.keys()]
    
    def _search_via_api_endpoint(self, search_query: str) -> Dict[str, Any]:
        """Search for movies using the actual /search endpoint via HTTP request"""
        try:
            import requests
            import os
            
            # Try to determine the correct base URL
            base_urls = [
                "http://127.0.0.1:5000",  # Default Flask dev server
                "http://localhost:5000",   # Alternative localhost
                "http://127.0.0.1:8080",  # Alternative port
                "http://localhost:8080",   # Alternative port
            ]
            
            # Check if we're running on a specific port from environment
            port = os.environ.get('PORT')
            if port:
                base_urls.insert(0, f"http://127.0.0.1:{port}")
                base_urls.insert(1, f"http://localhost:{port}")
            
            search_data = {
                'movie_name': search_query,
                'page': 1
            }
            
            headers = {'Content-Type': 'application/json'}
            
            # Try each base URL until one works
            for base_url in base_urls:
                try:
                    logger.info(f"Trying to search via {base_url}/search")
                    response = requests.post(
                        f"{base_url}/search",
                        json=search_data,
                        headers=headers,
                        timeout=30
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        if data.get('success'):
                            movies = data.get('results', [])
                            logger.info(f"Found {len(movies)} movies via /search endpoint at {base_url}")
                            return {"movies": movies}
                        else:
                            logger.warning(f"Search endpoint returned error: {data.get('error', 'Unknown error')}")
                            return {"movies": []}
                    else:
                        logger.debug(f"Search endpoint at {base_url} returned status {response.status_code}")
                        continue
                        
                except requests.exceptions.ConnectionError:
                    logger.debug(f"Could not connect to {base_url}")
                    continue
                except requests.exceptions.Timeout:
                    logger.debug(f"Timeout connecting to {base_url}")
                    continue
                except Exception as e:
                    logger.debug(f"Error with {base_url}: {e}")
                    continue
            
            # If all HTTP attempts failed, fall back to direct search
            logger.warning("All HTTP endpoints failed, falling back to direct agent search")
            return self._fallback_direct_search(search_query)
                
        except Exception as e:
            logger.error(f"Error in _search_via_api_endpoint: {e}")
            # Fallback to direct agent search
            return self._fallback_direct_search(search_query)
    
    def _fallback_direct_search(self, search_query: str) -> Dict[str, Any]:
        """Fallback method to search directly using agents if /search endpoint is not available"""
        try:
            if not self.movie_agents:
                logger.warning("No movie agents available for fallback search")
                return {"movies": []}
            
            all_results = []
            
            # Search using available agents (simplified version)
            for agent_name, agent in list(self.movie_agents.items())[:2]:  # Use only first 2 agents for speed
                try:
                    logger.info(f"Fallback search using {agent_name} for: {search_query}")
                    result = agent.search_movies(search_query)
                    if result and result.get('movies'):
                        movies = result['movies']
                        # Add source identifier
                        for movie in movies:
                            movie['source'] = agent_name.title()
                        all_results.extend(movies[:10])  # Limit to 10 per source
                except Exception as e:
                    logger.error(f"Error in fallback search with {agent_name}: {e}")
                    continue
            
            # Remove duplicates
            unique_movies = self._remove_duplicate_movies(all_results)
            logger.info(f"Fallback search found {len(unique_movies)} unique movies")
            
            return {"movies": unique_movies[:20]}  # Limit to 20 total
            
        except Exception as e:
            logger.error(f"Error in fallback search: {e}")
            return {"movies": []}

    def search_movies_with_sources(self, search_query: str, search_variations: List[str] = None) -> Dict[str, Any]:
        """Search for movies across all available sources in parallel"""
        if not search_variations:
            search_variations = [search_query]
        
        if not self.movie_agents:
            return {
                "movies": [],
                "search_summary": {
                    "total_movies": 0,
                    "sources_searched": [],
                    "successful_sources": [],
                    "error": "No movie search agents available"
                }
            }
        
        all_results = []
        search_summary = {
            "total_movies": 0,
            "sources_searched": [],
            "successful_sources": [],
            "search_queries_used": search_variations
        }
        
        # Search across all agents with timeout, trying multiple variations
        with ThreadPoolExecutor(max_workers=len(self.movie_agents) * min(3, len(search_variations))) as executor:
            future_to_agent = {}
            
            for agent_name, agent in self.movie_agents.items():
                # Try multiple search variations for better results
                variations_to_try = search_variations[:3]  # Try top 3 variations
                for i, query in enumerate(variations_to_try):
                    future = executor.submit(self._safe_search, agent, agent_name, query)
                    future_to_agent[future] = (agent_name, query, i)
            
            # Collect results with timeout - use try-catch for each future
            try:
                for future in as_completed(future_to_agent, timeout=90):  # Increased total timeout to 90 seconds
                    agent_name, query, variation_index = future_to_agent[future]
                    try:
                        result = future.result(timeout=45)  # Increased per agent timeout to 45 seconds
                        if result and result.get('movies'):
                            all_results.extend(result['movies'])
                            source_info = f"{agent_name} (query: '{query}')"
                            if source_info not in search_summary["successful_sources"]:
                                search_summary["successful_sources"].append(source_info)
                            logger.info(f"Found {len(result['movies'])} movies from {agent_name} using query: '{query}'")
                        
                        search_info = f"{agent_name} (variation {variation_index + 1})"
                        if search_info not in search_summary["sources_searched"]:
                            search_summary["sources_searched"].append(search_info)
                        
                    except Exception as e:
                        logger.error(f"Error searching {agent_name} with query '{query}': {str(e)}")
                        error_info = f"{agent_name} ('{query}') - FAILED: {str(e)}"
                        if error_info not in search_summary["sources_searched"]:
                            search_summary["sources_searched"].append(error_info)
            except Exception as timeout_error:
                logger.warning(f"Overall search timeout reached: {str(timeout_error)}")
                # Continue with whatever results we have so far
        
        # Remove duplicates and sort
        unique_movies = self._remove_duplicate_movies(all_results)
        sorted_movies = self._sort_by_relevance(unique_movies, search_query)
        
        search_summary["total_movies"] = len(sorted_movies)
        
        return {
            "movies": sorted_movies[:20],  # Limit to top 20 results
            "search_summary": search_summary,
            "search_query": search_query,
            "total_found": len(sorted_movies)
        }
    
    def _safe_search(self, agent, agent_name: str, query: str) -> Optional[Dict[str, Any]]:
        """Safely search using an agent with error handling"""
        try:
            logger.info(f"Searching {agent_name} for: {query}")
            result = agent.search_movies(query)
            return result
        except Exception as e:
            logger.error(f"Error in {agent_name} search: {str(e)}")
            return None
    
    def _remove_duplicate_movies(self, movies: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate movies based on title similarity"""
        unique_movies = []
        seen_titles = set()
        
        for movie in movies:
            title = movie.get('title', '').lower().strip()
            title_key = re.sub(r'[^\w\s]', '', title)
            
            if title_key not in seen_titles and title_key:
                seen_titles.add(title_key)
                unique_movies.append(movie)
        
        return unique_movies
    
    def _sort_by_relevance(self, movies: List[Dict[str, Any]], search_query: str) -> List[Dict[str, Any]]:
        """Sort movies by relevance to search query"""
        if not movies or not search_query:
            return movies
        
        search_lower = search_query.lower()
        is_latest_request = any(word in search_lower for word in ['latest', 'new', 'recent', '2024', '2025'])
        
        def relevance_score(movie):
            title = movie.get('title', '').lower()
            year = str(movie.get('year', ''))
            
            score = 0
            
            # For "latest" requests, heavily prioritize recent years
            if is_latest_request and year:
                try:
                    movie_year = int(year)
                    current_year = 2025  # Current year
                    year_diff = current_year - movie_year
                    
                    if year_diff <= 1:  # 2024-2025
                        score += 200  # Highest priority for very recent
                    elif year_diff <= 2:  # 2023
                        score += 150
                    elif year_diff <= 3:  # 2022
                        score += 100
                    elif year_diff <= 5:  # 2020-2021
                        score += 50
                    else:  # Older than 2020
                        score += 10  # Much lower priority for old movies
                except ValueError:
                    pass
            
            # Exact title match gets high score
            if search_lower == title:
                score += 100
            
            # Title contains search query
            elif search_lower in title:
                score += 50
            
            # Search query contains title (for short titles)
            elif title in search_lower:
                score += 30
            
            # Year match bonus
            if year and year in search_query:
                score += 20
            
            # Quality bonus (higher quality = higher score)
            quality = movie.get('quality', '')
            if isinstance(quality, list):
                quality = ' '.join(str(q) for q in quality)
            quality = str(quality).lower()
            
            if '1080p' in quality:
                score += 10
            elif '720p' in quality:
                score += 5
            
            # Source reliability bonus
            source = movie.get('source', '').lower()
            if 'downloadhub' in source:
                score += 3
            elif 'movierulz' in source:
                score += 2
            elif 'moviezwap' in source:
                score += 1
            
            return score
        
        return sorted(movies, key=relevance_score, reverse=True)
    
    def process_movie_request(self, user_message: str, session_id: str = None) -> Dict[str, Any]:
        """Process a movie request and return response with search results"""
        # Get session context for better responses
        conversation_context = ""
        if session_id:
            conversation_context = session_manager.get_conversation_context(session_id)
        
        # Analyze user intent with session context
        intent = self.analyze_user_intent(user_message, conversation_context)

        # SMART MOVIE DETECTION: Force movie_request for any movie-related input
        # Users come here to download movies, so be aggressive about detecting movie intent
        normalized_input = user_message.lower().strip()
        
        # Enhanced movie detection patterns
        movie_indicators = [
            'download', 'watch', 'movie', 'film', 'latest', 'new', 'release', 'quality',
            'hindi', 'english', 'tamil', 'telugu', 'bollywood', 'hollywood', '2023', '2024',
            'mp4', 'mkv', 'hd', '720p', '1080p', '4k'
        ]
        
        contains_movie_indicator = any(indicator in normalized_input for indicator in movie_indicators)
        looks_like_title = self._looks_like_movie_title(user_message)
        
        # Don't override clear greetings or personal messages
        is_clear_greeting = normalized_input in ['hello', 'hi', 'hey', 'hlo', 'helo', 'hallo']
        is_clear_personal = any(p in normalized_input for p in ['how are you', 'who are you', 'what are you'])
        
        # If not already a movie request but has movie indicators or looks like title, make it one
        # BUT respect clear greetings, personal questions, date/time, and information requests
        if (intent.get('intent_type') not in ('movie_request', 'greeting', 'personal', 'date_time', 'information_request') and 
            (contains_movie_indicator or looks_like_title) and 
            not is_clear_greeting and not is_clear_personal):
            
            intent['intent_type'] = 'movie_request'
            intent.setdefault('movie_details', {})
            intent['movie_details']['search_query'] = user_message.strip()
            intent['movie_details'].setdefault('search_variations', [user_message.strip()])
            
            # Add context that this is a download-focused request
            intent['user_intent_analysis'] = {
                'what_they_want': 'download links for movie',
                'is_specific_movie': looks_like_title,
                'download_focused': True
            }
        
        response_data = {
            "intent": intent,
            "response_text": "",
            "movies": [],
            "search_performed": False,
            "session_id": session_id
        }

        # Heuristic: detect short confirmation responses like "yes", "yeah", "correct",
        # and, if the previous turn was a specific movie confirmation, reuse last movie context
        normalized = user_message.strip().lower()
        is_affirmation = normalized in {"yes","y","yeah","yep","correct","exactly","right","sure","ok","okay"}

        
        # MOVIE SEARCH LOGIC: Use the /search endpoint like the /api page
        if intent.get("intent_type") == "movie_request":
            
            movie_details = intent.get("movie_details", {})
            search_query = movie_details.get("search_query", user_message.strip())
            
            # If no specific search query, use the user message directly
            if not search_query.strip():
                search_query = user_message.strip()
            
            logger.info(f"Performing movie search using /search endpoint for: {search_query}")
            
            # Use the same search endpoint that /api uses
            search_results = self._search_via_api_endpoint(search_query)
            found_movies = search_results.get("movies", [])
            
            if found_movies:
                # SUCCESS: Found movies using the API endpoint
                response_data["movies"] = found_movies
                response_data["search_performed"] = True
                response_data["search_level"] = "API_SUCCESS"
                
                # Set movie context for follow-ups
                if session_id and found_movies:
                    top = found_movies[0]
                    try:
                        session_manager.set_movie_context(session_id, {
                            'title': top.get('title'),
                            'year': top.get('year'),
                            'source': top.get('source'),
                            'url': top.get('url') or top.get('detail_url')
                        })
                    except Exception:
                        pass
                
                # Generate download-focused response
                response_data["response_text"] = self._generate_simple_movie_response(user_message, intent, found_movies)
            
            else:
                # No movies found
                logger.info(f"No movies found for: {search_query}")
                
                response_data["movies"] = []
                response_data["search_performed"] = True
                response_data["search_level"] = "NO_RESULTS_FOUND"
                
                # Generate no results response
                response_data["response_text"] = self._generate_no_results_response(user_message, intent, search_query)
        else:
            # If user simply confirms (e.g. "yes") and we have a previous movie context, reuse it to search
            if is_affirmation and session_id:
                ctx = session_manager.get_session(session_id)
                prev = (ctx or {}).get('movie_context') or {}
                if prev.get('title'):
                    logger.info(f"Affirmation detected; reusing movie context: {prev['title']}")
                    search_results = self._search_via_api_endpoint(prev['title'])
                    response_data["movies"] = search_results.get("movies", [])
                    response_data["search_performed"] = True
                    response_data["response_text"] = self._generate_simple_movie_response(user_message, intent, search_results.get("movies", []))
                else:
                    # If affirmation but no context, fall back to contextual response
                    response_data["response_text"] = self.generate_contextual_response(user_message, intent)
            elif (self._looks_like_movie_title(user_message) and 
                  not is_clear_greeting and not is_clear_personal and
                  intent.get('intent_type') not in ('date_time', 'information_request')):
                # If the user typed a likely movie title but LLM intent didn't trigger, force a movie search
                # BUT don't search if it's clearly a greeting, personal question, date/time, or info request
                title = user_message.strip()
                search_results = self._search_via_api_endpoint(title)
                response_data["movies"] = search_results.get("movies", [])
                response_data["search_performed"] = True
                response_data["response_text"] = self._generate_simple_movie_response(user_message, intent, search_results.get("movies", []))
            else:
                # Generate non-movie response
                response_data["response_text"] = self.generate_contextual_response(user_message, intent)
        
        return response_data
    
    def generate_contextual_response(self, user_message: str, intent: Dict[str, Any], search_results: List[Dict] = None) -> str:
        """Generate contextual response based on intent analysis"""
        
        intent_type = intent.get("intent_type", "general_chat")
        
        if intent_type == "greeting":
            return self._generate_greeting_response(user_message, intent)
        elif intent_type == "personal":
            return self._generate_personal_response(user_message, intent)
        elif intent_type == "movie_request":
            return self._generate_movie_response(user_message, intent, search_results)
        elif intent_type == "date_time":
            return self._generate_date_time_response(user_message, intent)
        elif intent_type == "information_request":
            return self._generate_information_response(user_message, intent)
        else:
            return self._generate_general_response(user_message, intent)
    
    def _generate_greeting_response(self, user_message: str, intent: Dict[str, Any]) -> str:
        """Generate friendly greeting response"""
        try:
            system_prompt = f"""You are {self.agent_personality['name']}, a {self.agent_personality['role']}. 
You are {', '.join(self.agent_personality['traits'])}.

The user just greeted you. Respond warmly and personally, then smoothly introduce your movie expertise.
Keep it conversational and inviting. Ask what kind of movies they're in the mood for.

Be natural, friendly, and show enthusiasm for helping with movies."""

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ]
            
            # Validate parameters
            if not self.model or not messages:
                logger.error("Invalid parameters for greeting response")
                return "Hello! I'm your AI movie assistant. I'm here to help you discover amazing movies. What kind of movies are you in the mood for today?"
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.8
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error generating greeting response: {str(e)}")
            return "Hello! I'm your AI movie assistant. I'm here to help you discover amazing movies. What kind of movies are you in the mood for today?"
    
    def _generate_personal_response(self, user_message: str, intent: Dict[str, Any]) -> str:
        """Generate empathetic personal response"""
        try:
            personal_context = intent.get("personal_context", {})
            emotional_tone = personal_context.get("emotional_tone", "neutral")
            requires_empathy = personal_context.get("requires_empathy", False)
            
            system_prompt = f"""You are {self.agent_personality['name']}, a {self.agent_personality['role']}.
You are {', '.join(self.agent_personality['traits'])}.

The user asked a personal question or shared something personal. 
Emotional tone detected: {emotional_tone}
Requires empathy: {requires_empathy}

Respond personally and authentically as an AI assistant. Be empathetic if needed.
After addressing their personal question, gently connect it to movies if appropriate.
For example, if they're sad, you might suggest uplifting movies.

Be genuine, caring, and helpful."""

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ]
            
            # Validate parameters before API call
            if not messages or len(messages) == 0:
                logger.error("No messages to send to Together API")
                return "I found some movies but couldn't generate a proper response. Please try again."
            
            # Ensure all messages have valid structure
            for msg in messages:
                if not isinstance(msg.get("content"), str) or not msg.get("content").strip():
                    logger.error(f"Invalid message content: {msg}")
                    return "I found some movies but encountered an issue generating the response."
            
            try:
                # Validate model name and parameters
                if not self.model or not isinstance(self.model, str):
                    logger.error(f"Invalid model: {self.model}")
                    return "I found some movies but couldn't generate a proper response. Please try again."
                
                # Ensure max_tokens is within valid range
                max_tokens = min(500, 4000)  # Together API limit
                
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.7
                )
            except Exception as api_error:
                logger.error(f"Together API call failed: {api_error}")
                return "I found some movies but couldn't generate a detailed response. Please try again."
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error generating personal response: {str(e)}")
            return "I'm doing well, thank you for asking! As an AI movie assistant, I'm always excited to help people discover great movies. How can I help you find something amazing to watch?"
    
    def _generate_movie_response(self, user_message: str, intent: Dict[str, Any], search_results: List[Dict] = None) -> str:
        """Generate intelligent movie response with search results"""
        try:
            movie_details = intent.get("movie_details", {})
            
            # Build context from search results
            search_context = ""
            if search_results and isinstance(search_results, dict):
                movies_list = search_results.get('movies', [])
                search_context = f"\nI found these movies for you:\n"
                for i, movie in enumerate(movies_list[:8]):  # Limit to 8 for context
                    quality = movie.get('quality', 'Unknown')
                    if isinstance(quality, list):
                        quality = ', '.join(str(q) for q in quality)
                    search_context += f"- {movie.get('title', 'Unknown')} ({movie.get('year', 'Unknown')}) - {quality} from {movie.get('source', 'Unknown')}\n"
            elif search_results and isinstance(search_results, list):
                search_context = f"\nI found these movies for you:\n"
                for i, movie in enumerate(search_results[:8]):  # Limit to 8 for context
                    quality = movie.get('quality', 'Unknown')
                    if isinstance(quality, list):
                        quality = ', '.join(str(q) for q in quality)
                    search_context += f"- {movie.get('title', 'Unknown')} ({movie.get('year', 'Unknown')}) - {quality} from {movie.get('source', 'Unknown')}\n"
            else:
                search_context = "\nI couldn't find specific movies matching your request, but I can still help with recommendations."
            
            # Get user intent analysis for better context
            user_analysis = intent.get("user_intent_analysis", {})
            what_they_want = user_analysis.get("what_they_want", "movies")
            is_specific_movie = user_analysis.get("is_specific_movie", False)
            
            # Get movie research details if available
            movie_research = movie_details.get("movie_research", {})
            
            system_prompt = f"""You are {self.agent_personality['name']}, a {self.agent_personality['role']}.
You are {', '.join(self.agent_personality['traits'])}.

IMPORTANT: DO NOT list individual movies in your response. The UI already displays movies in a structured format below your response.

UNDERSTAND THE USER'S REQUEST:
The user wants: {what_they_want}
Is this a specific movie request: {is_specific_movie}

{'MOVIE RESEARCH DETAILS:' if movie_research else ''}
{f"- Full Title: {movie_research.get('full_title', '')}" if movie_research.get('full_title') else ''}
{f"- Release Year: {movie_research.get('release_year', '')}" if movie_research.get('release_year') else ''}
{f"- Key Details: {movie_research.get('key_details', '')}" if movie_research.get('key_details') else ''}
{f"- Alternate Names: {movie_research.get('alternate_names', [])}" if movie_research.get('alternate_names') else ''}

User preferences:
- Movie titles: {movie_details.get('movie_titles', [])}
- Genres: {movie_details.get('genres', [])}
- Themes: {movie_details.get('themes', [])}
- Years: {movie_details.get('years', [])}
- Language: {movie_details.get('language', 'any')}

SEARCH RESULTS CONTEXT:
{search_context}

RESPOND INTELLIGENTLY:

If this is a SPECIFIC MOVIE request and movies were found:
- Confirm if the found movie matches what they're looking for
- Mention the movie details you researched (title, year, key info)
- Ask for confirmation: "Is this the {movie_research.get('full_title', 'movie')} you were looking for?"
- Highlight the available qualities and sources

If this is a SPECIFIC MOVIE request but no movies found:
- Acknowledge the specific movie they wanted
- Mention the correct details you found about the movie
- Suggest alternative search terms or spellings
- Offer to search for similar movies or the sequel/prequel

If this is a GENERAL movie request:
- Acknowledge their preferences and mood
- Comment on the variety of results found
- Give personalized recommendations based on their criteria

Be helpful, specific, and always confirm when dealing with specific movie requests!"""

            # Add to conversation history
            self.conversation_history.append({"role": "user", "content": user_message})
            
            # Build messages with proper validation
            messages = [{"role": "system", "content": system_prompt}]
            
            # Add conversation history with validation
            if self.conversation_history:
                # Only add valid messages and limit to prevent token overflow
                valid_history = []
                for msg in self.conversation_history[-4:]:  # Reduced from 6 to 4
                    if isinstance(msg, dict) and "role" in msg and "content" in msg:
                        # Ensure content is string and not too long
                        content = str(msg["content"])[:1000]  # Limit content length
                        if content.strip():  # Only add non-empty content
                            valid_history.append({"role": msg["role"], "content": content})
                
                messages.extend(valid_history)
            
            # Validate parameters before API call
            if not self.model or not messages:
                logger.error("Invalid parameters for movie response")
                return "I found some movies but couldn't generate a proper response. Please try again."
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7
            )
            
            assistant_response = response.choices[0].message.content
            
            # Add assistant response to history
            self.conversation_history.append({"role": "assistant", "content": assistant_response})
            
            return assistant_response
            
        except Exception as e:
            logger.error(f"Error generating movie response: {str(e)}")
            if search_results:
                return f"I found {len(search_results)} movies for you! Check out the results below - they include different qualities and sources. Click 'Extract Links' on any movie to get download options."
            else:
                return "I'd love to help you find some great movies! Could you tell me more about what you're looking for? Maybe a specific genre, actor, or type of mood you're in?"
    
    def _generate_simple_movie_response(self, user_message: str, intent: Dict[str, Any], movies: List[Dict[str, Any]]) -> str:
        """Generate a simple response for found movies without listing them individually"""
        try:
            if not movies:
                return "I couldn't find any movies matching your request. Please try a different search term."
            
            total_found = len(movies)
            
            # Check if this is a specific movie request
            user_analysis = intent.get("user_intent_analysis", {})
            is_specific = user_analysis.get("is_specific_movie", False)
            movie_research = intent.get("movie_details", {}).get("movie_research", {})
            
            if not self.has_api_key:
                # Simple fallback response when no API key
                if is_specific and movie_research.get('full_title'):
                    return f"Great! I found {total_found} result(s) for '{movie_research['full_title']}'. Check out the movies below and click 'Extract Links' to get download options!"
                else:
                    return f"Perfect! I found {total_found} movies for you. Browse through the results below and click 'Extract Links' on any movie to get download options!"
            
            system_prompt = f"""You are a movie download assistant. The user searched for movies and you found results.

USER REQUEST: "{user_message}"
IS SPECIFIC MOVIE: {is_specific}
MOVIES FOUND: {total_found}

{'MOVIE RESEARCH:' if movie_research else ''}
{f"- Title: {movie_research.get('full_title', '')}" if movie_research.get('full_title') else ''}
{f"- Year: {movie_research.get('release_year', '')}" if movie_research.get('release_year') else ''}

IMPORTANT: DO NOT list individual movies in your response. The UI displays movies in cards below your response.

RESPOND WITH:
1. Confirm you found the movie(s) they wanted
2. Mention the number of results found
3. Guide them to click "Extract Links" to get download links
4. Be enthusiastic about helping them download movies

If specific movie: Confirm if this matches what they wanted
If general request: Mention the variety of options found

Keep response focused on DOWNLOADING and be concise."""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.7
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error generating simple movie response: {str(e)}")
            # Fallback response
            if movies:
                return f"Great! I found {len(movies)} movies for you. Check out the results below and click 'Extract Links' on any movie to get download options!"
            else:
                return "I couldn't find any movies matching your request. Please try a different search term."

    def _generate_download_focused_response(self, user_message: str, intent: Dict[str, Any], search_results: Dict[str, Any]) -> str:
        """Generate download-focused response when movies are found"""
        try:
            movies_list = search_results.get('movies', [])
            total_found = len(movies_list)
            
            if total_found == 0:
                return "I couldn't find any movies matching your request in our download sources. Let me try some alternative search terms for you."
            
            # Build context about found movies
            movie_context = f"Found {total_found} movie(s) with download links:\n"
            for i, movie in enumerate(movies_list[:5]):  # Show top 5
                quality = movie.get('quality', 'Unknown')
                if isinstance(quality, list):
                    quality = ', '.join(str(q) for q in quality)
                movie_context += f"- {movie.get('title', 'Unknown')} ({movie.get('year', 'Unknown')}) - {quality} from {movie.get('source', 'Unknown')}\n"
            
            # Check if this is a specific movie request
            user_analysis = intent.get("user_intent_analysis", {})
            is_specific = user_analysis.get("is_specific_movie", False)
            movie_research = intent.get("movie_details", {}).get("movie_research", {})
            
            system_prompt = f"""You are a movie download assistant. Users come here specifically to download movies.
            
IMPORTANT: DO NOT list individual movies in your response. The UI displays movies in cards below your response.

USER REQUEST: "{user_message}"
IS SPECIFIC MOVIE: {is_specific}

SEARCH RESULTS CONTEXT:
{movie_context}

{'MOVIE RESEARCH:' if movie_research else ''}
{f"- Title: {movie_research.get('full_title', '')}" if movie_research.get('full_title') else ''}
{f"- Year: {movie_research.get('release_year', '')}" if movie_research.get('release_year') else ''}
{f"- Details: {movie_research.get('key_details', '')}" if movie_research.get('key_details') else ''}

RESPOND WITH:
1. Confirm you found the movie(s) they wanted
2. Highlight the available sources and qualities
3. Guide them to click "Extract Links" to get download links
4. Be enthusiastic about helping them download movies

If specific movie: Confirm if this matches what they wanted
If general request: Mention the variety of options found

Keep response focused on DOWNLOADING, not streaming platforms."""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.7
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error generating download-focused response: {str(e)}")
            return f"Great! I found {len(search_results.get('movies', []))} movies for you with download links. Click 'Extract Links' on any movie below to get the download options!"
    
    def _generate_no_results_response(self, user_message: str, intent: Dict[str, Any], search_query: str) -> str:
        """Generate helpful response when no movies are found in APIs"""
        try:
            movie_details = intent.get("movie_details", {})
            movie_research = movie_details.get("movie_research", {})
            
            system_prompt = f"""You are a movie download assistant. The user searched for a movie but we couldn't find it in our download sources.

USER SEARCHED FOR: "{user_message}"
SEARCH QUERY USED: "{search_query}"

{'MOVIE RESEARCH:' if movie_research else ''}
{f"- Title: {movie_research.get('full_title', '')}" if movie_research.get('full_title') else ''}
{f"- Year: {movie_research.get('release_year', '')}" if movie_research.get('release_year') else ''}
{f"- Details: {movie_research.get('key_details', '')}" if movie_research.get('key_details') else ''}

PROVIDE A HELPFUL RESPONSE:
1. Acknowledge the specific movie they wanted (if you have research info)
2. Explain that it's not currently available in our download sources
3. Suggest possible reasons (too new, different spelling, not yet released)
4. Offer to try alternative search terms
5. Suggest similar movies if possible

Be helpful and encouraging, not dismissive. Focus on finding download solutions."""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.7
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error generating no-results response: {str(e)}")
            # Fallback response
            if movie_research.get('full_title'):
                return f"I understand you're looking for '{movie_research['full_title']}' ({movie_research.get('release_year', 'Unknown year')}). Unfortunately, it's not currently available in our download sources. This could be because it's very new, not yet released, or might be listed under a different name. Try searching with alternative spellings or let me know if you'd like suggestions for similar movies!"
            else:
                return f"I couldn't find '{search_query}' in our current download sources. This might be because it's very new, not yet released, or listed differently. Try alternative spellings or let me know if you'd like suggestions for similar movies!"
    
    def _generate_date_time_response(self, user_message: str, intent: Dict[str, Any]) -> str:
        """Generate response for date/time questions"""
        try:
            from datetime import datetime
            import pytz
            
            # Get current date and time
            now = datetime.now()
            current_date = now.strftime("%A, %B %d, %Y")
            current_time = now.strftime("%I:%M %p")
            
            # Determine what specific info they want
            message_lower = user_message.lower()
            
            if 'time' in message_lower:
                return f"The current time is {current_time}. Is there a specific movie you'd like to watch today?"
            elif 'day' in message_lower:
                day_name = now.strftime("%A")
                return f"Today is {day_name}. Perfect day for watching a good movie! What genre are you in the mood for?"
            else:
                return f"Today's date is {current_date}. How about we find you a great movie to watch today?"
                
        except Exception as e:
            logger.error(f"Error generating date/time response: {str(e)}")
            return "I can help you with movie recommendations! What kind of movies are you interested in watching?"
    
    def _generate_information_response(self, user_message: str, intent: Dict[str, Any]) -> str:
        """Generate response for general information requests"""
        try:
            if not self.has_api_key:
                return "I'm primarily designed to help with movie recommendations and downloads. For general information, I'd suggest checking reliable sources online. Meanwhile, can I help you find some great movies to watch?"
            
            system_prompt = f"""You are {self.agent_personality['name']}, but the user is asking a general knowledge question, not about movies.

IMPORTANT: You should provide a helpful, accurate answer to their question, but then gently redirect the conversation back to movies since that's your specialty.

Be informative but concise. After answering their question, suggest how you can help them with movies.

User's question: "{user_message}" """

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ]
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error generating information response: {str(e)}")
            return "I'm primarily designed to help with movie recommendations and downloads. For detailed information on other topics, I'd suggest checking reliable sources. However, I'd love to help you find some great movies! What genre interests you?"
    
    def _generate_general_response(self, user_message: str, intent: Dict[str, Any]) -> str:
        """Generate general conversational response"""
        try:
            system_prompt = f"""You are {self.agent_personality['name']}, a {self.agent_personality['role']}.
You are {', '.join(self.agent_personality['traits'])}.

The user said something that's not specifically about movies or personal questions.
Respond helpfully and try to guide the conversation toward movies if appropriate.
Be conversational and show your movie expertise.

Keep responses concise but engaging."""

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ]
            
            # Validate parameters
            if not self.model or not messages:
                logger.error("Invalid parameters for general response")
                return "I'm here to help you discover amazing movies! Is there anything specific you'd like to watch, or would you like me to suggest something based on your mood?"
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error generating general response: {str(e)}")
            return "I'm here to help you discover amazing movies! Is there anything specific you'd like to watch, or would you like me to suggest something based on your mood?"
    
    def extract_movie_search_query(self, intent: Dict[str, Any]) -> str:
        """Extract the best search query for movie API with intelligent prioritization"""
        movie_details = intent.get("movie_details", {})
        user_analysis = intent.get("user_intent_analysis", {})
        
        # Priority 1: Specific movie with research (highest priority)
        if user_analysis.get("is_specific_movie") and movie_details.get("movie_research"):
            movie_research = movie_details["movie_research"]
            full_title = movie_research.get("full_title", "")
            release_year = movie_research.get("release_year", "")
            
            # Use full title with year for specific movies
            if full_title and release_year:
                return f"{full_title} {release_year}"
            elif full_title:
                return full_title
        
        # Priority 2: Specific movie titles mentioned
        if movie_details.get("movie_titles"):
            return movie_details["movie_titles"][0]
        
        # Priority 3: Pre-built search query from LLM analysis
        if movie_details.get("search_query"):
            return movie_details["search_query"]
        
        # Priority 4: Build intelligent query from components
        query_parts = []
        
        # Add language preference first (important for filtering)
        if movie_details.get("language") and movie_details["language"] != "any":
            query_parts.append(movie_details["language"])
        
        # Add genres (most important for discovery)
        if movie_details.get("genres"):
            query_parts.extend(movie_details["genres"][:2])  # Top 2 genres
        
        # Add themes (very specific)
        if movie_details.get("themes"):
            query_parts.extend(movie_details["themes"][:1])  # Top theme
        
        # Add year if recent (helps with relevance)
        if movie_details.get("years"):
            years = movie_details["years"]
            recent_years = [y for y in years if int(y) >= 2020]
            if recent_years:
                query_parts.append(recent_years[0])
        
        # Add actors (if mentioned specifically)
        if movie_details.get("actors"):
            query_parts.append(movie_details["actors"][0])
        
        # Fallback: Create query from mood/context
        if not query_parts:
            mood = movie_details.get("mood", "")
            if "exciting" in mood or "action" in mood:
                return "action movies"
            elif "funny" in mood or "laugh" in mood:
                return "comedy movies"
            elif "romantic" in mood:
                return "romance movies"
            elif "scary" in mood:
                return "horror movies"
            else:
                return "popular movies"
        
        return " ".join(query_parts)
    
    def get_search_variations(self, intent: Dict[str, Any]) -> List[str]:
        """Get multiple search variations for better movie finding"""
        movie_details = intent.get("movie_details", {})
        
        # If we have search variations from movie research, use them
        if movie_details.get("search_variations"):
            return movie_details["search_variations"]
        
        # Otherwise, create variations from the main search query
        main_query = self.extract_movie_search_query(intent)
        variations = [main_query]
        
        # Add variations for specific movies
        if movie_details.get("movie_titles"):
            title = movie_details["movie_titles"][0]
            variations.extend([title, f"{title} movie"])
            
            # Add year variations if available
            if movie_details.get("years"):
                year = movie_details["years"][0]
                variations.append(f"{title} {year}")
        
        return list(set(variations))  # Remove duplicates
    
    def generate_search_suggestions(self, user_message: str) -> List[str]:
        """Generate search suggestions based on user message"""
        try:
            system_prompt = """Generate 5 movie search suggestions based on the user's message.
Return only a simple list of movie titles or search terms, one per line.
Focus on popular, well-known movies that match their request.

Examples:
- If they want action: "John Wick", "Mission Impossible", "Fast and Furious"
- If they want comedy: "The Hangover", "Superbad", "Anchorman"
- If they mention a year: include popular movies from that year"""

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ]
            
            # Validate parameters
            if not self.model or not messages:
                logger.error("Invalid parameters for search suggestions")
                return ["Avengers Endgame", "The Dark Knight", "Inception", "Interstellar", "John Wick"]
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.8
            )
            
            suggestions = response.choices[0].message.content.strip().split('\n')
            return [s.strip('- ').strip() for s in suggestions if s.strip()][:5]
            
        except Exception as e:
            logger.error(f"Error generating search suggestions: {str(e)}")
            return ["Avengers Endgame", "The Dark Knight", "Inception", "Interstellar", "John Wick"]
    
    def clear_conversation(self):
        """Clear conversation history"""
        self.conversation_history = []
        logger.info("Conversation history cleared")

def main():
    """Test the Enhanced LLM Chat Agent"""
    try:
        agent = EnhancedLLMChatAgent("dummy_key")
        
        # Test different types of messages
        test_messages = [
            "Hello!",
            "How are you?",
            "I'm feeling sad today",
            "I want to watch The Matrix",
            "Suggest some action movies from 2023",
            "What's a good romantic comedy?"
        ]
        
        for message in test_messages:
            print(f"\nUser: {message}")
            intent = agent.analyze_user_intent(message)
            print(f"Intent: {intent['intent_type']} (confidence: {intent['confidence']})")
            
    except Exception as e:
        print(f"Test failed (expected with dummy key): {e}")

if __name__ == "__main__":
    main()