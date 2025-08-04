#!/usr/bin/env python3
"""
Enhanced LLM Chat Agent - Intelligent assistant that understands context
Handles personal questions personally and movie requests with proper API integration
"""

import os
import json
import re
import logging
from typing import Dict, List, Optional, Any
from together import Together
import requests

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EnhancedLLMChatAgent:
    def __init__(self, api_key: str = None):
        """Initialize Enhanced LLM Chat Agent with Together API"""
        self.api_key = api_key or os.getenv('TOGETHER_API_KEY')
        if not self.api_key:
            raise ValueError("Together API key is required. Set TOGETHER_API_KEY environment variable.")
        
        self.client = Together(api_key=self.api_key)
        self.model = "mistralai/Mixtral-8x7B-Instruct-v0.1"
        
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
            "role": "helpful movie recommendation assistant",
            "traits": ["friendly", "knowledgeable", "empathetic", "enthusiastic about movies"]
        }
        
    def analyze_user_intent(self, user_message: str) -> Dict[str, Any]:
        """Analyze user intent to determine response type"""
        try:
            system_prompt = """You are an expert movie recommendation assistant that analyzes user messages to understand their exact movie preferences.

ANALYZE THE USER'S MESSAGE CAREFULLY and extract:
1. Intent type: "personal", "movie_request", "general_chat", or "greeting"
2. Detailed movie preferences (be very specific and thorough)
3. The best search terms for finding movies

Respond in JSON format:
{
    "intent_type": "personal|movie_request|general_chat|greeting",
    "confidence": 0.9,
    "movie_details": {
        "movie_titles": ["exact movie names if mentioned"],
        "genres": ["specific genres mentioned or implied"],
        "years": ["specific years mentioned"],
        "actors": ["actor names mentioned"],
        "directors": ["director names mentioned"],
        "mood": "user's emotional preference",
        "language": "preferred language",
        "quality": "quality preference",
        "themes": ["themes like superhero, space, war, family, etc"],
        "search_query": "BEST search term for movie APIs"
    },
    "user_intent_analysis": {
        "what_they_want": "clear description of what user is looking for",
        "specific_preferences": "any specific requirements mentioned",
        "context": "context or reason for the request"
    }
}

EXAMPLES OF BETTER ANALYSIS:
- "I want something exciting and action-packed" → genres: ["action"], mood: "exciting", themes: ["adventure"], search_query: "action movies"
- "Show me some superhero movies" → themes: ["superhero"], genres: ["action", "adventure"], search_query: "superhero movies"
- "I'm in the mood for a good laugh" → genres: ["comedy"], mood: "funny", search_query: "comedy movies"
- "Any good sci-fi from 2023?" → genres: ["sci-fi"], years: ["2023"], search_query: "sci-fi 2023"
- "I want to watch Avengers" → movie_titles: ["Avengers"], themes: ["superhero"], search_query: "Avengers"
- "Something like John Wick" → movie_titles: ["John Wick"], genres: ["action"], themes: ["crime"], search_query: "John Wick"
- "Hindi action movies" → language: "hindi", genres: ["action"], search_query: "hindi action movies"
- "Latest Hollywood blockbusters" → language: "english", themes: ["blockbuster"], search_query: "hollywood movies"

BE SMART about extracting preferences from natural language!"""

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
        """Fallback method for intent analysis when LLM fails"""
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
        
        # Enhanced movie keyword detection
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
                "response_style": "informative"
            }
        
        # Default to general chat
        return {
            "intent_type": "general_chat",
            "confidence": 0.5,
            "response_style": "conversational"
        }
    
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
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=200,
                temperature=0.7
            )
            
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
            if search_results:
                search_context = f"\nI found these movies for you:\n"
                for i, movie in enumerate(search_results[:8]):  # Limit to 8 for context
                    search_context += f"- {movie.get('title', 'Unknown')} ({movie.get('year', 'Unknown')}) - {movie.get('quality', 'Unknown')} from {movie.get('source', 'Unknown')}\n"
            else:
                search_context = "\nI couldn't find specific movies matching your request, but I can still help with recommendations."
            
            # Get user intent analysis for better context
            user_analysis = intent.get("user_intent_analysis", {})
            what_they_want = user_analysis.get("what_they_want", "movies")
            
            system_prompt = f"""You are {self.agent_personality['name']}, a {self.agent_personality['role']}.
You are {', '.join(self.agent_personality['traits'])}.

IMPORTANT: DO NOT list individual movies in your response. The UI already displays movies in a structured format below your response.

UNDERSTAND THE USER'S REQUEST:
The user wants: {what_they_want}
Their preferences:
- Movie titles: {movie_details.get('movie_titles', [])}
- Genres: {movie_details.get('genres', [])}
- Themes: {movie_details.get('themes', [])}
- Years: {movie_details.get('years', [])}
- Mood: {movie_details.get('mood', 'any')}
- Language: {movie_details.get('language', 'any')}
- Specific preferences: {user_analysis.get('specific_preferences', 'none mentioned')}

SEARCH RESULTS CONTEXT:
{search_context}

RESPOND INTELLIGENTLY based on what they actually wanted:

If movies were found:
- Acknowledge their specific request (e.g., "Great! I found some {movie_details.get('mood', 'great')} {' '.join(movie_details.get('genres', ['movies']))} for you!")
- Comment on how well the results match their preferences
- Mention the variety of sources, qualities, and years available
- Give personalized advice based on their mood/preferences
- Suggest what to look for when choosing

If no movies were found:
- Acknowledge their specific request sympathetically
- Explain why the search might not have found results
- Suggest alternative search terms that might work better
- Ask clarifying questions to help narrow down their preferences
- Offer to search for similar or related movies

Be enthusiastic, specific to their request, and genuinely helpful. Show that you understand exactly what they're looking for."""

            # Add to conversation history
            self.conversation_history.append({"role": "user", "content": user_message})
            
            messages = [
                {"role": "system", "content": system_prompt},
                *self.conversation_history[-6:]  # Keep last 6 messages for context
            ]
            
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
        
        # Priority 1: Specific movie titles (highest priority)
        if movie_details.get("movie_titles"):
            return movie_details["movie_titles"][0]
        
        # Priority 2: Pre-built search query from LLM analysis
        if movie_details.get("search_query"):
            return movie_details["search_query"]
        
        # Priority 3: Build intelligent query from components
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