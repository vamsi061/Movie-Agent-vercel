#!/usr/bin/env python3
"""
Memory optimization utilities for Movie Agent
Reduces memory usage to prevent exceeding limits on free hosting platforms
"""

import gc
import logging
import psutil
import os
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class MemoryOptimizer:
    """Utility class for memory optimization"""
    
    @staticmethod
    def get_memory_usage():
        """Get current memory usage in MB"""
        try:
            process = psutil.Process(os.getpid())
            memory_mb = process.memory_info().rss / 1024 / 1024
            return round(memory_mb, 2)
        except:
            return 0
    
    @staticmethod
    def force_garbage_collection():
        """Force garbage collection to free memory"""
        collected = gc.collect()
        logger.info(f"Garbage collection freed {collected} objects")
        return collected
    
    @staticmethod
    def limit_movie_results(movies: List[Dict[str, Any]], max_results: int = 10) -> List[Dict[str, Any]]:
        """Limit movie results to prevent memory overflow"""
        if len(movies) > max_results:
            logger.info(f"Limiting results from {len(movies)} to {max_results} to save memory")
            return movies[:max_results]
        return movies
    
    @staticmethod
    def cleanup_large_objects(*objects):
        """Cleanup large objects and force garbage collection"""
        for obj in objects:
            if obj is not None:
                del obj
        gc.collect()
    
    @staticmethod
    def log_memory_usage(operation: str = ""):
        """Log current memory usage"""
        memory_mb = MemoryOptimizer.get_memory_usage()
        logger.info(f"Memory usage {operation}: {memory_mb} MB")
        
        # Warning if memory usage is high
        if memory_mb > 400:  # 400MB warning for 512MB limit
            logger.warning(f"High memory usage detected: {memory_mb} MB")
            MemoryOptimizer.force_garbage_collection()
    
    @staticmethod
    def is_memory_critical() -> bool:
        """Check if memory usage is critical"""
        memory_mb = MemoryOptimizer.get_memory_usage()
        return memory_mb > 450  # Critical at 450MB for 512MB limit

# Memory optimization decorator
def memory_optimized(func):
    """Decorator to add memory optimization to functions"""
    def wrapper(*args, **kwargs):
        MemoryOptimizer.log_memory_usage(f"before {func.__name__}")
        
        try:
            result = func(*args, **kwargs)
            
            # Limit results if it's a movie search function
            if isinstance(result, dict) and 'movies' in result:
                result['movies'] = MemoryOptimizer.limit_movie_results(result['movies'])
            elif isinstance(result, list) and len(result) > 0 and isinstance(result[0], dict):
                result = MemoryOptimizer.limit_movie_results(result)
            
            return result
            
        finally:
            MemoryOptimizer.log_memory_usage(f"after {func.__name__}")
            
            # Force garbage collection if memory is high
            if MemoryOptimizer.is_memory_critical():
                MemoryOptimizer.force_garbage_collection()
    
    return wrapper

if __name__ == "__main__":
    # Test memory optimization
    print(f"Current memory usage: {MemoryOptimizer.get_memory_usage()} MB")
    MemoryOptimizer.force_garbage_collection()
    print(f"After garbage collection: {MemoryOptimizer.get_memory_usage()} MB")