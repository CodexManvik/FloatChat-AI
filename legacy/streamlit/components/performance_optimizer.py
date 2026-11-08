"""
Performance Optimizer Component for ARGO Float Dashboard

This component provides performance optimization features including
caching, lazy loading, data sampling, and visualization optimization.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from typing import Dict, Any, Optional, Callable, List, Tuple, Union
from datetime import datetime, timedelta
import hashlib
import pickle
import logging
import time
from functools import wraps, lru_cache
from dataclasses import dataclass
import threading
import asyncio
from concurrent.futures import ThreadPoolExecutor
import gc

logger = logging.getLogger(__name__)

@dataclass
class CacheEntry:
    """Structure for cache entries"""
    data: Any
    timestamp: datetime
    access_count: int
    size_bytes: int
    ttl_seconds: int

@dataclass
class PerformanceMetrics:
    """Structure for performance metrics"""
    operation_name: str
    execution_time: float
    data_size: int
    cache_hit: bool
    memory_usage: float
    timestamp: datetime

class PerformanceOptimizer:
    """Comprehensive performance optimization system"""
    
    def __init__(self, 
                 cache_size_mb: int = 100,
                 default_ttl_seconds: int = 3600,
                 enable_metrics: bool = True):
        """
        Initialize the performance optimizer
        
        Args:
            cache_size_mb: Maximum cache size in MB
            default_ttl_seconds: Default TTL for cache entries
            enable_metrics: Whether to collect performance metrics
        """
        self.cache_size_mb = cache_size_mb
        self.cache_size_bytes = cache_size_mb * 1024 * 1024
        self.default_ttl_seconds = default_ttl_seconds
        self.enable_metrics = enable_metrics
        
        # Cache storage
        self.cache = {}
        self.cache_metadata = {}
        self.current_cache_size = 0
        
        # Performance metrics
        self.metrics = []
        self.max_metrics = 1000
        
        # Lazy loading state
        self.lazy_load_registry = {}
        
        # Thread pool for async operations
        self.thread_pool = ThreadPoolExecutor(max_workers=4)
        
        # Initialize session state
        self._initialize_session_state()
    
    def _initialize_session_state(self):
        """Initialize session state for performance optimizer"""
        try:
            if hasattr(st.session_state, '__contains__') and 'performance_optimizer_initialized' not in st.session_state:
                st.session_state.performance_optimizer_initialized = True
                st.session_state.performance_cache = {}
                st.session_state.lazy_load_state = {}
                st.session_state.performance_metrics = []
        except (AttributeError, TypeError):
            # Session state not available (e.g., in tests)
            pass
    
    def _generate_cache_key(self, func_name: str, args: tuple, kwargs: dict) -> str:
        """Generate a unique cache key for function calls"""
        try:
            # Create a string representation of the function call
            key_data = {
                'func': func_name,
                'args': str(args),
                'kwargs': str(sorted(kwargs.items()))
            }
            
            # Generate hash
            key_string = str(key_data)
            return hashlib.md5(key_string.encode()).hexdigest()
            
        except Exception as e:
            logger.warning(f"Error generating cache key: {e}")
            return f"{func_name}_{int(time.time())}"
    
    def _get_data_size(self, data: Any) -> int:
        """Estimate the size of data in bytes"""
        try:
            if isinstance(data, pd.DataFrame):
                return data.memory_usage(deep=True).sum()
            elif isinstance(data, (list, tuple)):
                return sum(self._get_data_size(item) for item in data)
            elif isinstance(data, dict):
                return sum(self._get_data_size(v) for v in data.values())
            elif isinstance(data, str):
                return len(data.encode('utf-8'))
            elif isinstance(data, (int, float)):
                return 8  # Approximate size
            else:
                # Use pickle to estimate size
                return len(pickle.dumps(data))
        except Exception as e:
            logger.warning(f"Error estimating data size: {e}")
            return 1024  # Default estimate
    
    def _cleanup_cache(self):
        """Clean up expired cache entries and manage cache size"""
        try:
            current_time = datetime.now()
            expired_keys = []
            
            # Find expired entries
            for key, metadata in self.cache_metadata.items():
                if (current_time - metadata.timestamp).total_seconds() > metadata.ttl_seconds:
                    expired_keys.append(key)
            
            # Remove expired entries
            for key in expired_keys:
                self._remove_cache_entry(key)
            
            # If still over size limit, remove least recently used entries
            if self.current_cache_size > self.cache_size_bytes:
                # Sort by access count and timestamp
                sorted_entries = sorted(
                    self.cache_metadata.items(),
                    key=lambda x: (x[1].access_count, x[1].timestamp)
                )
                
                # Remove entries until under size limit
                for key, metadata in sorted_entries:
                    if self.current_cache_size <= self.cache_size_bytes * 0.8:  # 80% threshold
                        break
                    self._remove_cache_entry(key)
            
        except Exception as e:
            logger.error(f"Error cleaning up cache: {e}")
    
    def _remove_cache_entry(self, key: str):
        """Remove a cache entry"""
        try:
            if key in self.cache:
                metadata = self.cache_metadata.get(key)
                if metadata:
                    self.current_cache_size -= metadata.size_bytes
                
                del self.cache[key]
                if key in self.cache_metadata:
                    del self.cache_metadata[key]
                    
        except Exception as e:
            logger.warning(f"Error removing cache entry {key}: {e}")
    
    def _record_metric(self, 
                      operation_name: str,
                      execution_time: float,
                      data_size: int,
                      cache_hit: bool):
        """Record performance metric"""
        try:
            if not self.enable_metrics:
                return
            
            metric = PerformanceMetrics(
                operation_name=operation_name,
                execution_time=execution_time,
                data_size=data_size,
                cache_hit=cache_hit,
                memory_usage=self._get_memory_usage(),
                timestamp=datetime.now()
            )
            
            self.metrics.append(metric)
            
            # Keep only recent metrics
            if len(self.metrics) > self.max_metrics:
                self.metrics = self.metrics[-self.max_metrics:]
                
        except Exception as e:
            logger.warning(f"Error recording metric: {e}")
    
    def _get_memory_usage(self) -> float:
        """Get current memory usage in MB"""
        try:
            import psutil
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024
        except ImportError:
            return 0.0
        except Exception as e:
            logger.warning(f"Error getting memory usage: {e}")
            return 0.0
    
    def cache_function(self, 
                      ttl_seconds: Optional[int] = None,
                      max_size_mb: Optional[int] = None):
        """
        Decorator for caching function results
        
        Args:
            ttl_seconds: Time to live for cache entry
            max_size_mb: Maximum size for this cache entry
            
        Returns:
            Decorator function
        """
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Generate cache key
                cache_key = self._generate_cache_key(func.__name__, args, kwargs)
                
                start_time = time.time()
                
                # Check cache
                if cache_key in self.cache:
                    metadata = self.cache_metadata[cache_key]
                    
                    # Check if expired
                    if (datetime.now() - metadata.timestamp).total_seconds() <= metadata.ttl_seconds:
                        # Update access count
                        metadata.access_count += 1
                        
                        execution_time = time.time() - start_time
                        self._record_metric(func.__name__, execution_time, metadata.size_bytes, True)
                        
                        logger.debug(f"Cache hit for {func.__name__}")
                        return self.cache[cache_key]
                    else:
                        # Remove expired entry
                        self._remove_cache_entry(cache_key)
                
                # Execute function
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time
                
                # Cache result
                try:
                    data_size = self._get_data_size(result)
                    
                    # Check size limits
                    if max_size_mb and data_size > max_size_mb * 1024 * 1024:
                        logger.warning(f"Result too large to cache: {data_size} bytes")
                    else:
                        # Clean up cache if needed
                        self._cleanup_cache()
                        
                        # Add to cache
                        ttl = ttl_seconds or self.default_ttl_seconds
                        metadata = CacheEntry(
                            data=result,
                            timestamp=datetime.now(),
                            access_count=1,
                            size_bytes=data_size,
                            ttl_seconds=ttl
                        )
                        
                        self.cache[cache_key] = result
                        self.cache_metadata[cache_key] = metadata
                        self.current_cache_size += data_size
                        
                        logger.debug(f"Cached result for {func.__name__}: {data_size} bytes")
                
                except Exception as e:
                    logger.warning(f"Error caching result for {func.__name__}: {e}")
                
                self._record_metric(func.__name__, execution_time, data_size, False)
                return result
            
            return wrapper
        return decorator
    
    def lazy_load_data(self, 
                      data_loader: Callable,
                      loader_key: str,
                      placeholder_text: str = "Loading data...",
                      *args, **kwargs) -> Any:
        """
        Lazy load data with caching and progress indication
        
        Args:
            data_loader: Function to load data
            loader_key: Unique key for this loader
            placeholder_text: Text to show while loading
            *args, **kwargs: Arguments for data loader
            
        Returns:
            Loaded data
        """
        try:
            # Check if already loaded
            if loader_key in self.lazy_load_registry:
                return self.lazy_load_registry[loader_key]
            
            # Show loading indicator
            with st.spinner(placeholder_text):
                start_time = time.time()
                
                # Load data
                data = data_loader(*args, **kwargs)
                
                # Cache the result
                self.lazy_load_registry[loader_key] = data
                
                execution_time = time.time() - start_time
                data_size = self._get_data_size(data)
                
                self._record_metric(f"lazy_load_{loader_key}", execution_time, data_size, False)
                
                logger.info(f"Lazy loaded {loader_key}: {data_size} bytes in {execution_time:.2f}s")
                
                return data
                
        except Exception as e:
            logger.error(f"Error in lazy loading {loader_key}: {e}")
            st.error(f"Error loading {loader_key}: {str(e)}")
            return None
    
    def sample_large_dataset(self, 
                           data: pd.DataFrame,
                           max_points: int = 10000,
                           sampling_strategy: str = "random",
                           preserve_extremes: bool = True) -> pd.DataFrame:
        """
        Sample large datasets for performance while maintaining accuracy
        
        Args:
            data: DataFrame to sample
            max_points: Maximum number of points to keep
            sampling_strategy: Strategy for sampling ('random', 'systematic', 'stratified')
            preserve_extremes: Whether to preserve extreme values
            
        Returns:
            Sampled DataFrame
        """
        try:
            if len(data) <= max_points:
                return data
            
            logger.info(f"Sampling dataset from {len(data)} to {max_points} points")
            
            if sampling_strategy == "random":
                sampled = data.sample(n=max_points, random_state=42)
                
            elif sampling_strategy == "systematic":
                # Systematic sampling
                step = len(data) // max_points
                indices = range(0, len(data), step)[:max_points]
                sampled = data.iloc[indices]
                
            elif sampling_strategy == "stratified":
                # Stratified sampling based on depth if available
                if 'depth' in data.columns:
                    # Create depth bins
                    data['depth_bin'] = pd.cut(data['depth'], bins=10, labels=False)
                    points_per_bin = max_points // 10
                    
                    sampled_parts = []
                    for bin_val in range(10):
                        bin_data = data[data['depth_bin'] == bin_val]
                        if len(bin_data) > 0:
                            n_sample = min(len(bin_data), points_per_bin)
                            sampled_parts.append(bin_data.sample(n=n_sample, random_state=42))
                    
                    sampled = pd.concat(sampled_parts, ignore_index=True)
                    sampled = sampled.drop('depth_bin', axis=1)
                else:
                    # Fall back to random sampling
                    sampled = data.sample(n=max_points, random_state=42)
            
            else:
                raise ValueError(f"Unknown sampling strategy: {sampling_strategy}")
            
            # Preserve extreme values if requested
            if preserve_extremes and len(data) > max_points:
                numeric_columns = data.select_dtypes(include=[np.number]).columns
                
                for col in numeric_columns:
                    if col in data.columns:
                        # Add min and max values
                        min_idx = data[col].idxmin()
                        max_idx = data[col].idxmax()
                        
                        if min_idx not in sampled.index:
                            sampled = pd.concat([sampled, data.loc[[min_idx]]], ignore_index=True)
                        if max_idx not in sampled.index:
                            sampled = pd.concat([sampled, data.loc[[max_idx]]], ignore_index=True)
            
            # Remove duplicates and reset index
            sampled = sampled.drop_duplicates().reset_index(drop=True)
            
            # Ensure we don't exceed max_points after adding extremes
            if len(sampled) > max_points:
                sampled = sampled.sample(n=max_points, random_state=42).reset_index(drop=True)
            
            logger.info(f"Sampled dataset to {len(sampled)} points using {sampling_strategy} strategy")
            
            return sampled
            
        except Exception as e:
            logger.error(f"Error sampling dataset: {e}")
            return data
    
    def optimize_plotly_figure(self, 
                             fig: go.Figure,
                             max_points: int = 10000,
                             enable_webgl: bool = True,
                             reduce_precision: bool = True) -> go.Figure:
        """
        Optimize Plotly figure for performance
        
        Args:
            fig: Plotly figure to optimize
            max_points: Maximum points per trace
            enable_webgl: Whether to use WebGL rendering
            reduce_precision: Whether to reduce numeric precision
            
        Returns:
            Optimized figure
        """
        try:
            optimized_fig = go.Figure(fig)
            
            # Enable WebGL for better performance with large datasets
            if enable_webgl:
                new_data = []
                for trace in optimized_fig.data:
                    if hasattr(trace, 'mode') and 'markers' in str(trace.mode):
                        # Use scattergl for scatter plots
                        if trace.type == 'scatter':
                            # Create new scattergl trace
                            new_trace = go.Scattergl(
                                x=trace.x,
                                y=trace.y,
                                mode=trace.mode,
                                name=trace.name,
                                marker=trace.marker
                            )
                            new_data.append(new_trace)
                        else:
                            new_data.append(trace)
                    else:
                        new_data.append(trace)
                
                optimized_fig.data = new_data
            
            # Optimize traces
            new_data = []
            for i, trace in enumerate(optimized_fig.data):
                if hasattr(trace, 'x') and hasattr(trace, 'y'):
                    x_data = trace.x
                    y_data = trace.y
                    
                    if x_data is not None and y_data is not None:
                        data_length = len(x_data) if hasattr(x_data, '__len__') else 0
                        
                        # Sample data if too large
                        if data_length > max_points:
                            indices = np.linspace(0, data_length - 1, max_points, dtype=int)
                            
                            # Create new trace with sampled data
                            new_trace_data = dict(trace)
                            new_trace_data['x'] = [x_data[idx] for idx in indices]
                            new_trace_data['y'] = [y_data[idx] for idx in indices]
                            
                            # Handle z data for 3D plots
                            if hasattr(trace, 'z') and trace.z is not None:
                                new_trace_data['z'] = [trace.z[idx] for idx in indices]
                            
                            # Create new trace of same type
                            if trace.type == 'scatter':
                                new_trace = go.Scatter(**new_trace_data)
                            elif trace.type == 'scattergl':
                                new_trace = go.Scattergl(**new_trace_data)
                            else:
                                new_trace = trace  # Keep original for other types
                            
                            new_data.append(new_trace)
                            logger.info(f"Sampled trace {i} from {data_length} to {max_points} points")
                        else:
                            new_data.append(trace)
                    else:
                        new_data.append(trace)
                else:
                    new_data.append(trace)
            
            optimized_fig.data = new_data
                
            # Reduce precision for numeric data
            if reduce_precision:
                final_data = []
                for trace in optimized_fig.data:
                    trace_data = dict(trace)
                    for attr in ['x', 'y', 'z']:
                        if hasattr(trace, attr):
                            data = getattr(trace, attr)
                            if data is not None and hasattr(data, '__iter__'):
                                try:
                                    # Round to 6 decimal places
                                    rounded_data = [round(float(val), 6) if isinstance(val, (int, float)) else val 
                                                  for val in data]
                                    trace_data[attr] = rounded_data
                                except (ValueError, TypeError):
                                    # Skip if data is not numeric
                                    pass
                    
                    # Create new trace with rounded data
                    if trace.type == 'scatter':
                        final_data.append(go.Scatter(**trace_data))
                    elif trace.type == 'scattergl':
                        final_data.append(go.Scattergl(**trace_data))
                    else:
                        final_data.append(trace)
                
                optimized_fig.data = final_data
            
            # Optimize layout
            optimized_fig.update_layout(
                # Disable hover for better performance
                hovermode='closest' if len(optimized_fig.data) < 5 else False,
                
                # Optimize rendering
                dragmode='pan',
                
                # Reduce animation duration
                transition_duration=300,
                
                # Optimize font rendering
                font=dict(size=12),
                
                # Disable unnecessary features for large datasets
                showlegend=len(optimized_fig.data) <= 10
            )
            
            logger.info("Optimized Plotly figure for performance")
            
            return optimized_fig
            
        except Exception as e:
            logger.error(f"Error optimizing Plotly figure: {e}")
            return fig
    
    def create_paginated_data_loader(self, 
                                   data_source: Callable,
                                   page_size: int = 1000,
                                   total_size: Optional[int] = None) -> Callable:
        """
        Create a paginated data loader for large datasets
        
        Args:
            data_source: Function that takes (offset, limit) and returns data
            page_size: Number of records per page
            total_size: Total number of records (if known)
            
        Returns:
            Paginated loader function
        """
        def paginated_loader(page: int = 0) -> Tuple[pd.DataFrame, bool]:
            """
            Load a page of data
            
            Args:
                page: Page number (0-based)
                
            Returns:
                Tuple of (data, has_more)
            """
            try:
                offset = page * page_size
                data = data_source(offset, page_size)
                
                # Determine if there are more pages
                has_more = len(data) == page_size
                if total_size is not None:
                    has_more = offset + len(data) < total_size
                
                return data, has_more
                
            except Exception as e:
                logger.error(f"Error loading page {page}: {e}")
                return pd.DataFrame(), False
        
        return paginated_loader
    
    def render_performance_metrics(self):
        """Render performance metrics in Streamlit"""
        try:
            if not self.enable_metrics or not self.metrics:
                st.info("No performance metrics available")
                return
            
            st.subheader("⚡ Performance Metrics")
            
            # Recent metrics summary
            recent_metrics = [m for m in self.metrics 
                            if (datetime.now() - m.timestamp).total_seconds() < 300]  # Last 5 minutes
            
            if recent_metrics:
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    avg_time = sum(m.execution_time for m in recent_metrics) / len(recent_metrics)
                    st.metric("Avg Response Time", f"{avg_time:.2f}s")
                
                with col2:
                    cache_hits = sum(1 for m in recent_metrics if m.cache_hit)
                    cache_rate = (cache_hits / len(recent_metrics)) * 100
                    st.metric("Cache Hit Rate", f"{cache_rate:.1f}%")
                
                with col3:
                    total_data = sum(m.data_size for m in recent_metrics)
                    st.metric("Data Processed", f"{total_data / 1024 / 1024:.1f} MB")
                
                with col4:
                    if recent_metrics:
                        current_memory = recent_metrics[-1].memory_usage
                        st.metric("Memory Usage", f"{current_memory:.1f} MB")
            
            # Cache statistics
            st.subheader("💾 Cache Statistics")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Cache Entries", len(self.cache))
            
            with col2:
                cache_size_mb = self.current_cache_size / 1024 / 1024
                st.metric("Cache Size", f"{cache_size_mb:.1f} MB")
            
            with col3:
                utilization = (self.current_cache_size / self.cache_size_bytes) * 100
                st.metric("Cache Utilization", f"{utilization:.1f}%")
            
            # Performance trends
            if len(self.metrics) > 10:
                st.subheader("📈 Performance Trends")
                
                # Create DataFrame for plotting
                metrics_df = pd.DataFrame([
                    {
                        'timestamp': m.timestamp,
                        'execution_time': m.execution_time,
                        'cache_hit': m.cache_hit,
                        'memory_usage': m.memory_usage,
                        'operation': m.operation_name
                    }
                    for m in self.metrics[-100:]  # Last 100 metrics
                ])
                
                # Execution time trend
                fig_time = px.line(metrics_df, x='timestamp', y='execution_time', 
                                 color='operation', title='Execution Time Trend')
                st.plotly_chart(fig_time, use_container_width=True)
                
                # Memory usage trend
                fig_memory = px.line(metrics_df, x='timestamp', y='memory_usage',
                                   title='Memory Usage Trend')
                st.plotly_chart(fig_memory, use_container_width=True)
        
        except Exception as e:
            logger.error(f"Error rendering performance metrics: {e}")
            st.error("Error displaying performance metrics")
    
    def clear_cache(self):
        """Clear all cache entries"""
        try:
            self.cache.clear()
            self.cache_metadata.clear()
            self.current_cache_size = 0
            self.lazy_load_registry.clear()
            
            # Force garbage collection
            gc.collect()
            
            logger.info("Cache cleared successfully")
            
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        try:
            return {
                'entries': len(self.cache),
                'size_bytes': self.current_cache_size,
                'size_mb': self.current_cache_size / 1024 / 1024,
                'utilization_percent': (self.current_cache_size / self.cache_size_bytes) * 100,
                'max_size_mb': self.cache_size_mb
            }
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {}

# Utility functions and decorators

def performance_monitor(operation_name: str = None):
    """
    Decorator to monitor performance of functions
    
    Args:
        operation_name: Name for the operation (defaults to function name)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time
                
                # Log performance
                op_name = operation_name or func.__name__
                logger.info(f"Performance: {op_name} completed in {execution_time:.2f}s")
                
                return result
                
            except Exception as e:
                execution_time = time.time() - start_time
                op_name = operation_name or func.__name__
                logger.error(f"Performance: {op_name} failed after {execution_time:.2f}s: {e}")
                raise
        
        return wrapper
    return decorator

def get_performance_optimizer() -> PerformanceOptimizer:
    """Get or create performance optimizer instance"""
    try:
        if hasattr(st.session_state, '__contains__') and 'performance_optimizer' not in st.session_state:
            st.session_state.performance_optimizer = PerformanceOptimizer()
        
        if hasattr(st.session_state, 'performance_optimizer'):
            return st.session_state.performance_optimizer
        else:
            return PerformanceOptimizer()
    except (AttributeError, TypeError):
        # Session state not available (e.g., in tests)
        return PerformanceOptimizer()