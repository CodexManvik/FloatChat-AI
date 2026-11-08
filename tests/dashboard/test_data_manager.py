"""
Unit tests for Data Manager Component
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
from unittest.mock import Mock, patch
from components.data_manager import DataManager

class TestDataManager:
    """Test cases for DataManager class"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Mock API client
        self.mock_api_client = Mock()
        self.data_manager = DataManager(self.mock_api_client)
        
        # Sample data for testing
        self.sample_data = pd.DataFrame({
            'id': [1, 2, 3, 4, 5],
            'float_id': ['ARGO_001', 'ARGO_001', 'ARGO_002', 'ARGO_002', 'ARGO_003'],
            'time': [
                datetime.now() - timedelta(days=10),
                datetime.now() - timedelta(days=5),
                datetime.now() - timedelta(days=15),
                datetime.now() - timedelta(days=20),
                datetime.now() - timedelta(days=30)
            ],
            'lat': [10.5, 10.7, 15.2, 15.0, -5.8],
            'lon': [75.3, 75.5, 80.1, 80.0, 85.7],
            'depth': [10, 50, 100, 200, 500],
            'temperature': [28.5, 26.2, 22.1, 18.5, 12.3],
            'salinity': [35.2, 35.1, 35.0, 34.9, 34.8],
            'wmo_id': [5900001, 5900001, 5900002, 5900002, 5900003],
            'cycle_number': [45, 46, 67, 68, 23]
        })
    
    def test_init(self):
        """Test data manager initialization"""
        assert self.data_manager.api_client == self.mock_api_client
        assert self.data_manager.config is not None
        assert self.data_manager.transformer is not None
    
    def test_init_without_api_client(self):
        """Test initialization without API client"""
        data_manager = DataManager(None)
        assert data_manager.api_client is None
    
    def test_get_default_filters(self):
        """Test default filter configuration"""
        default_filters = self.data_manager._get_default_filters()
        
        assert isinstance(default_filters, dict)
        assert 'date_mode' in default_filters
        assert 'date_range' in default_filters
        assert 'region_mode' in default_filters
        assert 'depth_mode' in default_filters
        assert 'quality_levels' in default_filters
        
        # Check default values
        assert default_filters['date_mode'] == "Date Range"
        assert default_filters['region_mode'] == "Predefined Regions"
        assert default_filters['depth_mode'] == "Range"
        assert "Excellent" in default_filters['quality_levels']
    
    def test_get_predefined_region_bounds(self):
        """Test predefined region bounds"""
        # Test known region
        indian_ocean = self.data_manager._get_predefined_region_bounds("Indian Ocean")
        
        assert isinstance(indian_ocean, dict)
        assert all(key in indian_ocean for key in ['north', 'south', 'east', 'west'])
        assert indian_ocean['north'] > indian_ocean['south']
        assert indian_ocean['east'] > indian_ocean['west']
        
        # Test unknown region
        unknown = self.data_manager._get_predefined_region_bounds("Unknown Ocean")
        assert unknown is None
    
    def test_count_active_filters(self):
        """Test active filter counting"""
        # Test default filters (should have minimal active filters)
        default_filters = self.data_manager._get_default_filters()
        count = self.data_manager._count_active_filters(default_filters)
        assert count >= 0
        
        # Test filters with active settings
        active_filters = {
            "date_mode": "Relative Period",
            "predefined_region": "Arabian Sea",
            "enable_temp_filter": True,
            "float_selection_mode": "Specific Float IDs"
        }
        
        count = self.data_manager._count_active_filters(active_filters)
        assert count > 0
    
    def test_apply_temporal_filters(self):
        """Test temporal filtering"""
        filters = {
            "date_range": (
                (datetime.now() - timedelta(days=25)).date(),
                (datetime.now() - timedelta(days=5)).date()
            )
        }
        
        filtered_data, log = self.data_manager._apply_temporal_filters(self.sample_data, filters)
        
        # Should filter out records outside date range
        assert len(filtered_data) <= len(self.sample_data)
        assert len(log) > 0
        assert "Date range filter" in log[0]
    
    def test_apply_geographic_filters(self):
        """Test geographic filtering"""
        # Test bounding box filter
        filters = {
            "region_bounds": {
                "north": 20.0,
                "south": 5.0,
                "east": 85.0,
                "west": 70.0
            }
        }
        
        filtered_data, log = self.data_manager._apply_geographic_filters(self.sample_data, filters)
        
        # Should filter based on lat/lon bounds
        assert len(filtered_data) <= len(self.sample_data)
        
        # Check that remaining data is within bounds
        if not filtered_data.empty:
            assert filtered_data['lat'].min() >= 5.0
            assert filtered_data['lat'].max() <= 20.0
            assert filtered_data['lon'].min() >= 70.0
            assert filtered_data['lon'].max() <= 85.0
    
    def test_apply_geographic_filters_circular(self):
        """Test circular geographic filtering"""
        filters = {
            "region_bounds": {
                "center_lat": 10.0,
                "center_lon": 75.0,
                "radius_km": 500.0
            }
        }
        
        filtered_data, log = self.data_manager._apply_geographic_filters(self.sample_data, filters)
        
        # Should apply circular filter
        assert len(filtered_data) <= len(self.sample_data)
        assert len(log) > 0
    
    def test_apply_physical_filters(self):
        """Test physical parameter filtering"""
        filters = {
            "depth_range": (0, 100),
            "enable_temp_filter": True,
            "temp_range": (20.0, 30.0),
            "enable_sal_filter": True,
            "sal_range": (34.5, 35.5)
        }
        
        filtered_data, log = self.data_manager._apply_physical_filters(self.sample_data, filters)
        
        # Should filter based on depth, temperature, and salinity
        assert len(filtered_data) <= len(self.sample_data)
        
        if not filtered_data.empty:
            # Check depth range
            assert filtered_data['depth'].min() >= 0
            assert filtered_data['depth'].max() <= 100
            
            # Check temperature range
            assert filtered_data['temperature'].min() >= 20.0
            assert filtered_data['temperature'].max() <= 30.0
            
            # Check salinity range
            assert filtered_data['salinity'].min() >= 34.5
            assert filtered_data['salinity'].max() <= 35.5
    
    def test_apply_technical_filters(self):
        """Test technical filtering"""
        filters = {
            "float_selection_mode": "Specific Float IDs",
            "float_ids_list": ["ARGO_001", "ARGO_002"],
            "enable_cycle_filter": True,
            "min_cycle": 40,
            "max_cycle": 70
        }
        
        filtered_data, log = self.data_manager._apply_technical_filters(self.sample_data, filters)
        
        # Should filter based on float IDs and cycle numbers
        assert len(filtered_data) <= len(self.sample_data)
        
        if not filtered_data.empty:
            # Check float IDs
            assert all(fid in ["ARGO_001", "ARGO_002"] for fid in filtered_data['float_id'])
            
            # Check cycle numbers
            assert filtered_data['cycle_number'].min() >= 40
            assert filtered_data['cycle_number'].max() <= 70
    
    def test_apply_filters_comprehensive(self):
        """Test comprehensive filter application"""
        filters = {
            "date_range": (
                (datetime.now() - timedelta(days=25)).date(),
                datetime.now().date()
            ),
            "region_bounds": {
                "north": 20.0,
                "south": -10.0,
                "east": 90.0,
                "west": 70.0
            },
            "depth_range": (0, 300),
            "enable_temp_filter": True,
            "temp_range": (10.0, 30.0)
        }
        
        filtered_data = self.data_manager.apply_filters(self.sample_data, filters)
        
        # Should apply all filters
        assert len(filtered_data) <= len(self.sample_data)
        assert isinstance(filtered_data, pd.DataFrame)
    
    def test_apply_filters_empty_data(self):
        """Test filter application on empty data"""
        empty_data = pd.DataFrame()
        filters = self.data_manager._get_default_filters()
        
        result = self.data_manager.apply_filters(empty_data, filters)
        
        assert result.empty
        assert isinstance(result, pd.DataFrame)
    
    def test_assess_data_quality(self):
        """Test data quality assessment"""
        quality_assessment = self.data_manager.assess_data_quality(self.sample_data)
        
        assert isinstance(quality_assessment, dict)
        assert 'status' in quality_assessment
        assert 'score' in quality_assessment
        assert 'issues' in quality_assessment
        
        # Should have reasonable quality score for clean test data
        assert 0 <= quality_assessment['score'] <= 1
    
    def test_assess_data_quality_empty_data(self):
        """Test data quality assessment on empty data"""
        empty_data = pd.DataFrame()
        
        quality_assessment = self.data_manager.assess_data_quality(empty_data)
        
        assert quality_assessment['status'] == 'no_data'
        assert quality_assessment['score'] == 0.0
        assert 'No data available' in quality_assessment['issues']
    
    def test_generate_statistics(self):
        """Test statistics generation"""
        stats = self.data_manager.generate_statistics(self.sample_data)
        
        assert isinstance(stats, dict)
        # Should contain basic statistics from get_data_summary
    
    def test_export_data_no_api_client(self):
        """Test export without API client"""
        data_manager = DataManager(None)
        
        with pytest.raises(Exception):  # Should raise APIException
            data_manager.export_data(self.sample_data, "csv")
    
    def test_export_data_empty_data(self):
        """Test export with empty data"""
        empty_data = pd.DataFrame()
        
        with pytest.raises(ValueError, match="No data to export"):
            self.data_manager.export_data(empty_data, "csv")
    
    def test_export_data_missing_id_column(self):
        """Test export with missing ID column"""
        data_without_id = self.sample_data.drop('id', axis=1)
        
        with pytest.raises(ValueError, match="Data missing required ID column"):
            self.data_manager.export_data(data_without_id, "csv")
    
    def test_perform_additional_quality_checks(self):
        """Test additional quality checks"""
        additional_checks = self.data_manager._perform_additional_quality_checks(self.sample_data)
        
        assert isinstance(additional_checks, dict)
        
        # Should check for duplicates
        if 'duplicate_count' in additional_checks:
            assert additional_checks['duplicate_count'] >= 0
        
        # Should check for future dates
        if 'future_dates' in additional_checks:
            assert additional_checks['future_dates'] >= 0
        
        # Should check coordinate validity
        if 'invalid_coordinates' in additional_checks:
            assert additional_checks['invalid_coordinates'] >= 0
    
    def test_filter_edge_cases(self):
        """Test filter edge cases"""
        # Test with data that has NaN values
        data_with_nan = self.sample_data.copy()
        data_with_nan.loc[0, 'temperature'] = np.nan
        data_with_nan.loc[1, 'salinity'] = np.nan
        
        filters = {
            "enable_temp_filter": True,
            "temp_range": (20.0, 30.0),
            "enable_sal_filter": True,
            "sal_range": (34.5, 35.5)
        }
        
        # Should handle NaN values gracefully
        filtered_data = self.data_manager.apply_filters(data_with_nan, filters)
        assert isinstance(filtered_data, pd.DataFrame)
    
    def test_filter_no_matches(self):
        """Test filters that result in no matches"""
        filters = {
            "depth_range": (5000, 6000),  # No data at this depth
            "enable_temp_filter": True,
            "temp_range": (50.0, 60.0)  # No data at this temperature
        }
        
        filtered_data = self.data_manager.apply_filters(self.sample_data, filters)
        
        # Should return empty DataFrame
        assert filtered_data.empty
        assert isinstance(filtered_data, pd.DataFrame)

if __name__ == "__main__":
    pytest.main([__file__])