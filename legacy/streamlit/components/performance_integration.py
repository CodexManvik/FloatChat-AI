"""
Performance Integration Component for ARGO Float Dashboard

This component integrates all performance optimization features
and provides a unified interface for performance management.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from typing import Dict, Any, Optional, Callable, List, Tuple, Union
from datetime import datetime, timedelta
import logging
import time
from dataclasses import dataclass

from .performance_optimizer import PerformanceOptimizer, get_performance_optimizer
from .data_sampler import DataSampler, SamplingConfig, SamplingStrategy, get_data_sampler
from .streamlit_cache import StreamlitCache, get_streamlit_cache

logger = logging.getLogger(__name__)

@dataclass
class PerformanceConfig:
    """Configuration for performance optimization"""
    enable_caching: bool = True
    enable_sampling: bool = True
    enable_lazy_loading: bool = True
    max_cache_size_mb: int = 200
    default_sample_size: int = 10000
    cache_ttl_hours: int = 24
    auto_optimize_plots: bool = True
    enable_webgl: bool = True

class PerformanceIntegration:
    """Integrated performance optimization system"""
    
    def __init__(self, config: Optional[PerformanceConfig] = None):
        """
        Initialize the performance integration system
        
        Args:
            config: Performance configuration
        """
        self.config = config or PerformanceConfig()
        
        # Initialize components
        self.optimizer = get_performance_optimizer()
        self.sampler = get_data_sampler()
        self.cache = get_streamlit_cache()
        
        # Performance tracking
        self.operation_times = {}
        self.data_sizes = {}
        
        # Initialize session state
        self._initialize_session_state()
    
    def _initialize_session_state(self):
        """Initialize session state for performance integration"""
        try:
            if hasattr(st.session_state, '__contains__') and 'performance_integration_initialized' not in st.session_state:
                st.session_state.performance_integration_initialized = True
                st.session_state.performance_config = self.config
                st.session_state.auto_optimization_enabled = True
        except (AttributeError, TypeError):
            # Session state not available (e.g., in tests)
            pass
    
    def optimize_data_loading(self, 
                            data_loader: Callable,
                            loader_key: str,
                            target_size: Optional[int] = None,
                            sampling_strategy: Optional[SamplingStrategy] = None,
                            cache_ttl_hours: Optional[int] = None) -> pd.DataFrame:
        """
        Optimize data loading with caching and sampling
        
        Args:
            data_loader: Function to load data
            loader_key: Unique key for caching
            target_size: Target sample size
            sampling_strategy: Sampling strategy to use
            cache_ttl_hours: Cache TTL in hours
            
        Returns:
            Optimized DataFrame
        """
        try:
            start_time = time.time()
            
            # Use caching if enabled
            if self.config.enable_caching:
                @self.cache.cache_data(ttl_hours=cache_ttl_hours or self.config.cache_ttl_hours)
                def cached_loader():
                    return data_loader()
                
                data = cached_loader()
            else:
                data = data_loader()
            
            load_time = time.time() - start_time
            original_size = len(data) if isinstance(data, pd.DataFrame) else 0
            
            # Apply sampling if enabled and data is large
            if (self.config.enable_sampling and 
                isinstance(data, pd.DataFrame) and 
                len(data) > (target_size or self.config.default_sample_size)):
                
                # Get sampling configuration
                if sampling_strategy:
                    config = SamplingConfig(
                        strategy=sampling_strategy,
                        target_size=target_size or self.config.default_sample_size
                    )
                else:
                    config = self.sampler.recommend_sampling_strategy(
                        data, target_size or self.config.default_sample_size
                    )
                
                # Sample data
                sampling_result = self.sampler.sample_data(data, config)
                data = sampling_result.sampled_data
                
                logger.info(f"Sampled data from {original_size} to {len(data)} records "
                           f"using {config.strategy.value} strategy")
            
            # Record performance metrics
            total_time = time.time() - start_time
            self.operation_times[loader_key] = total_time
            self.data_sizes[loader_key] = len(data) if isinstance(data, pd.DataFrame) else 0
            
            logger.info(f"Data loading optimized for {loader_key}: "
                       f"{original_size} -> {len(data) if isinstance(data, pd.DataFrame) else 0} "
                       f"in {total_time:.2f}s")
            
            return data
            
        except Exception as e:
            logger.error(f"Error in optimized data loading for {loader_key}: {e}")
            # Fallback to direct loading
            return data_loader()
    
    def optimize_visualization(self, 
                             fig: go.Figure,
                             max_points: Optional[int] = None,
                             enable_webgl: Optional[bool] = None) -> go.Figure:
        """
        Optimize Plotly visualization for performance
        
        Args:
            fig: Plotly figure to optimize
            max_points: Maximum points per trace
            enable_webgl: Whether to enable WebGL
            
        Returns:
            Optimized figure
        """
        try:
            if not self.config.auto_optimize_plots:
                return fig
            
            return self.optimizer.optimize_plotly_figure(
                fig,
                max_points=max_points or self.config.default_sample_size,
                enable_webgl=enable_webgl if enable_webgl is not None else self.config.enable_webgl
            )
            
        except Exception as e:
            logger.error(f"Error optimizing visualization: {e}")
            return fig
    
    def create_optimized_scatter_plot(self, 
                                    data: pd.DataFrame,
                                    x_col: str,
                                    y_col: str,
                                    color_col: Optional[str] = None,
                                    title: str = "Scatter Plot",
                                    max_points: Optional[int] = None) -> go.Figure:
        """
        Create optimized scatter plot with automatic sampling
        
        Args:
            data: DataFrame with plot data
            x_col: X-axis column name
            y_col: Y-axis column name
            color_col: Color column name (optional)
            title: Plot title
            max_points: Maximum points to plot
            
        Returns:
            Optimized Plotly figure
        """
        try:
            plot_data = data.copy()
            
            # Sample data if too large
            target_size = max_points or self.config.default_sample_size
            if len(plot_data) > target_size:
                config = SamplingConfig(
                    strategy=SamplingStrategy.RANDOM,
                    target_size=target_size,
                    preserve_extremes=True
                )
                
                sampling_result = self.sampler.sample_data(plot_data, config)
                plot_data = sampling_result.sampled_data
                
                logger.info(f"Sampled plot data from {len(data)} to {len(plot_data)} points")
            
            # Create figure
            if color_col and color_col in plot_data.columns:
                fig = go.Figure()
                
                # Group by color column for better performance
                for color_value in plot_data[color_col].unique():
                    subset = plot_data[plot_data[color_col] == color_value]
                    
                    trace_type = go.Scattergl if self.config.enable_webgl else go.Scatter
                    fig.add_trace(trace_type(
                        x=subset[x_col],
                        y=subset[y_col],
                        mode='markers',
                        name=str(color_value),
                        marker=dict(size=4)
                    ))
            else:
                trace_type = go.Scattergl if self.config.enable_webgl else go.Scatter
                fig = go.Figure(data=[trace_type(
                    x=plot_data[x_col],
                    y=plot_data[y_col],
                    mode='markers',
                    marker=dict(size=4)
                )])
            
            # Update layout
            fig.update_layout(
                title=title,
                xaxis_title=x_col,
                yaxis_title=y_col,
                hovermode='closest',
                showlegend=color_col is not None
            )
            
            return fig
            
        except Exception as e:
            logger.error(f"Error creating optimized scatter plot: {e}")
            # Return empty figure on error
            return go.Figure()
    
    def create_optimized_line_plot(self, 
                                 data: pd.DataFrame,
                                 x_col: str,
                                 y_col: str,
                                 group_col: Optional[str] = None,
                                 title: str = "Line Plot",
                                 max_points: Optional[int] = None) -> go.Figure:
        """
        Create optimized line plot with automatic sampling
        
        Args:
            data: DataFrame with plot data
            x_col: X-axis column name
            y_col: Y-axis column name
            group_col: Grouping column name (optional)
            title: Plot title
            max_points: Maximum points per line
            
        Returns:
            Optimized Plotly figure
        """
        try:
            plot_data = data.copy()
            target_size = max_points or self.config.default_sample_size
            
            fig = go.Figure()
            
            if group_col and group_col in plot_data.columns:
                # Handle grouped data
                for group_value in plot_data[group_col].unique():
                    group_data = plot_data[plot_data[group_col] == group_value].copy()
                    
                    # Sample group data if too large
                    if len(group_data) > target_size:
                        config = SamplingConfig(
                            strategy=SamplingStrategy.SYSTEMATIC,  # Better for time series
                            target_size=target_size,
                            preserve_extremes=True
                        )
                        
                        sampling_result = self.sampler.sample_data(group_data, config)
                        group_data = sampling_result.sampled_data
                    
                    # Sort by x column for proper line plotting
                    group_data = group_data.sort_values(x_col)
                    
                    trace_type = go.Scattergl if self.config.enable_webgl else go.Scatter
                    fig.add_trace(trace_type(
                        x=group_data[x_col],
                        y=group_data[y_col],
                        mode='lines+markers',
                        name=str(group_value),
                        line=dict(width=2),
                        marker=dict(size=3)
                    ))
            else:
                # Handle single line
                if len(plot_data) > target_size:
                    config = SamplingConfig(
                        strategy=SamplingStrategy.SYSTEMATIC,
                        target_size=target_size,
                        preserve_extremes=True
                    )
                    
                    sampling_result = self.sampler.sample_data(plot_data, config)
                    plot_data = sampling_result.sampled_data
                
                # Sort by x column
                plot_data = plot_data.sort_values(x_col)
                
                trace_type = go.Scattergl if self.config.enable_webgl else go.Scatter
                fig.add_trace(trace_type(
                    x=plot_data[x_col],
                    y=plot_data[y_col],
                    mode='lines+markers',
                    line=dict(width=2),
                    marker=dict(size=3)
                ))
            
            # Update layout
            fig.update_layout(
                title=title,
                xaxis_title=x_col,
                yaxis_title=y_col,
                hovermode='x unified'
            )
            
            return fig
            
        except Exception as e:
            logger.error(f"Error creating optimized line plot: {e}")
            return go.Figure()
    
    def lazy_load_component(self, 
                          component_loader: Callable,
                          component_key: str,
                          placeholder_text: str = "Loading component...",
                          *args, **kwargs) -> Any:
        """
        Lazy load a Streamlit component with caching
        
        Args:
            component_loader: Function to load the component
            component_key: Unique key for caching
            placeholder_text: Placeholder text while loading
            *args, **kwargs: Arguments for component loader
            
        Returns:
            Loaded component result
        """
        try:
            if not self.config.enable_lazy_loading:
                return component_loader(*args, **kwargs)
            
            return self.optimizer.lazy_load_data(
                component_loader,
                component_key,
                placeholder_text,
                *args, **kwargs
            )
            
        except Exception as e:
            logger.error(f"Error in lazy loading component {component_key}: {e}")
            return component_loader(*args, **kwargs)
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary across all components"""
        try:
            summary = {
                'cache_stats': self.cache.get_cache_info(),
                'optimizer_stats': {
                    'cache_entries': len(self.optimizer.cache),
                    'cache_size_mb': self.optimizer.current_cache_size / 1024 / 1024,
                    'metrics_count': len(self.optimizer.metrics)
                },
                'sampler_stats': {
                    'sampling_history': len(self.sampler.sampling_history),
                    'last_sampling': self.sampler.sampling_history[-1] if self.sampler.sampling_history else None
                },
                'operation_times': self.operation_times,
                'data_sizes': self.data_sizes,
                'config': {
                    'caching_enabled': self.config.enable_caching,
                    'sampling_enabled': self.config.enable_sampling,
                    'lazy_loading_enabled': self.config.enable_lazy_loading,
                    'auto_optimize_plots': self.config.auto_optimize_plots
                }
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"Error getting performance summary: {e}")
            return {}
    
    def render_performance_dashboard(self):
        """Render comprehensive performance dashboard"""
        try:
            st.header("⚡ Performance Dashboard")
            
            # Performance summary
            summary = self.get_performance_summary()
            
            # Key metrics
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                cache_stats = summary.get('cache_stats', {})
                st.metric("Cache Hit Rate", f"{cache_stats.get('hit_rate', 0):.1f}%")
            
            with col2:
                cache_size = cache_stats.get('total_size_mb', 0)
                st.metric("Cache Size", f"{cache_size:.1f} MB")
            
            with col3:
                avg_time = np.mean(list(self.operation_times.values())) if self.operation_times else 0
                st.metric("Avg Operation Time", f"{avg_time:.2f}s")
            
            with col4:
                total_data = sum(self.data_sizes.values()) if self.data_sizes else 0
                st.metric("Total Data Processed", f"{total_data:,} records")
            
            # Configuration
            st.subheader("⚙️ Performance Configuration")
            
            col1, col2 = st.columns(2)
            
            with col1:
                enable_caching = st.checkbox(
                    "Enable Caching",
                    value=self.config.enable_caching,
                    help="Cache frequently accessed data"
                )
                
                enable_sampling = st.checkbox(
                    "Enable Data Sampling",
                    value=self.config.enable_sampling,
                    help="Sample large datasets for better performance"
                )
                
                enable_lazy_loading = st.checkbox(
                    "Enable Lazy Loading",
                    value=self.config.enable_lazy_loading,
                    help="Load components only when needed"
                )
            
            with col2:
                auto_optimize_plots = st.checkbox(
                    "Auto-optimize Plots",
                    value=self.config.auto_optimize_plots,
                    help="Automatically optimize Plotly figures"
                )
                
                enable_webgl = st.checkbox(
                    "Enable WebGL",
                    value=self.config.enable_webgl,
                    help="Use WebGL for better plot performance"
                )
                
                default_sample_size = st.number_input(
                    "Default Sample Size",
                    min_value=1000,
                    max_value=50000,
                    value=self.config.default_sample_size,
                    step=1000,
                    help="Default maximum number of data points"
                )
            
            # Update configuration
            if st.button("Apply Configuration"):
                self.config.enable_caching = enable_caching
                self.config.enable_sampling = enable_sampling
                self.config.enable_lazy_loading = enable_lazy_loading
                self.config.auto_optimize_plots = auto_optimize_plots
                self.config.enable_webgl = enable_webgl
                self.config.default_sample_size = default_sample_size
                
                st.success("Configuration updated!")
                st.rerun()
            
            # Component dashboards
            st.markdown("---")
            
            # Cache management
            st.subheader("💾 Cache Management")
            self.cache.render_cache_controls()
            
            # Performance metrics
            st.subheader("📊 Performance Metrics")
            self.optimizer.render_performance_metrics()
            
            # Operation times
            if self.operation_times:
                st.subheader("⏱️ Operation Times")
                
                times_data = []
                for operation, time_taken in self.operation_times.items():
                    times_data.append({
                        'Operation': operation,
                        'Time (s)': f"{time_taken:.3f}",
                        'Data Size': self.data_sizes.get(operation, 0)
                    })
                
                times_df = pd.DataFrame(times_data)
                st.dataframe(times_df, use_container_width=True)
        
        except Exception as e:
            logger.error(f"Error rendering performance dashboard: {e}")
            st.error("Error displaying performance dashboard")
    
    def clear_all_caches(self):
        """Clear all caches across components"""
        try:
            self.cache.invalidate_cache()
            self.optimizer.clear_cache()
            
            # Clear operation tracking
            self.operation_times.clear()
            self.data_sizes.clear()
            
            logger.info("All caches cleared")
            
        except Exception as e:
            logger.error(f"Error clearing caches: {e}")

# Global instance
_performance_integration = None

def get_performance_integration(config: Optional[PerformanceConfig] = None) -> PerformanceIntegration:
    """Get global performance integration instance"""
    global _performance_integration
    
    if _performance_integration is None:
        _performance_integration = PerformanceIntegration(config)
    
    return _performance_integration

# Convenience functions
def optimize_data_loading(data_loader: Callable, 
                         loader_key: str,
                         target_size: Optional[int] = None,
                         sampling_strategy: Optional[SamplingStrategy] = None) -> pd.DataFrame:
    """Convenience function for optimized data loading"""
    integration = get_performance_integration()
    return integration.optimize_data_loading(data_loader, loader_key, target_size, sampling_strategy)

def optimize_visualization(fig: go.Figure, 
                          max_points: Optional[int] = None,
                          enable_webgl: Optional[bool] = None) -> go.Figure:
    """Convenience function for visualization optimization"""
    integration = get_performance_integration()
    return integration.optimize_visualization(fig, max_points, enable_webgl)

def create_optimized_plot(data: pd.DataFrame,
                         plot_type: str,
                         x_col: str,
                         y_col: str,
                         **kwargs) -> go.Figure:
    """Convenience function for creating optimized plots"""
    integration = get_performance_integration()
    
    if plot_type == 'scatter':
        return integration.create_optimized_scatter_plot(data, x_col, y_col, **kwargs)
    elif plot_type == 'line':
        return integration.create_optimized_line_plot(data, x_col, y_col, **kwargs)
    else:
        raise ValueError(f"Unsupported plot type: {plot_type}")

def lazy_load_component(component_loader: Callable,
                       component_key: str,
                       placeholder_text: str = "Loading...",
                       *args, **kwargs) -> Any:
    """Convenience function for lazy loading components"""
    integration = get_performance_integration()
    return integration.lazy_load_component(component_loader, component_key, placeholder_text, *args, **kwargs)