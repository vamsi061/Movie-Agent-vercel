#!/usr/bin/env python3
"""
Chat Integration - Simple wrapper for web interface integration
"""

from llm_chat_agent import EnhancedLLMChatAgent
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global agent instance
_chat_agent = None

def get_chat_agent():
    """Get or create the chat agent instance"""
    global _chat_agent
    if _chat_agent is None:
        try:
            _chat_agent = EnhancedLLMChatAgent()
            logger.info("Chat agent initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize chat agent: {e}")
            _chat_agent = None
    return _chat_agent

def process_chat_message(user_message: str) -> dict:
    """
    Main function for web interface integration
    
    Args:
        user_message (str): User's message
        
    Returns:
        dict: {
            'response': str,           # AI response text
            'movies': list,            # List of movie results
            'search_performed': bool,  # Whether movie search was performed
            'intent_type': str,        # Type of user intent
            'success': bool            # Whether processing was successful
        }
    """
    try:
        agent = get_chat_agent()
        if not agent:
            return {
                'response': "Sorry, I'm having trouble initializing. Please try again.",
                'movies': [],
                'search_performed': False,
                'intent_type': 'error',
                'success': False
            }
        
        # Process the user message
        result = agent.process_movie_request(user_message)
        
        return {
            'response': result.get('response_text', 'Sorry, I could not process your request.'),
            'movies': result.get('movies', []),
            'search_performed': result.get('search_performed', False),
            'intent_type': result.get('intent', {}).get('intent_type', 'unknown'),
            'success': True
        }
        
    except Exception as e:
        logger.error(f"Error processing chat message: {e}")
        return {
            'response': "Sorry, I encountered an error processing your request. Please try again.",
            'movies': [],
            'search_performed': False,
            'intent_type': 'error',
            'success': False
        }

# For backward compatibility with existing web interface
def chat_with_llm(user_message: str) -> str:
    """
    Simple function that returns just the response text
    For backward compatibility with existing implementations
    """
    result = process_chat_message(user_message)
    return result['response']

if __name__ == "__main__":
    # Test the integration
    test_messages = [
        "hello",
        "rrr movie",
        "action movies",
        "how are you"
    ]
    
    print("🎬 Testing Chat Integration")
    print("=" * 50)
    
    for msg in test_messages:
        print(f"\nUser: {msg}")
        result = process_chat_message(msg)
        print(f"Response: {result['response']}")
        print(f"Intent: {result['intent_type']}")
        print(f"Search: {result['search_performed']}")
        if result['movies']:
            print(f"Movies found: {len(result['movies'])}")
    
    print("\n" + "=" * 50)
    print("✅ Chat integration test completed!")