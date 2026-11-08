"""
Integration tests for Statistics Manager with Dashboard Components
"""

import pytest
import pandas as pd
import numpy as np
import streamlit as st
from datetime import datetime, timedelta
import sys
import os

# Add the parent directory to the path to import components
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from components.statistics_manager import StatisticsManager
from components.layout_manager import DashboardLayout

class TestStatisticsIntegration:
    """Test cases for Statistics Manager integration with dashboard."""
    
    @pytest.fixture
    def stats_manager(self):
        """Create a StatisticsManager instance for testing."""
        return StatisticsManager()
    
    @pytest.fixture
    def layout_manager(self):
        """Create a DashboardLayout instance for testing."""
        return DashboardLayout()
    
    @pytest.fixture
    def sample_dashboard_data(self, layout_manager):
        """Get sample data from layout manager."""
        return layout_manager._get_sample_data()
    
    def test_sample_data_generation(self, layout_manager):
        """Test that sample data is generated correctly."""
        data = layout_manager._get_sample_data()
        
        assert isinstance(data, pd.DataFrame)
        assert len(data) == 200
        assert 'float_id' in data.columns
        assert 'temperature' in data.columns
        assert 'salinity' in data.columns
        assert 'quality_flag' in data.columns
        assert 'date' in data.columns
        
        # Check data types
        assert data['temperature'].dtype in [np.float64, np.float32]
        assert data['salinity'].dtype in [np.float64, np.float32]
        assert data['quality_flag'].dtype in [np.int64, np.int32]
    
    def test_dataset_summary_integration(self, stats_manager, sample_dashboard_data):
        """Test dataset summary with dashboard data."""
        summary = stats_manager.generate_dataset_summary(sample_dashboard_data)
        
        assert isinstance(summary, dict)
        assert summary['total_floats'] == 4  # FLOAT_001 to FLOAT_004
        assert summary['total_profiles'] == 200
        assert summary['total_measurements'] == 200
        
        # Check that all expected parameters are present
        expected_params = ['temperature', 'salinity', 'pressure', 'oxygen', 'chlorophyll', 'ph']
        for param in expected_params:
            assert param in summary['parameters']
        
        # Check geographic coverage
        geo = summary['geographic_coverage']
        assert geo is not None
        assert -60 <= geo['lat_min'] <= geo['lat_max'] <= 60
        assert 40 <= geo['lon_min'] <= geo['lon_max'] <= 120  # Indian Ocean focus
        
        # Check quality overview
        quality = summary['quality_overview']
        assert quality is not None
        assert 'good_data_percentage' in quality
        assert quality['good_data_percentage'] > 80  # Should be high with our sample data
    
    def test_parameter_statistics_integration(self, stats_manager, sample_dashboard_data):
        """Test parameter statistics calculation with dashboard data."""
        # Test temperature statistics
        temp_stats = stats_manager.calculate_parameter_statistics(sample_dashboard_data, 'temperature')
        
        assert len(temp_stats) > 0
        assert 'mean' in temp_stats
        assert 'std' in temp_stats
        assert 'min' in temp_stats
        assert 'max' in temp_stats
        
        # Temperature should be reasonable for ocean data
        assert -5 <= temp_stats['mean'] <= 35  # Reasonable ocean temperature range
        assert temp_stats['std'] > 0
        
        # Test salinity statistics
        sal_stats = stats_manager.calculate_parameter_statistics(sample_dashboard_data, 'salinity')
        
        assert len(sal_stats) > 0
        assert 30 <= sal_stats['mean'] <= 40  # Reasonable salinity range
        
        # Test BGC parameters
        oxygen_stats = stats_manager.calculate_parameter_statistics(sample_dashboard_data, 'oxygen')
        assert len(oxygen_stats) > 0
        assert oxygen_stats['mean'] > 0
    
    def test_data_quality_assessment_integration(self, stats_manager, sample_dashboard_data):
        """Test data quality assessment with dashboard data."""
        assessment = stats_manager.assess_data_quality(sample_dashboard_data)
        
        assert isinstance(assessment, dict)
        assert 'overall_score' in assessment
        assert 1 <= assessment['overall_score'] <= 5
        
        # Check quality flags summary
        flags_summary = assessment['quality_flags_summary']
        assert flags_summary is not None
        assert 'good_data_percentage' in flags_summary
        
        # With our sample data, should have high quality
        assert flags_summary['good_data_percentage'] > 70
        
        # Check missing data analysis
        missing_analysis = assessment['missing_data_analysis']
        assert isinstance(missing_analysis, dict)
        
        # Our sample data shouldn't have missing values
        for param, info in missing_analysis.items():
            assert info['missing_percentage'] == 0.0
        
        # Check outlier analysis
        outlier_analysis = assessment['outlier_analysis']
        assert isinstance(outlier_analysis, dict)
        
        # Should have outlier analysis for numeric parameters
        assert 'temperature' in outlier_analysis
        assert 'salinity' in outlier_analysis
    
    def test_visualization_creation_integration(self, stats_manager, sample_dashboard_data):
        """Test visualization creation with dashboard data."""
        # Test quality flag visualization
        quality_fig = stats_manager.create_quality_flag_visualization(sample_dashboard_data)
        
        assert quality_fig is not None
        assert hasattr(quality_fig, 'data')
        assert len(quality_fig.data) > 0
        assert quality_fig.layout.title.text == "Data Quality Flags Distribution"
        
        # Test statistics summary plot
        parameters = ['temperature', 'salinity', 'oxygen']
        stats_fig = stats_manager.create_statistics_summary_plot(sample_dashboard_data, parameters)
        
        assert stats_fig is not None
        assert hasattr(stats_fig, 'data')
        assert len(stats_fig.data) > 0
        assert stats_fig.layout.title.text == "Parameter Statistics Summary"
    
    def test_comprehensive_workflow(self, stats_manager, layout_manager):
        """Test complete workflow from data generation to statistics display."""
        # Step 1: Generate sample data
        data = layout_manager._get_sample_data()
        assert not data.empty
        
        # Step 2: Generate dataset summary
        summary = stats_manager.generate_dataset_summary(data)
        assert len(summary) > 0
        
        # Step 3: Calculate parameter statistics for all numeric parameters
        numeric_params = ['temperature', 'salinity', 'pressure', 'oxygen', 'chlorophyll', 'ph']
        all_stats = {}
        
        for param in numeric_params:
            stats = stats_manager.calculate_parameter_statistics(data, param)
            if stats:
                all_stats[param] = stats
        
        assert len(all_stats) == len(numeric_params)
        
        # Step 4: Assess data quality
        quality_assessment = stats_manager.assess_data_quality(data)
        assert quality_assessment['overall_score'] > 0
        
        # Step 5: Create visualizations
        quality_viz = stats_manager.create_quality_flag_visualization(data)
        stats_viz = stats_manager.create_statistics_summary_plot(data, numeric_params[:3])
        
        assert quality_viz is not None
        assert stats_viz is not None
        
        # Step 6: Verify all components work together
        assert summary['total_measurements'] == len(data)
        assert len(all_stats) > 0
        assert quality_assessment['overall_score'] >= 1
    
    def test_error_handling_integration(self, stats_manager):
        """Test error handling with various data scenarios."""
        # Test with empty data
        empty_data = pd.DataFrame()
        
        summary = stats_manager.generate_dataset_summary(empty_data)
        assert summary['total_floats'] == 0
        
        assessment = stats_manager.assess_data_quality(empty_data)
        assert assessment['overall_score'] == 0
        
        # Test with invalid parameter
        layout = DashboardLayout()
        valid_data = layout._get_sample_data()
        
        invalid_stats = stats_manager.calculate_parameter_statistics(valid_data, 'nonexistent_param')
        assert len(invalid_stats) == 0
        
        # Test visualization with empty data
        empty_fig = stats_manager.create_quality_flag_visualization(empty_data)
        assert empty_fig is not None
    
    def test_performance_with_large_dataset(self, stats_manager, layout_manager):
        """Test performance with larger dataset."""
        # Temporarily modify sample data generation for larger dataset
        original_method = layout_manager._get_sample_data
        
        def large_sample_data():
            np.random.seed(42)
            n_records = 1000  # Larger dataset
            
            data = {
                'float_id': np.random.choice(['FLOAT_001', 'FLOAT_002', 'FLOAT_003', 'FLOAT_004'], n_records),
                'profile_id': range(1, n_records + 1),
                'latitude': np.random.uniform(-60, 60, n_records),
                'longitude': np.random.uniform(40, 120, n_records),
                'depth': np.random.uniform(0, 2000, n_records),
                'temperature': np.random.normal(15, 8, n_records),
                'salinity': np.random.normal(35, 3, n_records),
                'pressure': np.random.uniform(0, 2000, n_records),
                'oxygen': np.random.normal(200, 50, n_records),
                'chlorophyll': np.random.exponential(0.5, n_records),
                'ph': np.random.normal(8.1, 0.2, n_records),
                'quality_flag': np.random.choice([1, 2, 3, 4, 9], n_records, p=[0.7, 0.15, 0.08, 0.05, 0.02]),
                'date': [datetime.now() - timedelta(days=int(x)) for x in np.random.randint(0, 365, n_records)]
            }
            
            return pd.DataFrame(data)
        
        # Test with larger dataset
        large_data = large_sample_data()
        
        # All operations should complete without errors
        summary = stats_manager.generate_dataset_summary(large_data)
        assert summary['total_measurements'] == 1000
        
        assessment = stats_manager.assess_data_quality(large_data)
        assert assessment['overall_score'] > 0
        
        temp_stats = stats_manager.calculate_parameter_statistics(large_data, 'temperature')
        assert len(temp_stats) > 0

if __name__ == "__main__":
    pytest.main([__file__])