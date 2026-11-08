"""
Unit tests for Data Sampler Component
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
import sys
import os

# Add the parent directory to the path to import components
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from components.data_sampler import (
    DataSampler, SamplingStrategy, SamplingConfig, SamplingResult,
    get_data_sampler
)

class TestDataSampler:
    """Test cases for DataSampler class."""
    
    @pytest.fixture
    def sampler(self):
        """Create a DataSampler instance for testing."""
        return DataSampler()
    
    @pytest.fixture
    def large_dataset(self):
        """Create large dataset for testing."""
        np.random.seed(42)
        n_records = 20000
        
        return pd.DataFrame({
            'latitude': np.random.uniform(-60, 60, n_records),
            'longitude': np.random.uniform(-180, 180, n_records),
            'depth': np.random.uniform(0, 2000, n_records),
            'temperature': np.random.normal(15, 5, n_records),
            'salinity': np.random.normal(35, 2, n_records),
            'date': [datetime.now() - timedelta(days=int(x)) for x in np.random.randint(0, 365, n_records)]
        })
    
    @pytest.fixture
    def small_dataset(self):
        """Create small dataset for testing."""
        return pd.DataFrame({
            'x': [1, 2, 3, 4, 5],
            'y': [5, 4, 3, 2, 1],
            'category': ['A', 'B', 'A', 'C', 'B']
        })
    
    def test_initialization(self, sampler):
        """Test DataSampler initialization."""
        assert isinstance(sampler, DataSampler)
        assert sampler.sampling_history == []
        assert sampler.quality_metrics == {}
    
    def test_random_sampling(self, sampler, large_dataset):
        """Test random sampling strategy."""
        config = SamplingConfig(
            strategy=SamplingStrategy.RANDOM,
            target_size=5000
        )
        
        result = sampler.sample_data(large_dataset, config)
        
        assert isinstance(result, SamplingResult)
        assert result.original_size == len(large_dataset)
        assert result.sampled_size <= 5000
        assert result.strategy_used == SamplingStrategy.RANDOM
        assert 0 <= result.quality_score <= 1
        assert result.execution_time > 0
    
    def test_systematic_sampling(self, sampler, large_dataset):
        """Test systematic sampling strategy."""
        config = SamplingConfig(
            strategy=SamplingStrategy.SYSTEMATIC,
            target_size=4000
        )
        
        result = sampler.sample_data(large_dataset, config)
        
        assert result.sampled_size <= 4000
        assert result.strategy_used == SamplingStrategy.SYSTEMATIC
        assert len(result.sampled_data) > 0
    
    def test_stratified_sampling(self, sampler, large_dataset):
        """Test stratified sampling strategy."""
        config = SamplingConfig(
            strategy=SamplingStrategy.STRATIFIED,
            target_size=6000
        )
        
        result = sampler.sample_data(large_dataset, config)
        
        assert result.sampled_size <= 6000
        assert result.strategy_used == SamplingStrategy.STRATIFIED
        assert 'depth' in result.sampled_data.columns  # Should preserve stratification column
    
    def test_temporal_sampling(self, sampler, large_dataset):
        """Test temporal sampling strategy."""
        config = SamplingConfig(
            strategy=SamplingStrategy.TEMPORAL,
            target_size=3000,
            temporal_bins=12
        )
        
        result = sampler.sample_data(large_dataset, config)
        
        assert result.sampled_size <= 3000
        assert result.strategy_used == SamplingStrategy.TEMPORAL
        assert 'date' in result.sampled_data.columns
    
    def test_spatial_sampling(self, sampler, large_dataset):
        """Test spatial sampling strategy."""
        config = SamplingConfig(
            strategy=SamplingStrategy.SPATIAL,
            target_size=4000,
            spatial_bins=16
        )
        
        result = sampler.sample_data(large_dataset, config)
        
        assert result.sampled_size <= 4000
        assert result.strategy_used == SamplingStrategy.SPATIAL
        assert 'latitude' in result.sampled_data.columns
        assert 'longitude' in result.sampled_data.columns
    
    def test_adaptive_sampling(self, sampler, large_dataset):
        """Test adaptive sampling strategy."""
        config = SamplingConfig(
            strategy=SamplingStrategy.ADAPTIVE,
            target_size=5000
        )
        
        result = sampler.sample_data(large_dataset, config)
        
        assert result.sampled_size <= 5000
        assert result.strategy_used == SamplingStrategy.ADAPTIVE
        assert len(result.sampled_data) > 0
    
    def test_importance_sampling(self, sampler, large_dataset):
        """Test importance sampling strategy."""
        config = SamplingConfig(
            strategy=SamplingStrategy.IMPORTANCE,
            target_size=3000,
            importance_column='temperature'
        )
        
        result = sampler.sample_data(large_dataset, config)
        
        assert result.sampled_size <= 3000
        assert result.strategy_used == SamplingStrategy.IMPORTANCE
        assert 'temperature' in result.sampled_data.columns
    
    def test_importance_sampling_no_column(self, sampler, large_dataset):
        """Test importance sampling without importance column."""
        config = SamplingConfig(
            strategy=SamplingStrategy.IMPORTANCE,
            target_size=3000,
            importance_column='nonexistent_column'
        )
        
        result = sampler.sample_data(large_dataset, config)
        
        # Should fall back to random sampling
        assert result.sampled_size <= 3000
        assert len(result.sampled_data) > 0
    
    def test_small_dataset_no_sampling(self, sampler, small_dataset):
        """Test that small datasets are not sampled."""
        config = SamplingConfig(
            strategy=SamplingStrategy.RANDOM,
            target_size=10000  # Larger than dataset
        )
        
        result = sampler.sample_data(small_dataset, config)
        
        assert result.original_size == len(small_dataset)
        assert result.sampled_size == len(small_dataset)
        assert result.sampling_ratio == 1.0
        pd.testing.assert_frame_equal(result.sampled_data, small_dataset)
    
    def test_preserve_extremes(self, sampler):
        """Test extreme value preservation."""
        # Create dataset with clear extremes
        data = pd.DataFrame({
            'value': [1, 2, 3, 4, 5, 100, -100],  # 100 and -100 are extremes
            'other': np.random.randn(7)
        })
        
        config = SamplingConfig(
            strategy=SamplingStrategy.RANDOM,
            target_size=3,
            preserve_extremes=True
        )
        
        result = sampler.sample_data(data, config)
        
        # Should preserve extremes
        assert result.preserved_extremes > 0
        assert 100 in result.sampled_data['value'].values or -100 in result.sampled_data['value'].values
    
    def test_preserve_recent_data(self, sampler):
        """Test recent data preservation."""
        # Create dataset with recent and old data
        now = datetime.now()
        data = pd.DataFrame({
            'value': range(100),
            'date': [now - timedelta(days=x) for x in range(100)]
        })
        
        config = SamplingConfig(
            strategy=SamplingStrategy.RANDOM,
            target_size=20,
            preserve_recent=True
        )
        
        result = sampler.sample_data(data, config)
        
        # Should include some recent data
        recent_threshold = now - timedelta(days=10)  # Last 10 days
        recent_data = result.sampled_data[pd.to_datetime(result.sampled_data['date']) >= recent_threshold]
        assert len(recent_data) > 0
    
    def test_quality_score_calculation(self, sampler):
        """Test quality score calculation."""
        # Create dataset with known statistical properties
        np.random.seed(42)
        data = pd.DataFrame({
            'normal': np.random.normal(10, 2, 10000),
            'uniform': np.random.uniform(0, 100, 10000)
        })
        
        config = SamplingConfig(
            strategy=SamplingStrategy.RANDOM,
            target_size=1000
        )
        
        result = sampler.sample_data(data, config)
        
        # Quality score should be reasonable for random sampling
        assert 0 <= result.quality_score <= 1
        
        # For random sampling of sufficient size, quality should be decent
        assert result.quality_score > 0.3
    
    def test_sampling_history(self, sampler, large_dataset):
        """Test that sampling history is recorded."""
        config = SamplingConfig(
            strategy=SamplingStrategy.RANDOM,
            target_size=5000
        )
        
        # Perform sampling
        result = sampler.sample_data(large_dataset, config)
        
        # Check history
        assert len(sampler.sampling_history) == 1
        assert sampler.sampling_history[0] == result
    
    def test_recommend_sampling_strategy(self, sampler):
        """Test sampling strategy recommendation."""
        # Test with spatial-temporal data
        spatio_temporal_data = pd.DataFrame({
            'latitude': np.random.uniform(-60, 60, 10000),
            'longitude': np.random.uniform(-180, 180, 10000),
            'date': [datetime.now() - timedelta(days=x) for x in range(10000)],
            'value': np.random.randn(10000)
        })
        
        config = sampler.recommend_sampling_strategy(spatio_temporal_data, 2000)
        
        assert isinstance(config, SamplingConfig)
        assert config.target_size == 2000
        assert config.strategy == SamplingStrategy.ADAPTIVE  # Should recommend adaptive for rich data
        
        # Test with simple data
        simple_data = pd.DataFrame({
            'x': range(1000),
            'y': np.random.randn(1000)
        })
        
        config_simple = sampler.recommend_sampling_strategy(simple_data, 500)
        assert config_simple.strategy in [SamplingStrategy.SYSTEMATIC, SamplingStrategy.RANDOM]
    
    def test_error_handling(self, sampler):
        """Test error handling in sampling."""
        # Test with invalid data
        invalid_data = pd.DataFrame()
        
        config = SamplingConfig(
            strategy=SamplingStrategy.RANDOM,
            target_size=1000
        )
        
        result = sampler.sample_data(invalid_data, config)
        
        # Should handle gracefully
        assert isinstance(result, SamplingResult)
        assert result.original_size == 0
        assert result.sampled_size == 0
    
    def test_temporal_sampling_no_date_column(self, sampler):
        """Test temporal sampling fallback when no date column."""
        data = pd.DataFrame({
            'x': range(1000),
            'y': np.random.randn(1000)
        })
        
        config = SamplingConfig(
            strategy=SamplingStrategy.TEMPORAL,
            target_size=500
        )
        
        result = sampler.sample_data(data, config)
        
        # Should fall back to random sampling
        assert result.sampled_size <= 500
        assert len(result.sampled_data) > 0
    
    def test_spatial_sampling_no_coordinates(self, sampler):
        """Test spatial sampling fallback when no coordinate columns."""
        data = pd.DataFrame({
            'x': range(1000),
            'y': np.random.randn(1000)
        })
        
        config = SamplingConfig(
            strategy=SamplingStrategy.SPATIAL,
            target_size=500
        )
        
        result = sampler.sample_data(data, config)
        
        # Should fall back to random sampling
        assert result.sampled_size <= 500
        assert len(result.sampled_data) > 0

class TestSamplingConfig:
    """Test cases for SamplingConfig."""
    
    def test_sampling_config_creation(self):
        """Test SamplingConfig creation."""
        config = SamplingConfig(
            strategy=SamplingStrategy.STRATIFIED,
            target_size=5000,
            preserve_extremes=True,
            preserve_recent=False,
            quality_threshold=0.9,
            spatial_bins=20,
            temporal_bins=24,
            importance_column='temperature'
        )
        
        assert config.strategy == SamplingStrategy.STRATIFIED
        assert config.target_size == 5000
        assert config.preserve_extremes is True
        assert config.preserve_recent is False
        assert config.quality_threshold == 0.9
        assert config.spatial_bins == 20
        assert config.temporal_bins == 24
        assert config.importance_column == 'temperature'
    
    def test_sampling_config_defaults(self):
        """Test SamplingConfig default values."""
        config = SamplingConfig(
            strategy=SamplingStrategy.RANDOM,
            target_size=1000
        )
        
        assert config.preserve_extremes is True
        assert config.preserve_recent is True
        assert config.quality_threshold == 0.8
        assert config.spatial_bins == 10
        assert config.temporal_bins == 12
        assert config.importance_column is None

class TestSamplingResult:
    """Test cases for SamplingResult."""
    
    def test_sampling_result_creation(self):
        """Test SamplingResult creation."""
        sample_data = pd.DataFrame({'x': [1, 2, 3], 'y': [4, 5, 6]})
        
        result = SamplingResult(
            sampled_data=sample_data,
            original_size=1000,
            sampled_size=3,
            sampling_ratio=0.003,
            strategy_used=SamplingStrategy.RANDOM,
            quality_score=0.85,
            preserved_extremes=2,
            execution_time=0.5
        )
        
        assert len(result.sampled_data) == 3
        assert result.original_size == 1000
        assert result.sampled_size == 3
        assert result.sampling_ratio == 0.003
        assert result.strategy_used == SamplingStrategy.RANDOM
        assert result.quality_score == 0.85
        assert result.preserved_extremes == 2
        assert result.execution_time == 0.5

class TestUtilityFunctions:
    """Test cases for utility functions."""
    
    @patch('streamlit.session_state', {})
    def test_get_data_sampler_new(self):
        """Test getting new data sampler."""
        sampler = get_data_sampler()
        
        assert isinstance(sampler, DataSampler)
    
    @patch('streamlit.session_state', {'data_sampler': DataSampler()})
    def test_get_data_sampler_existing(self):
        """Test getting existing data sampler."""
        existing_sampler = DataSampler()
        
        with patch('streamlit.session_state', {'data_sampler': existing_sampler}):
            sampler = get_data_sampler()
            
            assert sampler is existing_sampler

class TestIntegrationScenarios:
    """Test cases for integration scenarios."""
    
    def test_complete_sampling_workflow(self):
        """Test complete sampling workflow."""
        sampler = DataSampler()
        
        # Create realistic oceanographic dataset
        np.random.seed(42)
        n_records = 15000
        
        data = pd.DataFrame({
            'float_id': np.random.choice(['FLOAT_001', 'FLOAT_002', 'FLOAT_003'], n_records),
            'latitude': np.random.uniform(-60, 60, n_records),
            'longitude': np.random.uniform(40, 120, n_records),  # Indian Ocean
            'depth': np.random.exponential(200, n_records),  # Depth distribution
            'temperature': 25 - 0.01 * np.random.exponential(200, n_records) + np.random.normal(0, 2, n_records),
            'salinity': np.random.normal(35, 2, n_records),
            'date': [datetime.now() - timedelta(days=int(x)) for x in np.random.randint(0, 365, n_records)]
        })
        
        # Get recommendation
        config = sampler.recommend_sampling_strategy(data, 3000)
        
        # Perform sampling
        result = sampler.sample_data(data, config)
        
        # Verify results
        assert result.original_size == n_records
        assert result.sampled_size <= 3000
        assert result.quality_score > 0
        assert result.execution_time > 0
        assert len(sampler.sampling_history) == 1
        
        # Check that important columns are preserved
        assert 'latitude' in result.sampled_data.columns
        assert 'longitude' in result.sampled_data.columns
        assert 'depth' in result.sampled_data.columns
        assert 'temperature' in result.sampled_data.columns
    
    def test_multiple_sampling_strategies_comparison(self):
        """Test comparison of different sampling strategies."""
        sampler = DataSampler()
        
        # Create test dataset
        np.random.seed(42)
        data = pd.DataFrame({
            'depth': np.random.uniform(0, 2000, 10000),
            'temperature': np.random.normal(15, 5, 10000),
            'latitude': np.random.uniform(-60, 60, 10000),
            'longitude': np.random.uniform(-180, 180, 10000),
            'date': [datetime.now() - timedelta(days=int(x)) for x in np.random.randint(0, 365, 10000)]
        })
        
        strategies = [
            SamplingStrategy.RANDOM,
            SamplingStrategy.SYSTEMATIC,
            SamplingStrategy.STRATIFIED,
            SamplingStrategy.SPATIAL,
            SamplingStrategy.TEMPORAL
        ]
        
        results = []
        for strategy in strategies:
            config = SamplingConfig(strategy=strategy, target_size=2000)
            result = sampler.sample_data(data, config)
            results.append(result)
        
        # All should produce valid results
        for result in results:
            assert result.sampled_size <= 2000
            assert result.quality_score >= 0
            assert len(result.sampled_data) > 0
        
        # Should have different quality scores
        quality_scores = [r.quality_score for r in results]
        assert len(set(quality_scores)) > 1  # Should have some variation

if __name__ == "__main__":
    pytest.main([__file__])