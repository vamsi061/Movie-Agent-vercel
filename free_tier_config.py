#!/usr/bin/env python3
"""
Free tier optimization configuration
Ultra-lightweight settings for 512MB memory limit platforms
"""

import os
import gc
import logging

# Configure for free tier deployment
FREE_TIER_CONFIG = {
    # Limit concurrent agents to reduce memory usage
    'MAX_CONCURRENT_AGENTS': 2,  # Only run 2 agents at once instead of all 6
    
    # Reduce result limits
    'MAX_MOVIES_PER_AGENT': 5,   # Max 5 movies per agent (instead of 10-20)
    'MAX_TOTAL_RESULTS': 10,     # Max 10 total results (instead of 50)
    
    # Aggressive garbage collection
    'FORCE_GC_AFTER_SEARCH': True,
    'FORCE_GC_THRESHOLD': 300,   # Force GC at 300MB (instead of 450MB)
    
    # Disable memory-intensive features
    'DISABLE_CACHING': True,
    'DISABLE_SESSION_PERSISTENCE': True,
    'DISABLE_DETAILED_LOGGING': True,
    
    # Prioritize lightweight agents
    'AGENT_PRIORITY': [
        'downloadhub',  # Lightweight, reliable
        'movierulz',    # Medium weight, good results
        'moviezwap',    # Skip if memory critical
        'movies4u',     # Skip (requires Selenium)
        'telegram',     # Skip if not configured
        'skysetx'       # Skip if not configured
    ]
}

def apply_free_tier_optimizations():
    """Apply optimizations for free tier deployment"""
    
    # Set environment variables for free tier
    os.environ.setdefault('MAX_MOVIES_PER_SEARCH', '10')
    os.environ.setdefault('DISABLE_SELENIUM', 'true')
    os.environ.setdefault('DISABLE_CACHING', 'true')
    os.environ.setdefault('FORCE_GC', 'true')
    
    # Configure garbage collection for aggressive cleanup
    gc.set_threshold(100, 5, 5)  # More aggressive than default (700, 10, 10)
    
    # Reduce logging level to save memory
    if FREE_TIER_CONFIG['DISABLE_DETAILED_LOGGING']:
        logging.getLogger().setLevel(logging.WARNING)
    
    print("✅ Free tier optimizations applied")

def get_enabled_agents_for_free_tier():
    """Get prioritized agents for free tier deployment"""
    return FREE_TIER_CONFIG['AGENT_PRIORITY'][:FREE_TIER_CONFIG['MAX_CONCURRENT_AGENTS']]

def should_limit_results():
    """Check if we should limit results for memory"""
    return True  # Always limit on free tier

if __name__ == '__main__':
    apply_free_tier_optimizations()
    print(f"Enabled agents for free tier: {get_enabled_agents_for_free_tier()}")
    print(f"Max results per agent: {FREE_TIER_CONFIG['MAX_MOVIES_PER_AGENT']}")
    print(f"Max total results: {FREE_TIER_CONFIG['MAX_TOTAL_RESULTS']}")