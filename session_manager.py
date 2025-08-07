"""
Session Manager for Movie Agent
Handles user sessions with memory and automatic expiration
"""

import time
import uuid
import json
import threading
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class SessionManager:
    def __init__(self, session_timeout_minutes: int = 15):
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.session_timeout = session_timeout_minutes * 60  # Convert to seconds
        self.cleanup_thread = None
        self.start_cleanup_thread()
    
    def start_cleanup_thread(self):
        """Start background thread to clean up expired sessions"""
        def cleanup_expired_sessions():
            while True:
                try:
                    current_time = time.time()
                    expired_sessions = []
                    
                    for session_id, session_data in self.sessions.items():
                        if current_time - session_data['last_activity'] > self.session_timeout:
                            expired_sessions.append(session_id)
                    
                    for session_id in expired_sessions:
                        del self.sessions[session_id]
                        logger.info(f"Expired session: {session_id}")
                    
                    time.sleep(60)  # Check every minute
                except Exception as e:
                    logger.error(f"Error in session cleanup: {e}")
                    time.sleep(60)
        
        self.cleanup_thread = threading.Thread(target=cleanup_expired_sessions, daemon=True)
        self.cleanup_thread.start()
    
    def create_session(self) -> str:
        """Create a new session and return session ID"""
        session_id = str(uuid.uuid4())
        current_time = time.time()
        
        self.sessions[session_id] = {
            'created_at': current_time,
            'last_activity': current_time,
            'conversation_history': [],
            'user_preferences': {},
            'search_history': [],
            'movie_context': {},
            'follow_up_context': None
        }
        
        logger.info(f"Created new session: {session_id}")
        return session_id
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data if it exists and is not expired"""
        if session_id not in self.sessions:
            return None
        
        session_data = self.sessions[session_id]
        current_time = time.time()
        
        # Check if session is expired
        if current_time - session_data['last_activity'] > self.session_timeout:
            del self.sessions[session_id]
            logger.info(f"Session expired and removed: {session_id}")
            return None
        
        # Update last activity
        session_data['last_activity'] = current_time
        return session_data
    
    def add_conversation(self, session_id: str, user_message: str, ai_response: str, movie_results: List[Dict] = None):
        """Add conversation to session history"""
        session_data = self.get_session(session_id)
        if not session_data:
            return False
        
        conversation_entry = {
            'timestamp': time.time(),
            'user_message': user_message,
            'ai_response': ai_response,
            'movie_results': movie_results or [],
            'movie_count': len(movie_results) if movie_results else 0
        }
        
        session_data['conversation_history'].append(conversation_entry)
        
        # Keep only last 10 conversations to manage memory
        if len(session_data['conversation_history']) > 10:
            session_data['conversation_history'] = session_data['conversation_history'][-10:]
        
        # Update search history
        if movie_results:
            search_entry = {
                'query': user_message,
                'results_count': len(movie_results),
                'timestamp': time.time()
            }
            session_data['search_history'].append(search_entry)
            
            # Keep only last 5 searches
            if len(session_data['search_history']) > 5:
                session_data['search_history'] = session_data['search_history'][-5:]
        
        return True
    
    def update_user_preferences(self, session_id: str, preferences: Dict[str, Any]):
        """Update user preferences based on conversation"""
        session_data = self.get_session(session_id)
        if not session_data:
            return False
        
        # Merge preferences
        session_data['user_preferences'].update(preferences)
        return True
    
    def set_movie_context(self, session_id: str, movie_info: Dict[str, Any]):
        """Set current movie context for follow-up questions"""
        session_data = self.get_session(session_id)
        if not session_data:
            return False
        
        session_data['movie_context'] = movie_info
        session_data['follow_up_context'] = {
            'type': 'movie_discussion',
            'movie_title': movie_info.get('title', ''),
            'timestamp': time.time()
        }
        return True
    
    def get_conversation_context(self, session_id: str) -> str:
        """Get formatted conversation context for LLM"""
        session_data = self.get_session(session_id)
        if not session_data or not session_data['conversation_history']:
            return ""
        
        context_parts = []
        
        # Add recent conversation history
        recent_conversations = session_data['conversation_history'][-3:]  # Last 3 conversations
        if recent_conversations:
            context_parts.append("RECENT CONVERSATION HISTORY:")
            for i, conv in enumerate(recent_conversations, 1):
                context_parts.append(f"{i}. User: {conv['user_message']}")
                context_parts.append(f"   AI: {conv['ai_response'][:100]}...")
                if conv['movie_results']:
                    context_parts.append(f"   Found: {conv['movie_count']} movies")
        
        # Add user preferences
        if session_data['user_preferences']:
            context_parts.append("\nUSER PREFERENCES:")
            for key, value in session_data['user_preferences'].items():
                context_parts.append(f"- {key}: {value}")
        
        # Add current movie context
        if session_data['movie_context']:
            context_parts.append(f"\nCURRENT MOVIE CONTEXT:")
            context_parts.append(f"- Discussing: {session_data['movie_context'].get('title', 'Unknown')}")
        
        # Add follow-up context
        if session_data['follow_up_context']:
            follow_up = session_data['follow_up_context']
            if time.time() - follow_up['timestamp'] < 300:  # 5 minutes
                context_parts.append(f"\nFOLLOW-UP CONTEXT:")
                context_parts.append(f"- Type: {follow_up['type']}")
                if follow_up.get('movie_title'):
                    context_parts.append(f"- Movie: {follow_up['movie_title']}")
        
        return "\n".join(context_parts)
    
    def get_session_stats(self, session_id: str) -> Dict[str, Any]:
        """Get session statistics"""
        session_data = self.get_session(session_id)
        if not session_data:
            return {}
        
        current_time = time.time()
        session_age = current_time - session_data['created_at']
        time_remaining = self.session_timeout - (current_time - session_data['last_activity'])
        
        return {
            'session_id': session_id,
            'created_at': datetime.fromtimestamp(session_data['created_at']).isoformat(),
            'session_age_minutes': round(session_age / 60, 1),
            'time_remaining_minutes': round(max(0, time_remaining) / 60, 1),
            'conversation_count': len(session_data['conversation_history']),
            'search_count': len(session_data['search_history']),
            'has_preferences': bool(session_data['user_preferences']),
            'has_movie_context': bool(session_data['movie_context'])
        }
    
    def get_all_sessions_stats(self) -> Dict[str, Any]:
        """Get statistics for all active sessions"""
        return {
            'total_active_sessions': len(self.sessions),
            'session_timeout_minutes': self.session_timeout / 60,
            'sessions': [self.get_session_stats(sid) for sid in self.sessions.keys()]
        }

# Global session manager instance
session_manager = SessionManager(session_timeout_minutes=15)