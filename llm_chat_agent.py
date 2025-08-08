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
            system_prompt = """You are an expert movie database assistant that analyzes user messages to understand their exact movie requests.

ANALYZE THE USER'S MESSAGE CAREFULLY and extract:
1. Intent type: "personal", "movie_request", "general_chat", or "greeting"
2. If they mention a specific movie, research and provide complete details
3. The best search terms for finding movies

FOR SPECIFIC MOVIE REQUESTS (like "rrr movie", "avatar", "john wick"):
- Research the movie thoroughly
- Provide the correct full title, year, and key details
- Handle common abbreviations and alternate names
- Suggest the best search terms

Respond in JSON format:
{
    "intent_type": "personal|movie_request|general_chat|greeting",
    "confidence": 0.9,
    "movie_details": {
        "movie_titles": ["exact movie names with full details"],
        "genres": ["specific genres"],
        "years": ["release years"],
        "actors": ["main actors"],
        "directors": ["directors"],
        "language": "movie language",
        "movie_research": {
            "full_title": "complete official movie title",
            "release_year": "year",
            "alternate_names": ["other known names"],
            "key_details": "important info about the movie"
        },
        "search_query": "BEST search term for movie APIs",
        "search_variations": ["alternative search terms to try"]
    },
    "user_intent_analysis": {
        "what_they_want": "specific movie or general preference",
        "is_specific_movie": true/false,
        "confidence_in_movie_match": "high/medium/low"
    }
}

MOVIE RESEARCH EXAMPLES:
- "rrr movie" → movie_research: {"full_title": "RRR", "release_year": "2022", "alternate_names": ["RRR (Rise Roar Revolt)", "Roudram Ranam Rudhiram"], "key_details": "Telugu epic action film by S.S. Rajamouli starring Ram Charan and Jr. NTR"}, search_query: "RRR 2022", search_variations: ["RRR", "RRR movie", "RRR 2022"]

- "avatar" → movie_research: {"full_title": "Avatar", "release_year": "2009", "alternate_names": ["Avatar: The Way of Water (2022 sequel)"], "key_details": "James Cameron sci-fi film"}, search_query: "Avatar 2009", search_variations: ["Avatar", "Avatar movie", "Avatar James Cameron"]

- "john wick" → movie_research: {"full_title": "John Wick", "release_year": "2014", "alternate_names": ["John Wick Chapter series"], "key_details": "Action thriller starring Keanu Reeves"}, search_query: "John Wick", search_variations: ["John Wick", "John Wick 2014", "John Wick movie"]

- "avengers endgame" → movie_research: {"full_title": "Avengers: Endgame", "release_year": "2019", "key_details": "Marvel superhero film, final Infinity Saga movie"}, search_query: "Avengers Endgame", search_variations: ["Avengers Endgame", "Avengers: Endgame", "Endgame"]

BE THOROUGH in movie research and provide multiple search variations!"""

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ]
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=400,
                temperature=0.3
            )
            
            response_text = response.choices[0].message.content
            
            # Try to parse JSON response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                intent = json.loads(json_match.group())
                logger.info(f"Analyzed intent: {intent}")
                return intent
            else:
                logger.warning("Could not parse LLM response as JSON")
                return self._fallback_intent_analysis(user_message)
                
        except Exception as e:
            logger.error(f"Error analyzing user intent: {str(e)}")
            return self._fallback_intent_analysis(user_message)
    
    def _fallback_intent_analysis(self, user_message: str) -> Dict[str, Any]:
        """Enhanced fallback method for intent analysis when LLM fails"""
        message_lower = user_message.lower()
        
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
        theme_keywords = ['superhero', 'space', 'war', 'family', 'crime', 'zombie', 'vampire', 'magic']
        
        if any(keyword in message_lower for keyword in movie_keywords + mood_keywords + theme_keywords):
            # Extract detailed movie preferences
            genres = [genre for genre in self.movie_genres if genre in message_lower]
            years = re.findall(r'\b(19|20)\d{2}\b', user_message)
            themes = [theme for theme in theme_keywords if theme in message_lower]
            
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
            if language != "any":
                search_parts.append(language)
            if genres:
                search_parts.extend(genres[:2])
            if themes:
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
                    "mood": mood,
                    "language": language,
                    "search_query": search_query
                },
                "user_intent_analysis": {
                    "what_they_want": "general movie recommendations",
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
    
    def _init_movie_agents(self):
        """Initialize movie search agents safely"""
        try:
            from agents.movierulz_agent import MovieRulzAgent
            self.movie_agents['movierulz'] = MovieRulzAgent()
            logger.info("MovieRulz agent initialized")
        except Exception as e:
            logger.error(f"Failed to initialize MovieRulz agent: {e}")
        
        try:
            from agents.moviezwap_agent import MoviezWapAgent
            self.movie_agents['moviezwap'] = MoviezWapAgent()
            logger.info("MoviezWap agent initialized")
        except Exception as e:
            logger.error(f"Failed to initialize MoviezWap agent: {e}")
        
        try:
            from agents.enhanced_downloadhub_agent import EnhancedDownloadHubAgent
            self.movie_agents['downloadhub'] = EnhancedDownloadHubAgent()
            logger.info("DownloadHub agent initialized")
        except Exception as e:
            logger.error(f"Failed to initialize DownloadHub agent: {e}")
        
        logger.info(f"Initialized {len(self.movie_agents)} movie search agents: {list(self.movie_agents.keys())}")
    
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
        
        # Search across all agents with timeout
        with ThreadPoolExecutor(max_workers=len(self.movie_agents)) as executor:
            future_to_agent = {}
            
            for agent_name, agent in self.movie_agents.items():
                # Use primary search query for each agent
                query = search_variations[0] if search_variations else search_query
                future = executor.submit(self._safe_search, agent, agent_name, query)
                future_to_agent[future] = (agent_name, query)
            
            # Collect results with timeout
            for future in as_completed(future_to_agent, timeout=60):  # 60 second total timeout
                agent_name, query = future_to_agent[future]
                try:
                    result = future.result(timeout=30)  # 30 second per agent timeout
                    if result and result.get('movies'):
                        all_results.extend(result['movies'])
                        search_summary["successful_sources"].append(f"{agent_name}")
                        logger.info(f"Found {len(result['movies'])} movies from {agent_name}")
                    
                    search_summary["sources_searched"].append(agent_name)
                    
                except Exception as e:
                    logger.error(f"Error searching {agent_name}: {str(e)}")
                    search_summary["sources_searched"].append(f"{agent_name} - FAILED")
        
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
        
        def relevance_score(movie):
            title = movie.get('title', '').lower()
            year = str(movie.get('year', ''))
            
            score = 0
            
            # Exact title match gets highest score
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
        
        response_data = {
            "intent": intent,
            "response_text": "",
            "movies": [],
            "search_performed": False,
            "session_id": session_id
        }
        
        # Check if it's a movie request that requires search
        if (intent.get("intent_type") == "movie_request" and 
            intent.get("movie_details", {}).get("search_query")):
            
            movie_details = intent.get("movie_details", {})
            search_query = movie_details.get("search_query", user_message.strip())
            search_variations = movie_details.get("search_variations", [search_query])
            
            logger.info(f"Performing movie search for: {search_query}")
            
            # Search for movies
            search_results = self.search_movies_with_sources(search_query, search_variations)
            response_data["movies"] = search_results.get("movies", [])
            response_data["search_summary"] = search_results.get("search_summary", {})
            response_data["search_performed"] = True
            
            # Generate contextual response
            response_data["response_text"] = self._generate_movie_response(user_message, intent, search_results)
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
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=150,
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
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=500,  # Increased from 200 to allow proper responses
                    temperature=0.7,
                    stream=False  # Explicitly disable streaming
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
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=350,
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
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=150,
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
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=200,
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