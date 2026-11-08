"""
Streamlit Cache System for ARGO Float Dashboard

This component provides advanced caching capabilities specifically
designed for Streamlit applications with performance optimization.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from typing import Dict, Any, Optional, Callable, List, Tuple, Union
from datetime import datetime, timedelta
import hashlib
import pickle
import logging
import time
from functools import wraps
import threading
import gc
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class CacheStats:
    """Cache statistics"""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    total_size_mb: float = 0.0
    entries: int = 0

class StreamlitCache:
    """Advanced caching system for Streamlit applications"""
    
    def __init__(self, 
                 max_size_mb: int = 200,
                 default_ttl_hours: int = 24,
                 cleanup_interval_minutes: int = 30):
        """
        Initialize the Streamlit cache system
        
        Args:
            max_size_mb: Maximum cache size in MB
            default_ttl_hours: Default TTL in hours
            cleanup_interval_minutes: Cleanup interval in minutes
        """
        self.max_size_mb = max_size_mb
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.default_ttl_hours = default_ttl_hours
        self.cleanup_interval_minutes = cleanup_interval_minutes
        
        # Cache statistics
        self.stats = CacheStats()
        
        # Last cleanup time
        self.last_cleanup = datetime.now()
        
        # Initialize session state cache
        self._initialize_cache()
    
    def _initialize_cache(self):
        """Initialize cache in session state"""
        try:
            if hasattr(st.session_state, '__contains__'):
                if 'streamlit_cache_data' not in st.session_state:
                    st.session_state.streamlit_cache_data = {}
                if 'streamlit_cache_metadata' not in st.session_state:
                    st.session_state.streamlit_cache_metadata = {}
                if 'streamlit_cache_stats' not in st.session_state:
                    st.session_state.streamlit_cache_stats = CacheStats()
        except (AttributeError, TypeError):
            # Session state not available (e.g., in tests)
            pass
    
    def _get_cache_key(self, func_name: str, args: tuple, kwargs: dict) -> str:
        """Generate cache key for function call"""
        try:
            # Create deterministic key from function signature
            key_parts = [func_name]
            
            # Add args
            for arg in args:
                if isinstance(arg, pd.DataFrame):
                    # Use DataFrame shape and column hash for DataFrames
                    key_parts.append(f"df_{arg.shape}_{hash(tuple(arg.columns))}")
                elif isinstance(arg, (list, tuple, dict)):
                    key_parts.append(str(hash(str(arg))))
                else:
                    key_parts.append(str(arg))
            
            # Add kwargs
            for k, v in sorted(kwargs.items()):
                if isinstance(v, pd.DataFrame):
                    key_parts.append(f"{k}_df_{v.shape}_{hash(tuple(v.columns))}")
                else:
                    key_parts.append(f"{k}_{v}")
            
            # Generate hash
            key_string = "_".join(key_parts)
            return hashlib.md5(key_string.encode()).hexdigest()
            
        except Exception as e:
            logger.warning(f"Error generating cache key: {e}")
            return f"{func_name}_{int(time.time())}"
    
    def _estimate_size(self, obj: Any) -> int:
        """Estimate object size in bytes"""
        try:
            if isinstance(obj, pd.DataFrame):
                return obj.memory_usage(deep=True).sum()
            elif isinstance(obj, go.Figure):
                # Estimate Plotly figure size
                return len(str(obj.to_json())) * 2  # Rough estimate
            elif isinstance(obj, (list, tuple)):
                return sum(self._estimate_size(item) for item in obj)
            elif isinstance(obj, dict):
                return sum(self._estimate_size(v) for v in obj.values())
            elif isinstance(obj, str):
                return len(obj.encode('utf-8'))
            elif isinstance(obj, (int, float, bool)):
                return 8
            else:
                # Use pickle size as fallback
                return len(pickle.dumps(obj))
        except Exception as e:
            logger.warning(f"Error estimating size: {e}")
            return 1024  # Default estimate
    
    def _cleanup_if_needed(self):
        """Cleanup cache if needed"""
        try:
            now = datetime.now()
            
            # Check if cleanup is needed
            if (now - self.last_cleanup).total_seconds() < self.cleanup_interval_minutes * 60:
                return
            
            self.last_cleanup = now
            
            if not hasattr(st.session_state, 'streamlit_cache_metadata'):
                return
            
            # Remove expired entries
            expired_keys = []
            for key, metadata in st.session_state.streamlit_cache_metadata.items():
                if (now - metadata['timestamp']).total_seconds() > metadata['ttl_seconds']:
                    expired_keys.append(key)
            
            for key in expired_keys:
                self._remove_cache_entry(key)
                self.stats.evictions += 1
            
            # Check size limit
            total_size = sum(meta['size_bytes'] for meta in st.session_state.streamlit_cache_metadata.values())
            
            if total_size > self.max_size_bytes:
                # Remove least recently used entries
                sorted_entries = sorted(
                    st.session_state.streamlit_cache_metadata.items(),
                    key=lambda x: (x[1]['access_count'], x[1]['timestamp'])
                )
                
                for key, metadata in sorted_entries:
                    if total_size <= self.max_size_bytes * 0.8:  # 80% threshold
                        break
                    
                    self._remove_cache_entry(key)
                    total_size -= metadata['size_bytes']
                    self.stats.evictions += 1
            
            # Update stats
            self.stats.entries = len(st.session_state.streamlit_cache_data)
            self.stats.total_size_mb = total_size / 1024 / 1024
            
        except Exception as e:
            logger.error(f"Error in cache cleanup: {e}")
    
    def _remove_cache_entry(self, key: str):
        """Remove cache entry"""
        try:
            if hasattr(st.session_state, 'streamlit_cache_data') and key in st.session_state.streamlit_cache_data:
                del st.session_state.streamlit_cache_data[key]
            
            if hasattr(st.session_state, 'streamlit_cache_metadata') and key in st.session_state.streamlit_cache_metadata:
                del st.session_state.streamlit_cache_metadata[key]
                
        except Exception as e:
            logger.warning(f"Error removing cache entry {key}: {e}")
    
    def cache_data(self, ttl_hours: Optional[int] = None):
        """
        Decorator for caching data operations
        
        Args:
            ttl_hours: Time to live in hours
        """
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Initialize cache if needed
                self._initialize_cache()
                
                # Generate cache key
                cache_key = self._get_cache_key(func.__name__, args, kwargs)
                
                # Check cache
                if (hasattr(st.session_state, 'streamlit_cache_data') and 
                    cache_key in st.session_state.streamlit_cache_data):
                    
                    metadata = st.session_state.streamlit_cache_metadata[cache_key]
                    
                    # Check if expired
                    if (datetime.now() - metadata['timestamp']).total_seconds() <= metadata['ttl_seconds']:
                        # Update access count
                        metadata['access_count'] += 1
                        self.stats.hits += 1
                        
                        logger.debug(f"Cache hit for {func.__name__}")
                        return st.session_state.streamlit_cache_data[cache_key]
                    else:
                        # Remove expired entry
                        self._remove_cache_entry(cache_key)
                
                # Cache miss - execute function
                self.stats.misses += 1
                result = func(*args, **kwargs)
                
                # Cache result
                try:
                    size_bytes = self._estimate_size(result)
                    ttl_seconds = (ttl_hours or self.default_ttl_hours) * 3600
                    
                    # Store in cache
                    if not hasattr(st.session_state, 'streamlit_cache_data'):
                        st.session_state.streamlit_cache_data = {}
                    if not hasattr(st.session_state, 'streamlit_cache_metadata'):
                        st.session_state.streamlit_cache_metadata = {}
                    
                    st.session_state.streamlit_cache_data[cache_key] = result
                    st.session_state.streamlit_cache_metadata[cache_key] = {
                        'timestamp': datetime.now(),
                        'ttl_seconds': ttl_seconds,
                        'size_bytes': size_bytes,
                        'access_count': 1,
                        'function_name': func.__name__
                    }
                    
                    logger.debug(f"Cached result for {func.__name__}: {size_bytes} bytes")
                    
                    # Cleanup if needed
                    self._cleanup_if_needed()
                    
                except Exception as e:
                    logger.warning(f"Error caching result for {func.__name__}: {e}")
                
                return result
            
            return wrapper
        return decorator
    
    def cache_resource(self, ttl_hours: Optional[int] = None):
        """
        Decorator for caching expensive resources (models, connections, etc.)
        
        Args:
            ttl_hours: Time to live in hours
        """
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Use Streamlit's built-in cache_resource for resources
                @st.cache_resource(ttl=timedelta(hours=ttl_hours or self.default_ttl_hours))
                def cached_func(*args, **kwargs):
                    return func(*args, **kwargs)
                
                return cached_func(*args, **kwargs)
            
            return wrapper
        return decorator
    
    def invalidate_cache(self, pattern: Optional[str] = None):
        """
        Invalidate cache entries
        
        Args:
            pattern: Pattern to match cache keys (None = clear all)
        """
        try:
            if not hasattr(st.session_state, 'streamlit_cache_data'):
                return
            
            if pattern is None:
                # Clear all cache
                st.session_state.streamlit_cache_data.clear()
                st.session_state.streamlit_cache_metadata.clear()
                logger.info("Cleared all cache entries")
            else:
                # Clear matching entries
                keys_to_remove = [
                    key for key in st.session_state.streamlit_cache_data.keys()
                    if pattern in key
                ]
                
                for key in keys_to_remove:
                    self._remove_cache_entry(key)
                
                logger.info(f"Cleared {len(keys_to_remove)} cache entries matching '{pattern}'")
            
            # Force garbage collection
            gc.collect()
            
        except Exception as e:
            logger.error(f"Error invalidating cache: {e}")
    
    def get_cache_info(self) -> Dict[str, Any]:
        """Get cache information"""
        try:
            if not hasattr(st.session_state, 'streamlit_cache_metadata'):
                return {
                    'entries': 0,
                    'total_size_mb': 0.0,
                    'hit_rate': 0.0,
                    'functions': {}
                }
            
            # Calculate current stats
            total_size = sum(meta['size_bytes'] for meta in st.session_state.streamlit_cache_metadata.values())
            entries = len(st.session_state.streamlit_cache_metadata)
            
            # Hit rate
            total_requests = self.stats.hits + self.stats.misses
            hit_rate = (self.stats.hits / total_requests * 100) if total_requests > 0 else 0.0
            
            # Function breakdown
            functions = {}
            for metadata in st.session_state.streamlit_cache_metadata.values():
                func_name = metadata['function_name']
                if func_name not in functions:
                    functions[func_name] = {'count': 0, 'size_mb': 0.0}
                
                functions[func_name]['count'] += 1
                functions[func_name]['size_mb'] += metadata['size_bytes'] / 1024 / 1024
            
            return {
                'entries': entries,
                'total_size_mb': total_size / 1024 / 1024,
                'max_size_mb': self.max_size_mb,
                'utilization_percent': (total_size / self.max_size_bytes) * 100,
                'hit_rate': hit_rate,
                'hits': self.stats.hits,
                'misses': self.stats.misses,
                'evictions': self.stats.evictions,
                'functions': functions
            }
            
        except Exception as e:
            logger.error(f"Error getting cache info: {e}")
            return {}
    
    def render_cache_controls(self):
        """Render cache control interface in Streamlit"""
        try:
            st.subheader("💾 Cache Management")
            
            # Get cache info
            cache_info = self.get_cache_info()
            
            # Cache statistics
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Cache Entries", cache_info.get('entries', 0))
            
            with col2:
                st.metric("Cache Size", f"{cache_info.get('total_size_mb', 0):.1f} MB")
            
            with col3:
                st.metric("Hit Rate", f"{cache_info.get('hit_rate', 0):.1f}%")
            
            with col4:
                utilization = cache_info.get('utilization_percent', 0)
                st.metric("Utilization", f"{utilization:.1f}%")
            
            # Cache controls
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("🗑️ Clear All Cache"):
                    self.invalidate_cache()
                    st.success("Cache cleared successfully!")
                    st.rerun()
            
            with col2:
                if st.button("🧹 Force Cleanup"):
                    self.last_cleanup = datetime.now() - timedelta(hours=1)  # Force cleanup
                    self._cleanup_if_needed()
                    st.success("Cache cleanup completed!")
                    st.rerun()
            
            with col3:
                if st.button("♻️ Garbage Collect"):
                    gc.collect()
                    st.success("Garbage collection completed!")
            
            # Function breakdown
            functions = cache_info.get('functions', {})
            if functions:
                st.subheader("📊 Cache by Function")
                
                func_data = []
                for func_name, stats in functions.items():
                    func_data.append({
                        'Function': func_name,
                        'Entries': stats['count'],
                        'Size (MB)': f"{stats['size_mb']:.2f}"
                    })
                
                if func_data:
                    func_df = pd.DataFrame(func_data)
                    st.dataframe(func_df, use_container_width=True)
            
            # Cache settings
            with st.expander("⚙️ Cache Settings"):
                new_max_size = st.number_input(
                    "Max Cache Size (MB)",
                    min_value=50,
                    max_value=1000,
                    value=self.max_size_mb,
                    step=50
                )
                
                new_ttl = st.number_input(
                    "Default TTL (hours)",
                    min_value=1,
                    max_value=168,  # 1 week
                    value=self.default_ttl_hours,
                    step=1
                )
                
                if st.button("Apply Settings"):
                    self.max_size_mb = new_max_size
                    self.max_size_bytes = new_max_size * 1024 * 1024
                    self.default_ttl_hours = new_ttl
                    st.success("Settings updated!")
        
        except Exception as e:
            logger.error(f"Error rendering cache controls: {e}")
            st.error("Error displaying cache controls")

# Global cache instance
_streamlit_cache = None

def get_streamlit_cache() -> StreamlitCache:
    """Get global Streamlit cache instance"""
    global _streamlit_cache
    
    if _streamlit_cache is None:
        _streamlit_cache = StreamlitCache()
    
    return _streamlit_cache

# Convenience decorators
def cache_data(ttl_hours: Optional[int] = None):
    """Convenience decorator for caching data"""
    cache = get_streamlit_cache()
    return cache.cache_data(ttl_hours)

def cache_resource(ttl_hours: Optional[int] = None):
    """Convenience decorator for caching resources"""
    cache = get_streamlit_cache()
    return cache.cache_resource(ttl_hours)

# Utility functions
def clear_cache(pattern: Optional[str] = None):
    """Clear cache entries"""
    cache = get_streamlit_cache()
    cache.invalidate_cache(pattern)

def get_cache_stats() -> Dict[str, Any]:
    """Get cache statistics"""
    cache = get_streamlit_cache()
    return cache.get_cache_info()