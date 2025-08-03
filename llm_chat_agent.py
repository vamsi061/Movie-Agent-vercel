#!/usr/bin/env python3
"""
LLM Chat Agent - Intelligent movie search assistant using Together API
Provides movie suggestions and understands user queries
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

class LLMChatAgent:
    def __init__(self, api_key: str = None):
        """Initialize LLM Chat Agent with Together API"""
        self.api_key = api_key or os.getenv('TOGETHER_API_KEY')
        if not self.api_key:
            raise ValueError("Together API key is required. Set TOGETHER_API_KEY environment variable.")
        
        self.client = Together(api_key=self.api_key)
        self.model = "mistralai/Mixtral-8x7B-Instruct-v0.1"  # Serverless model that works
        
        # Movie genres and categories for better suggestions
        self.movie_genres = [
            "action", "adventure", "comedy", "drama", "horror", "thriller", 
            "sci-fi", "fantasy", "romance", "animation", "documentary", 
            "crime", "mystery", "war", "western", "musical", "biography"
        ]
        
        self.conversation_history = []
        
    def extract_movie_intent(self, user_message: str) -> Dict[str, Any]:
        """Extract movie search intent from user message using LLM"""
        try:
            system_prompt = """You are a movie search assistant. Analyze the user's message and extract:
1. Movie titles they want to search for
2. Genres they're interested in
3. Years/decades they prefer
4. Any specific actors or directors mentioned
5. Mood or type of movie they want

Respond in JSON format:
{
    "movie_titles": ["title1", "title2"],
    "genres": ["genre1", "genre2"],
    "years": ["2020", "2021"],
    "actors": ["actor1", "actor2"],
    "directors": ["director1"],
    "mood": "description of what they want",
    "search_query": "best search term to use",
    "confidence": 0.8
}

If no specific movie is mentioned, suggest popular movies based on their preferences."""

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ]
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=500,
                temperature=0.3
            )
            
            response_text = response.choices[0].message.content
            
            # Try to extract JSON from response
            try:
                # Find JSON in response
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    intent_data = json.loads(json_match.group())
                else:
                    # Fallback parsing
                    intent_data = self._fallback_intent_extraction(user_message)
            except json.JSONDecodeError:
                intent_data = self._fallback_intent_extraction(user_message)
            
            logger.info(f"Extracted intent: {intent_data}")
            return intent_data
            
        except Exception as e:
            logger.error(f"Error extracting movie intent: {str(e)}")
            return self._fallback_intent_extraction(user_message)
    
    def _fallback_intent_extraction(self, user_message: str) -> Dict[str, Any]:
        """Fallback method to extract basic intent without LLM"""
        intent = {
            "movie_titles": [],
            "genres": [],
            "years": [],
            "actors": [],
            "directors": [],
            "mood": "",
            "search_query": user_message,
            "confidence": 0.5
        }
        
        # Simple keyword extraction
        message_lower = user_message.lower()
        
        # Extract years
        years = re.findall(r'\b(19|20)\d{2}\b', user_message)
        intent["years"] = years
        
        # Extract genres
        for genre in self.movie_genres:
            if genre in message_lower:
                intent["genres"].append(genre)
        
        # If it looks like a movie title (quoted or capitalized)
        quoted_titles = re.findall(r'"([^"]+)"', user_message)
        if quoted_titles:
            intent["movie_titles"] = quoted_titles
            intent["search_query"] = quoted_titles[0]
        
        return intent
    
    def generate_movie_suggestions(self, user_message: str, search_results: List[Dict] = None) -> str:
        """Generate intelligent movie suggestions based on user query and search results"""
        try:
            # Build context from search results
            search_context = ""
            if search_results:
                search_context = f"\nAvailable movies found:\n"
                for i, movie in enumerate(search_results[:10]):  # Limit to 10 for context
                    search_context += f"- {movie.get('title', 'Unknown')} ({movie.get('year', 'Unknown')}) - {movie.get('quality', 'Unknown')} from {movie.get('source', 'Unknown')}\n"
            
            system_prompt = f"""You are a helpful movie assistant. The user is looking for movies to watch. 
Based on their message and the search results, provide helpful suggestions and guidance.

Be conversational, friendly, and helpful. If movies were found, highlight the best options.
If no movies were found, suggest alternative search terms or similar movies.

Keep responses concise but informative. Include movie details like year, quality when available.
{search_context}"""

            # Add to conversation history
            self.conversation_history.append({"role": "user", "content": user_message})
            
            messages = [
                {"role": "system", "content": system_prompt},
                *self.conversation_history[-6:]  # Keep last 6 messages for context
            ]
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=300,
                temperature=0.7
            )
            
            assistant_response = response.choices[0].message.content
            
            # Add assistant response to history
            self.conversation_history.append({"role": "assistant", "content": assistant_response})
            
            return assistant_response
            
        except Exception as e:
            logger.error(f"Error generating suggestions: {str(e)}")
            return self._fallback_suggestion(user_message, search_results)
    
    def _fallback_suggestion(self, user_message: str, search_results: List[Dict] = None) -> str:
        """Fallback suggestion when LLM fails"""
        if search_results:
            if len(search_results) > 0:
                return f"I found {len(search_results)} movies for you! Here are the top results:\n\n" + \
                       "\n".join([f"• {movie.get('title', 'Unknown')} ({movie.get('year', 'Unknown')}) - {movie.get('quality', 'Unknown')}" 
                                 for movie in search_results[:5]])
            else:
                return "I couldn't find any movies matching your search. Try different keywords or check the spelling!"
        else:
            return "I'm here to help you find movies! What would you like to watch today?"
    
    def generate_search_suggestions(self, partial_query: str) -> List[str]:
        """Generate search suggestions for autocomplete"""
        try:
            system_prompt = """Generate 5 movie search suggestions based on the partial query. 
Return only movie titles or search terms, one per line. Be creative but relevant.
Focus on popular movies, recent releases, and classic films."""
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Suggest movies for: {partial_query}"}
            ]
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=150,
                temperature=0.8
            )
            
            suggestions = response.choices[0].message.content.strip().split('\n')
            return [s.strip('- ').strip() for s in suggestions if s.strip()][:5]
            
        except Exception as e:
            logger.error(f"Error generating search suggestions: {str(e)}")
            return self._fallback_search_suggestions(partial_query)
    
    def _fallback_search_suggestions(self, partial_query: str) -> List[str]:
        """Fallback search suggestions"""
        popular_movies = [
            "Avengers Endgame", "Top Gun Maverick", "Spider-Man No Way Home",
            "The Batman", "Black Panther", "Inception", "Interstellar",
            "John Wick", "Fast and Furious", "Mission Impossible"
        ]
        
        query_lower = partial_query.lower()
        suggestions = [movie for movie in popular_movies if query_lower in movie.lower()]
        
        if not suggestions:
            suggestions = popular_movies[:5]
        
        return suggestions[:5]
    
    def analyze_user_mood(self, message: str) -> Dict[str, Any]:
        """Analyze user's mood and preferences to suggest appropriate movies"""
        try:
            system_prompt = """Analyze the user's message to understand their mood and movie preferences.
Return JSON with:
{
    "mood": "happy/sad/excited/bored/romantic/adventurous/etc",
    "energy_level": "high/medium/low",
    "preferred_genres": ["genre1", "genre2"],
    "movie_length_preference": "short/medium/long/any",
    "content_rating": "family/teen/adult/any"
}"""
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message}
            ]
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=200,
                temperature=0.3
            )
            
            response_text = response.choices[0].message.content
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            
            if json_match:
                return json.loads(json_match.group())
            else:
                return {"mood": "neutral", "energy_level": "medium", "preferred_genres": ["action"]}
                
        except Exception as e:
            logger.error(f"Error analyzing mood: {str(e)}")
            return {"mood": "neutral", "energy_level": "medium", "preferred_genres": ["action"]}
    
    def clear_conversation(self):
        """Clear conversation history"""
        self.conversation_history = []
        logger.info("Conversation history cleared")

def main():
    """Test the LLM Chat Agent"""
    # Test with dummy API key (replace with real key)
    try:
        agent = LLMChatAgent("dummy_key")
        
        # Test intent extraction
        test_message = "I want to watch a good action movie from 2023"
        intent = agent.extract_movie_intent(test_message)
        print(f"Intent: {intent}")
        
        # Test suggestions
        suggestions = agent.generate_movie_suggestions(test_message)
        print(f"Suggestions: {suggestions}")
        
    except Exception as e:
        print(f"Test failed (expected with dummy key): {e}")

if __name__ == "__main__":
    main()