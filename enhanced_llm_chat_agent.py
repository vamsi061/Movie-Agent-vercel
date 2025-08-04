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
            system_prompt = """You are an intelligent assistant that analyzes user messages to understand their intent. 

Analyze the user's message and determine:
1. Intent type: "personal", "movie_request", "general_chat", or "greeting"
2. If movie-related, extract detailed movie preferences
3. If personal, identify the emotional context
4. Confidence level of your analysis

Respond in JSON format:
{
    "intent_type": "personal|movie_request|general_chat|greeting",
    "confidence": 0.9,
    "movie_details": {
        "movie_titles": ["specific movie names if mentioned"],
        "genres": ["action", "comedy", "drama"],
        "years": ["2023", "2020"],
        "actors": ["actor names"],
        "directors": ["director names"],
        "mood": "exciting/funny/romantic/scary/thrilling",
        "language": "hindi/english/tamil/telugu/any",
        "quality": "1080p/720p/480p/any",
        "search_query": "best search term for API"
    },
    "personal_context": {
        "topic": "greeting/mood/personal_question/recommendation/compliment",
        "emotional_tone": "happy/sad/excited/curious/neutral",
        "requires_empathy": true/false,
        "conversation_starter": true/false
    },
    "response_style": "conversational|informative|empathetic|professional|enthusiastic"
}

Examples:
- "Hello" → intent_type: "greeting", response_style: "conversational"
- "How are you?" → intent_type: "personal", personal_context: {"topic": "greeting", "requires_empathy": true}
- "I'm feeling sad today" → intent_type: "personal", personal_context: {"emotional_tone": "sad", "requires_empathy": true}
- "I want to watch The Matrix" → intent_type: "movie_request", movie_details: {"movie_titles": ["The Matrix"]}
- "Suggest some action movies from 2023" → intent_type: "movie_request", movie_details: {"genres": ["action"], "years": ["2023"]}
- "What's a good romantic comedy?" → intent_type: "movie_request", movie_details: {"genres": ["romance", "comedy"]}"""

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
        
        # Check for movie keywords
        movie_keywords = ['movie', 'film', 'watch', 'download', 'stream', 'cinema', 'bollywood', 'hollywood']
        if any(keyword in message_lower for keyword in movie_keywords):
            # Extract basic movie details
            genres = [genre for genre in self.movie_genres if genre in message_lower]
            years = re.findall(r'\b(19|20)\d{2}\b', user_message)
            
            return {
                "intent_type": "movie_request",
                "confidence": 0.6,
                "movie_details": {
                    "movie_titles": [],
                    "genres": genres,
                    "years": years,
                    "search_query": user_message
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
            
            system_prompt = f"""You are {self.agent_personality['name']}, a {self.agent_personality['role']}.
You are {', '.join(self.agent_personality['traits'])}.

IMPORTANT: DO NOT list individual movies in your response. The UI already displays movies in a structured format below your response.

The user is looking for movies. Here's what they want:
- Movie titles: {movie_details.get('movie_titles', [])}
- Genres: {movie_details.get('genres', [])}
- Years: {movie_details.get('years', [])}
- Mood: {movie_details.get('mood', 'any')}

{search_context}

Instead of listing movies, provide:
1. Encouraging commentary about the search results
2. General guidance about what was found
3. Suggestions for refining the search if needed
4. Enthusiasm and helpful advice

If movies were found:
- Comment on the variety and quality of results
- Mention the sources and formats available
- Give tips on choosing the best option

If no movies were found:
- Acknowledge their request sympathetically
- Suggest alternative search terms or similar movies
- Ask clarifying questions to help them better

Be conversational, knowledgeable, and excited about movies. Focus on guiding the user rather than listing movies."""

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
        """Extract the best search query for movie API"""
        movie_details = intent.get("movie_details", {})
        
        # If specific movie titles mentioned, use the first one
        if movie_details.get("movie_titles"):
            return movie_details["movie_titles"][0]
        
        # If search query provided, use it
        if movie_details.get("search_query"):
            return movie_details["search_query"]
        
        # Build query from genres and other details
        query_parts = []
        
        if movie_details.get("genres"):
            query_parts.extend(movie_details["genres"])
        
        if movie_details.get("years"):
            query_parts.extend(movie_details["years"])
        
        if movie_details.get("actors"):
            query_parts.extend(movie_details["actors"])
        
        return " ".join(query_parts) if query_parts else "popular movies"
    
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