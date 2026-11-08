"""
Unit tests for Performance Optimizer Component
"""

import pytest
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import sys
import os
import time

# Add the parent directory to the path to import components
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from components.performance_optimizer import (
    PerformanceOptimizer, CacheEntry, PerformanceMetrics,
    performance_monitor, get_performance_optimizer
)

class TestPerformanceOptimizer:
    """Test cases for PerformanceOptimizer class."""
    
    @pytest.fixture
    def optimizer(self):
        """Create a PerformanceOptimizer instance for testing."""
        return PerformanceOptimizer(cache_size_mb=10, default_ttl_seconds=3600)
    
    @pytest.fixture
    def sample_dataframe(self):
        """Create sample DataFrame for testing."""
        return pd.DataFrame({
            'x': np.random.randn(1000),
            'y': np.random.randn(1000),
            'category': np.random.choice(['A', 'B', 'C'], 1000)
        })
    
    def test_initialization(self, optimizer):
        """Test PerformanceOptimizer initialization."""
        assert isinstance(optimizer, PerformanceOptimizer)
        assert optimizer.cache_size_mb == 10
        assert optimizer.default_ttl_seconds == 3600
        assert optimizer.cache == {}
        assert optimizer.cache_metadata == {}
        assert optimizer.current_cache_size == 0
    
    def test_generate_cache_key(self, optimizer):
        """Test cache key generation."""
        key1 = optimizer._generate_cache_key("test_func", (1, 2), {"param": "value"})
        key2 = optimizer._generate_cache_key("test_func", (1, 2), {"param": "value"})
        key3 = optimizer._generate_cache_key("test_func", (1, 3), {"param": "value"})
        
        # Same inputs should generate same key
        assert key1 == key2
        
        # Different inputs should generate different keys
        assert key1 != key3
        
        # Keys should be strings
        assert isinstance(key1, str)
    
    def test_get_data_size(self, optimizer, sample_dataframe):
        """Test data size estimation."""
        # Test DataFrame size
        df_size = optimizer._get_data_size(sample_dataframe)
        assert df_size > 0
        assert isinstance(df_size, (int, np.integer))
        
        # Test string size
        string_size = optimizer._get_data_size("test string")
        assert string_size > 0
        
        # Test numeric size
        int_size = optimizer._get_data_size(42)
        assert int_size == 8
        
        # Test list size
        list_size = optimizer._get_data_size([1, 2, 3])
        assert list_size > 0
    
    def test_cache_function_decorator(self, optimizer):
        """Test cache function decorator."""
        call_count = 0
        
        @optimizer.cache_function(ttl_seconds=3600)
        def expensive_function(x, y):
            nonlocal call_count
            call_count += 1
            return x + y
        
        # First call should execute function
        result1 = expensive_function(2, 3)
        assert result1 == 5
        assert call_count == 1
        
        # Second call should use cache
        result2 = expensive_function(2, 3)
        assert result2 == 5
        assert call_count == 1  # Should not increment
        
        # Different parameters should execute function again
        result3 = expensive_function(3, 4)
        assert result3 == 7
        assert call_count == 2
    
    def test_cache_cleanup(self, optimizer):
        """Test cache cleanup functionality."""
        # Add some test entries
        test_data = "test data"
        cache_key = "test_key"
        
        optimizer.cache[cache_key] = test_data
        optimizer.cache_metadata[cache_key] = CacheEntry(
            data=test_data,
            timestamp=datetime.now() - timedelta(hours=2),  # Expired
            access_count=1,
            size_bytes=100,
            ttl_seconds=3600  # 1 hour TTL
        )
        optimizer.current_cache_size = 100
        
        # Run cleanup
        optimizer._cleanup_cache()
        
        # Expired entry should be removed
        assert cache_key not in optimizer.cache
        assert cache_key not in optimizer.cache_metadata
        assert optimizer.current_cache_size == 0
    
    def test_lazy_load_data(self, optimizer):
        """Test lazy loading functionality."""
        load_count = 0
        
        def data_loader():
            nonlocal load_count
            load_count += 1
            return pd.DataFrame({'data': [1, 2, 3]})
        
        # First call should load data
        result1 = optimizer.lazy_load_data(data_loader, "test_loader", "Loading test data...")
        assert isinstance(result1, pd.DataFrame)
        assert load_count == 1
        
        # Second call should use cached data
        result2 = optimizer.lazy_load_data(data_loader, "test_loader", "Loading test data...")
        assert isinstance(result2, pd.DataFrame)
        assert load_count == 1  # Should not increment
        
        # Results should be the same
        pd.testing.assert_frame_equal(result1, result2)
    
    def test_sample_large_dataset_random(self, optimizer):
        """Test random sampling of large dataset."""
        # Create large dataset
        large_data = pd.DataFrame({
            'x': np.random.randn(50000),
            'y': np.random.randn(50000),
            'depth': np.random.uniform(0, 2000, 50000)
        })
        
        # Sample data
        sampled = optimizer.sample_large_dataset(
            large_data, 
            max_points=10000, 
            sampling_strategy="random"
        )
        
        assert len(sampled) <= 10000
        assert len(sampled) > 0
        assert list(sampled.columns) == list(large_data.columns)
    
    def test_sample_large_dataset_systematic(self, optimizer):
        """Test systematic sampling of large dataset."""
        large_data = pd.DataFrame({
            'x': range(20000),
            'y': np.random.randn(20000)
        })
        
        sampled = optimizer.sample_large_dataset(
            large_data,
            max_points=5000,
            sampling_strategy="systematic"
        )
        
        assert len(sampled) <= 5000
        assert len(sampled) > 0
        
        # Check that sampling is systematic (evenly spaced)
        if len(sampled) > 1:
            x_values = sampled['x'].values
            # Should be roughly evenly spaced
            assert x_values[1] - x_values[0] > 1
    
    def test_sample_large_dataset_stratified(self, optimizer):
        """Test stratified sampling of large dataset."""
        large_data = pd.DataFrame({
            'depth': np.random.uniform(0, 2000, 15000),
            'temperature': np.random.randn(15000)
        })
        
        sampled = optimizer.sample_large_dataset(
            large_data,
            max_points=5000,
            sampling_strategy="stratified"
        )
        
        assert len(sampled) <= 5000
        assert len(sampled) > 0
        assert 'depth' in sampled.columns
    
    def test_sample_small_dataset(self, optimizer):
        """Test sampling when dataset is already small."""
        small_data = pd.DataFrame({
            'x': [1, 2, 3, 4, 5],
            'y': [5, 4, 3, 2, 1]
        })
        
        sampled = optimizer.sample_large_dataset(small_data, max_points=10000)
        
        # Should return original data unchanged
        pd.testing.assert_frame_equal(sampled, small_data)
    
    def test_optimize_plotly_figure(self, optimizer):
        """Test Plotly figure optimization."""
        # Create test figure with many points
        x_data = np.random.randn(20000)
        y_data = np.random.randn(20000)
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=x_data, y=y_data, mode='markers'))
        
        # Optimize figure
        optimized_fig = optimizer.optimize_plotly_figure(fig, max_points=5000)
        
        assert isinstance(optimized_fig, go.Figure)
        assert len(optimized_fig.data) == 1
        
        # Check that data was sampled
        trace = optimized_fig.data[0]
        assert len(trace.x) <= 5000
        assert len(trace.y) <= 5000
    
    def test_optimize_plotly_figure_webgl(self, optimizer):
        """Test Plotly figure optimization with WebGL."""
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=[1, 2, 3], y=[1, 2, 3], mode='markers'))
        
        optimized_fig = optimizer.optimize_plotly_figure(fig, enable_webgl=True)
        
        # Should convert to scattergl for better performance
        assert optimized_fig.data[0].type == 'scattergl'
    
    def test_create_paginated_data_loader(self, optimizer):
        """Test paginated data loader creation."""
        # Mock data source
        def mock_data_source(offset, limit):
            total_data = list(range(100))  # 100 items total
            return pd.DataFrame({
                'id': total_data[offset:offset + limit],
                'value': [x * 2 for x in total_data[offset:offset + limit]]
            })
        
        # Create paginated loader
        paginated_loader = optimizer.create_paginated_data_loader(
            mock_data_source, page_size=10, total_size=100
        )
        
        # Test first page
        page0_data, has_more = paginated_loader(0)
        assert len(page0_data) == 10
        assert has_more is True
        assert page0_data['id'].iloc[0] == 0
        
        # Test last page
        page9_data, has_more = paginated_loader(9)
        assert len(page9_data) == 10
        assert has_more is False
        assert page9_data['id'].iloc[0] == 90
    
    def test_record_metric(self, optimizer):
        """Test performance metric recording."""
        optimizer._record_metric("test_operation", 1.5, 1024, True)
        
        assert len(optimizer.metrics) == 1
        metric = optimizer.metrics[0]
        assert metric.operation_name == "test_operation"
        assert metric.execution_time == 1.5
        assert metric.data_size == 1024
        assert metric.cache_hit is True
    
    def test_clear_cache(self, optimizer):
        """Test cache clearing."""
        # Add some test data
        optimizer.cache["test1"] = "data1"
        optimizer.cache["test2"] = "data2"
        optimizer.cache_metadata["test1"] = CacheEntry(
            data="data1", timestamp=datetime.now(), access_count=1, 
            size_bytes=100, ttl_seconds=3600
        )
        optimizer.current_cache_size = 100
        
        # Clear cache
        optimizer.clear_cache()
        
        assert len(optimizer.cache) == 0
        assert len(optimizer.cache_metadata) == 0
        assert optimizer.current_cache_size == 0
        assert len(optimizer.lazy_load_registry) == 0

class TestPerformanceMonitorDecorator:
    """Test cases for performance monitor decorator."""
    
    def test_performance_monitor_success(self):
        """Test performance monitor with successful function."""
        @performance_monitor("test_operation")
        def test_function(x, y):
            time.sleep(0.01)  # Small delay
            return x + y
        
        with patch('components.performance_optimizer.logger') as mock_logger:
            result = test_function(2, 3)
            
            assert result == 5
            mock_logger.info.assert_called_once()
            
            # Check log message contains timing info
            log_call = mock_logger.info.call_args[0][0]
            assert "test_operation completed" in log_call
            assert "s" in log_call  # Should contain time in seconds
    
    def test_performance_monitor_error(self):
        """Test performance monitor with failing function."""
        @performance_monitor("failing_operation")
        def failing_function():
            time.sleep(0.01)
            raise ValueError("Test error")
        
        with patch('components.performance_optimizer.logger') as mock_logger:
            with pytest.raises(ValueError):
                failing_function()
            
            mock_logger.error.assert_called_once()
            
            # Check error log message
            log_call = mock_logger.error.call_args[0][0]
            assert "failing_operation failed" in log_call
            assert "Test error" in log_call

class TestUtilityFunctions:
    """Test cases for utility functions."""
    
    @patch('streamlit.session_state', {})
    def test_get_performance_optimizer_new(self):
        """Test getting new performance optimizer."""
        optimizer = get_performance_optimizer()
        
        assert isinstance(optimizer, PerformanceOptimizer)
    
    @patch('streamlit.session_state', {'performance_optimizer': PerformanceOptimizer()})
    def test_get_performance_optimizer_existing(self):
        """Test getting existing performance optimizer."""
        existing_optimizer = PerformanceOptimizer()
        
        with patch('streamlit.session_state', {'performance_optimizer': existing_optimizer}):
            optimizer = get_performance_optimizer()
            
            assert optimizer is existing_optimizer

class TestIntegrationScenarios:
    """Test cases for integration scenarios."""
    
    def test_complete_caching_workflow(self):
        """Test complete caching workflow."""
        optimizer = PerformanceOptimizer(cache_size_mb=5)
        
        # Create cached function
        @optimizer.cache_function(ttl_seconds=3600)
        def process_data(data_size):
            # Simulate expensive operation
            return pd.DataFrame({
                'x': np.random.randn(data_size),
                'y': np.random.randn(data_size)
            })
        
        # First call - should cache
        result1 = process_data(1000)
        assert len(result1) == 1000
        assert len(optimizer.cache) == 1
        
        # Second call - should use cache
        result2 = process_data(1000)
        assert len(result2) == 1000
        pd.testing.assert_frame_equal(result1, result2)
        
        # Different parameters - should create new cache entry
        result3 = process_data(500)
        assert len(result3) == 500
        assert len(optimizer.cache) == 2
    
    def test_sampling_and_optimization_workflow(self):
        """Test combined sampling and optimization workflow."""
        optimizer = PerformanceOptimizer()
        
        # Create large dataset
        large_data = pd.DataFrame({
            'x': np.random.randn(25000),
            'y': np.random.randn(25000),
            'depth': np.random.uniform(0, 2000, 25000)
        })
        
        # Sample data
        sampled_data = optimizer.sample_large_dataset(
            large_data, max_points=5000, sampling_strategy="stratified"
        )
        
        # Create figure from sampled data
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=sampled_data['x'], 
            y=sampled_data['y'], 
            mode='markers'
        ))
        
        # Optimize figure
        optimized_fig = optimizer.optimize_plotly_figure(fig, max_points=2000)
        
        # Verify results
        assert len(sampled_data) <= 5000
        assert len(optimized_fig.data[0].x) <= 2000
        assert isinstance(optimized_fig, go.Figure)
    
    def test_lazy_loading_with_caching(self):
        """Test lazy loading combined with caching."""
        optimizer = PerformanceOptimizer()
        
        load_count = 0
        
        @optimizer.cache_function(ttl_seconds=3600)
        def expensive_data_loader():
            nonlocal load_count
            load_count += 1
            return pd.DataFrame({
                'data': np.random.randn(1000),
                'timestamp': [datetime.now()] * 1000
            })
        
        # First lazy load
        result1 = optimizer.lazy_load_data(
            expensive_data_loader, 
            "expensive_loader", 
            "Loading expensive data..."
        )
        
        assert load_count == 1
        assert len(result1) == 1000
        
        # Second lazy load - should use lazy load cache
        result2 = optimizer.lazy_load_data(
            expensive_data_loader,
            "expensive_loader",
            "Loading expensive data..."
        )
        
        assert load_count == 1  # Should not increment
        pd.testing.assert_frame_equal(result1, result2)

if __name__ == "__main__":
    pytest.main([__file__])