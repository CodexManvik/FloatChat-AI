"""
Unit tests for Statistics Manager Component
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

# Add the parent directory to the path to import components
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from components.statistics_manager import StatisticsManager

class TestStatisticsManager:
    """Test cases for StatisticsManager class."""
    
    @pytest.fixture
    def stats_manager(self):
        """Create a StatisticsManager instance for testing."""
        return StatisticsManager()
    
    @pytest.fixture
    def sample_data(self):
        """Create sample ARGO data for testing."""
        np.random.seed(42)
        n_records = 100
        
        data = {
            'float_id': np.random.choice(['FLOAT_001', 'FLOAT_002', 'FLOAT_003'], n_records),
            'profile_id': range(1, n_records + 1),
            'latitude': np.random.uniform(-60, 60, n_records),
            'longitude': np.random.uniform(-180, 180, n_records),
            'depth': np.random.uniform(0, 2000, n_records),
            'temperature': np.random.normal(15, 5, n_records),
            'salinity': np.random.normal(35, 2, n_records),
            'pressure': np.random.uniform(0, 2000, n_records),
            'quality_flag': np.random.choice([1, 2, 3, 4, 9], n_records, p=[0.6, 0.2, 0.1, 0.05, 0.05]),
            'date': [datetime.now() - timedelta(days=x) for x in range(n_records)]
        }
        
        return pd.DataFrame(data)
    
    @pytest.fixture
    def empty_data(self):
        """Create empty DataFrame for testing."""
        return pd.DataFrame()
    
    def test_initialization(self, stats_manager):
        """Test StatisticsManager initialization."""
        assert isinstance(stats_manager, StatisticsManager)
        assert hasattr(stats_manager, 'quality_flags')
        assert hasattr(stats_manager, 'quality_colors')
        assert len(stats_manager.quality_flags) == 10
        assert len(stats_manager.quality_colors) == 10
    
    def test_generate_dataset_summary_with_data(self, stats_manager, sample_data):
        """Test dataset summary generation with valid data."""
        summary = stats_manager.generate_dataset_summary(sample_data)
        
        assert isinstance(summary, dict)
        assert 'total_floats' in summary
        assert 'total_profiles' in summary
        assert 'total_measurements' in summary
        assert 'date_range' in summary
        assert 'geographic_coverage' in summary
        assert 'depth_coverage' in summary
        assert 'parameters' in summary
        assert 'quality_overview' in summary
        
        # Check values
        assert summary['total_floats'] == 3  # FLOAT_001, FLOAT_002, FLOAT_003
        assert summary['total_profiles'] == 100
        assert summary['total_measurements'] == 100
        
        # Check date range
        assert summary['date_range'] is not None
        assert 'start' in summary['date_range']
        assert 'end' in summary['date_range']
        assert 'span_days' in summary['date_range']
        
        # Check geographic coverage
        geo = summary['geographic_coverage']
        assert geo is not None
        assert -60 <= geo['lat_min'] <= geo['lat_max'] <= 60
        assert -180 <= geo['lon_min'] <= geo['lon_max'] <= 180
        
        # Check parameters
        expected_params = ['temperature', 'salinity', 'pressure']
        for param in expected_params:
            assert param in summary['parameters']
    
    def test_generate_dataset_summary_empty_data(self, stats_manager, empty_data):
        """Test dataset summary generation with empty data."""
        summary = stats_manager.generate_dataset_summary(empty_data)
        
        assert isinstance(summary, dict)
        assert summary['total_floats'] == 0
        assert summary['total_profiles'] == 0
        assert summary['total_measurements'] == 0
        assert summary['date_range'] is None
        assert summary['geographic_coverage'] is None
        assert summary['depth_coverage'] is None
        assert summary['parameters'] == []
    
    def test_calculate_parameter_statistics_valid(self, stats_manager, sample_data):
        """Test parameter statistics calculation with valid data."""
        stats = stats_manager.calculate_parameter_statistics(sample_data, 'temperature')
        
        assert isinstance(stats, dict)
        assert 'count' in stats
        assert 'mean' in stats
        assert 'median' in stats
        assert 'std' in stats
        assert 'min' in stats
        assert 'max' in stats
        assert 'q25' in stats
        assert 'q75' in stats
        assert 'range' in stats
        assert 'coefficient_of_variation' in stats
        
        # Check that values are reasonable
        assert stats['count'] == 100
        assert stats['min'] <= stats['q25'] <= stats['median'] <= stats['q75'] <= stats['max']
        assert stats['range'] == stats['max'] - stats['min']
        assert stats['coefficient_of_variation'] >= 0
    
    def test_calculate_parameter_statistics_invalid(self, stats_manager, sample_data):
        """Test parameter statistics calculation with invalid parameter."""
        stats = stats_manager.calculate_parameter_statistics(sample_data, 'nonexistent_parameter')
        
        assert isinstance(stats, dict)
        assert len(stats) == 0
    
    def test_calculate_parameter_statistics_empty_data(self, stats_manager, empty_data):
        """Test parameter statistics calculation with empty data."""
        stats = stats_manager.calculate_parameter_statistics(empty_data, 'temperature')
        
        assert isinstance(stats, dict)
        assert len(stats) == 0
    
    def test_assess_data_quality_with_flags(self, stats_manager, sample_data):
        """Test data quality assessment with quality flags."""
        assessment = stats_manager.assess_data_quality(sample_data)
        
        assert isinstance(assessment, dict)
        assert 'overall_score' in assessment
        assert 'issues' in assessment
        assert 'recommendations' in assessment
        assert 'quality_flags_summary' in assessment
        assert 'missing_data_analysis' in assessment
        assert 'outlier_analysis' in assessment
        
        # Check overall score
        assert 1 <= assessment['overall_score'] <= 5
        
        # Check quality flags summary
        flags_summary = assessment['quality_flags_summary']
        assert 'flag_distribution' in flags_summary
        assert 'good_data_percentage' in flags_summary
        assert 'bad_data_percentage' in flags_summary
        
        # Check that percentages are valid
        assert 0 <= flags_summary['good_data_percentage'] <= 100
        assert 0 <= flags_summary['bad_data_percentage'] <= 100
    
    def test_assess_data_quality_empty_data(self, stats_manager, empty_data):
        """Test data quality assessment with empty data."""
        assessment = stats_manager.assess_data_quality(empty_data)
        
        assert isinstance(assessment, dict)
        assert assessment['overall_score'] == 0
        assert len(assessment['issues']) > 0
        assert "No data available" in assessment['issues'][0]
    
    def test_assess_data_quality_no_flags(self, stats_manager):
        """Test data quality assessment without quality flags."""
        # Create data without quality flags
        data = pd.DataFrame({
            'temperature': np.random.normal(15, 5, 50),
            'salinity': np.random.normal(35, 2, 50)
        })
        
        assessment = stats_manager.assess_data_quality(data)
        
        assert isinstance(assessment, dict)
        assert 'missing_data_analysis' in assessment
        assert 'outlier_analysis' in assessment
    
    def test_create_quality_flag_visualization_with_flags(self, stats_manager, sample_data):
        """Test quality flag visualization creation with valid data."""
        fig = stats_manager.create_quality_flag_visualization(sample_data)
        
        assert fig is not None
        assert hasattr(fig, 'data')
        assert len(fig.data) > 0
        assert fig.layout.title.text == "Data Quality Flags Distribution"
    
    def test_create_quality_flag_visualization_no_flags(self, stats_manager):
        """Test quality flag visualization creation without quality flags."""
        data = pd.DataFrame({
            'temperature': np.random.normal(15, 5, 50)
        })
        
        fig = stats_manager.create_quality_flag_visualization(data)
        
        assert fig is not None
        assert fig.layout.title.text == "Data Quality Flags Distribution"
    
    def test_create_statistics_summary_plot_valid(self, stats_manager, sample_data):
        """Test statistics summary plot creation with valid data."""
        parameters = ['temperature', 'salinity', 'pressure']
        fig = stats_manager.create_statistics_summary_plot(sample_data, parameters)
        
        assert fig is not None
        assert hasattr(fig, 'data')
        assert len(fig.data) > 0
        assert fig.layout.title.text == "Parameter Statistics Summary"
    
    def test_create_statistics_summary_plot_empty_params(self, stats_manager, sample_data):
        """Test statistics summary plot creation with empty parameters."""
        fig = stats_manager.create_statistics_summary_plot(sample_data, [])
        
        assert fig is not None
        # Should have annotation about no parameters
        assert len(fig.layout.annotations) > 0
    
    def test_create_statistics_summary_plot_invalid_params(self, stats_manager, sample_data):
        """Test statistics summary plot creation with invalid parameters."""
        parameters = ['nonexistent_param1', 'nonexistent_param2']
        fig = stats_manager.create_statistics_summary_plot(sample_data, parameters)
        
        assert fig is not None
        # Should have annotation about no valid statistics
        assert len(fig.layout.annotations) > 0
    
    def test_missing_data_analysis(self, stats_manager):
        """Test missing data analysis functionality."""
        # Create data with missing values
        data = pd.DataFrame({
            'temperature': [15.0, np.nan, 16.0, np.nan, 17.0],
            'salinity': [35.0, 36.0, np.nan, np.nan, 37.0],
            'pressure': [10.0, 11.0, 12.0, 13.0, 14.0]
        })
        
        assessment = stats_manager.assess_data_quality(data)
        missing_analysis = assessment['missing_data_analysis']
        
        assert 'temperature' in missing_analysis
        assert 'salinity' in missing_analysis
        assert 'pressure' in missing_analysis
        
        # Check temperature (2 missing out of 5 = 40%)
        temp_missing = missing_analysis['temperature']
        assert temp_missing['missing_count'] == 2
        assert temp_missing['missing_percentage'] == 40.0
        
        # Check salinity (2 missing out of 5 = 40%)
        sal_missing = missing_analysis['salinity']
        assert sal_missing['missing_count'] == 2
        assert sal_missing['missing_percentage'] == 40.0
        
        # Check pressure (0 missing)
        press_missing = missing_analysis['pressure']
        assert press_missing['missing_count'] == 0
        assert press_missing['missing_percentage'] == 0.0
    
    def test_outlier_detection(self, stats_manager):
        """Test outlier detection functionality."""
        # Create data with known outliers
        normal_data = np.random.normal(15, 1, 95)  # Normal temperature data
        outliers = [50, -10, 100, -50, 200]  # Clear outliers
        temperature_data = np.concatenate([normal_data, outliers])
        
        data = pd.DataFrame({
            'temperature': temperature_data,
            'salinity': np.random.normal(35, 1, 100)  # Normal salinity data
        })
        
        assessment = stats_manager.assess_data_quality(data)
        outlier_analysis = assessment['outlier_analysis']
        
        assert 'temperature' in outlier_analysis
        temp_outliers = outlier_analysis['temperature']
        
        # Should detect the 5 outliers we added
        assert temp_outliers['outlier_count'] >= 5
        assert temp_outliers['outlier_percentage'] >= 5.0
        
        # Should have bounds
        assert 'lower_bound' in temp_outliers
        assert 'upper_bound' in temp_outliers
    
    def test_quality_score_calculation(self, stats_manager):
        """Test quality score calculation based on good data percentage."""
        # Test high quality data (90% good)
        high_quality_flags = [1] * 90 + [4] * 10
        data_high = pd.DataFrame({'quality_flag': high_quality_flags})
        assessment_high = stats_manager.assess_data_quality(data_high)
        assert assessment_high['overall_score'] == 5
        
        # Test medium quality data (75% good)
        medium_quality_flags = [1] * 75 + [4] * 25
        data_medium = pd.DataFrame({'quality_flag': medium_quality_flags})
        assessment_medium = stats_manager.assess_data_quality(data_medium)
        assert assessment_medium['overall_score'] == 3
        
        # Test low quality data (50% good)
        low_quality_flags = [1] * 50 + [4] * 50
        data_low = pd.DataFrame({'quality_flag': low_quality_flags})
        assessment_low = stats_manager.assess_data_quality(data_low)
        assert assessment_low['overall_score'] <= 2

if __name__ == "__main__":
    pytest.main([__file__])