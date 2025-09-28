"""
Unit tests for Export Manager Component
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
import json
import io
from components.export_manager import ExportManager

class TestExportManager:
    """Test cases for ExportManager class"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Mock API client
        self.mock_api_client = Mock()
        self.export_manager = ExportManager(self.mock_api_client)
        
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
            'salinity': [35.2, 35.1, 35.0, 34.9, 34.8]
        })
    
    def test_init(self):
        """Test export manager initialization"""
        assert self.export_manager.api_client == self.mock_api_client
        assert self.export_manager.config is not None
        assert 'visualization' in self.export_manager.supported_formats
        assert 'data' in self.export_manager.supported_formats
        assert 'report' in self.export_manager.supported_formats
    
    def test_init_without_api_client(self):
        """Test initialization without API client"""
        export_manager = ExportManager(None)
        assert export_manager.api_client is None
    
    def test_supported_formats(self):
        """Test supported export formats"""
        formats = self.export_manager.supported_formats
        
        # Check visualization formats
        viz_formats = formats['visualization']
        assert 'PNG' in viz_formats
        assert 'PDF' in viz_formats
        assert 'SVG' in viz_formats
        assert 'HTML' in viz_formats
        
        # Check data formats
        data_formats = formats['data']
        assert 'CSV' in data_formats
        assert 'JSON' in data_formats
        assert 'ASCII' in data_formats
        assert 'NetCDF' in data_formats
        
        # Check report formats
        report_formats = formats['report']
        assert 'PDF' in report_formats
        assert 'HTML' in report_formats
    
    def test_get_available_visualizations(self):
        """Test getting available visualizations"""
        viz_list = self.export_manager._get_available_visualizations()
        
        assert isinstance(viz_list, list)
        assert len(viz_list) > 0
        assert all(isinstance(viz, str) for viz in viz_list)
        
        # Check for expected visualization types
        viz_names = ' '.join(viz_list).lower()
        assert 'map' in viz_names
        assert 'profile' in viz_names or 'temperature' in viz_names
    
    def test_create_sample_export_data(self):
        """Test sample data creation"""
        sample_data = self.export_manager._create_sample_export_data()
        
        assert isinstance(sample_data, pd.DataFrame)
        assert not sample_data.empty
        assert len(sample_data) > 0
        
        # Check for expected columns
        expected_cols = ['id', 'float_id', 'time', 'lat', 'lon', 'depth', 'temperature', 'salinity']
        for col in expected_cols:
            assert col in sample_data.columns
        
        # Check data types and ranges
        assert sample_data['lat'].between(-90, 90).all()
        assert sample_data['lon'].between(-180, 180).all()
        assert sample_data['depth'].min() >= 0
        assert sample_data['temperature'].between(-5, 40).all()
        assert sample_data['salinity'].between(30, 40).all()
    
    def test_create_sample_visualization(self):
        """Test sample visualization creation"""
        viz_types = ['Float Location Map', 'Temperature Profile', 'Salinity Profile', 'Generic Chart']
        
        for viz_type in viz_types:
            fig = self.export_manager._create_sample_visualization(viz_type)
            
            # Check that a valid Plotly figure is created
            assert hasattr(fig, 'data')
            assert hasattr(fig, 'layout')
            assert len(fig.data) > 0
            assert fig.layout.title.text == viz_type
    
    def test_create_export_metadata(self):
        """Test export metadata creation"""
        export_type = "data"
        details = {
            "format": "CSV",
            "record_count": 100,
            "export_time": datetime.now().isoformat()
        }
        
        metadata = self.export_manager._create_export_metadata(export_type, details)
        
        assert isinstance(metadata, dict)
        assert metadata['export_type'] == export_type
        assert 'export_timestamp' in metadata
        assert 'dashboard_version' in metadata
        assert 'data_source' in metadata
        assert metadata['export_details'] == details
        assert 'system_info' in metadata
    
    def test_create_quality_report(self):
        """Test quality report creation"""
        quality_report = self.export_manager._create_quality_report(self.sample_data)
        
        assert isinstance(quality_report, str)
        assert len(quality_report) > 0
        assert 'Quality Report' in quality_report
        assert 'Total Records' in quality_report
        assert 'Data Completeness' in quality_report
        
        # Check that it includes information about each column
        for col in self.sample_data.columns:
            assert col in quality_report
    
    def test_create_report_content(self):
        """Test HTML report content creation"""
        options = {
            "custom_title": "Test Report",
            "custom_author": "Test Author",
            "include_overview": True,
            "include_data_summary": True,
            "include_quality_assessment": True
        }
        
        html_content = self.export_manager._create_report_content(options)
        
        assert isinstance(html_content, str)
        assert len(html_content) > 0
        assert '<!DOCTYPE html>' in html_content
        assert options['custom_title'] in html_content
        assert options['custom_author'] in html_content
        
        # Check for included sections
        if options['include_overview']:
            assert 'System Overview' in html_content
        if options['include_data_summary']:
            assert 'Data Summary' in html_content
        if options['include_quality_assessment']:
            assert 'Quality Assessment' in html_content
    
    def test_get_export_data_empty_source(self):
        """Test getting export data with empty source"""
        with patch('streamlit.session_state') as mock_session_state:
            mock_session_state.get.return_value = None
            
            result = self.export_manager._get_export_data("Current Filtered Data")
            assert result is None
    
    def test_get_export_data_sample_fallback(self):
        """Test getting export data with sample fallback"""
        # Test when API client is available but returns sample data
        result = self.export_manager._get_export_data("All Available Data")
        
        if result is not None:
            assert isinstance(result, pd.DataFrame)
            assert not result.empty
    
    @patch('streamlit.session_state')
    def test_get_export_data_filtered(self, mock_session_state):
        """Test getting filtered export data"""
        mock_session_state.get.return_value = self.sample_data
        
        result = self.export_manager._get_export_data("Current Filtered Data")
        
        assert result is not None
        assert isinstance(result, pd.DataFrame)
        pd.testing.assert_frame_equal(result, self.sample_data)
    
    def test_data_validation_in_quality_report(self):
        """Test data validation in quality report"""
        # Create data with some quality issues
        problematic_data = self.sample_data.copy()
        problematic_data.loc[0, 'temperature'] = np.nan  # Missing value
        problematic_data.loc[1, 'lat'] = 95.0  # Invalid latitude
        
        quality_report = self.export_manager._create_quality_report(problematic_data)
        
        # Should handle missing values gracefully
        assert 'temperature' in quality_report
        assert 'complete' in quality_report.lower()
    
    def test_metadata_structure(self):
        """Test metadata structure consistency"""
        test_cases = [
            ("visualization", {"format": "PNG", "resolution": (800, 600)}),
            ("data", {"format": "CSV", "compression": "ZIP"}),
            ("report", {"format": "HTML", "template": "Government"})
        ]
        
        for export_type, details in test_cases:
            metadata = self.export_manager._create_export_metadata(export_type, details)
            
            # Check required fields
            required_fields = ['export_type', 'export_timestamp', 'dashboard_version', 
                             'data_source', 'export_details', 'system_info']
            
            for field in required_fields:
                assert field in metadata, f"Missing required field: {field}"
            
            assert metadata['export_type'] == export_type
            assert metadata['export_details'] == details
    
    def test_visualization_creation_robustness(self):
        """Test visualization creation with various inputs"""
        test_viz_names = [
            "Float Location Map",
            "Temperature Profile", 
            "Salinity Profile",
            "T-S Diagram",
            "BGC Parameters",
            "Unknown Visualization Type"
        ]
        
        for viz_name in test_viz_names:
            try:
                fig = self.export_manager._create_sample_visualization(viz_name)
                
                # Basic validation
                assert fig is not None
                assert hasattr(fig, 'data')
                assert hasattr(fig, 'layout')
                
            except Exception as e:
                pytest.fail(f"Visualization creation failed for '{viz_name}': {e}")
    
    def test_report_content_customization(self):
        """Test report content customization options"""
        base_options = {
            "custom_title": "Custom Title",
            "custom_author": "Custom Author",
            "include_overview": False,
            "include_data_summary": False,
            "include_quality_assessment": False
        }
        
        # Test with no sections included
        html_content = self.export_manager._create_report_content(base_options)
        assert 'Custom Title' in html_content
        assert 'Custom Author' in html_content
        assert 'System Overview' not in html_content
        
        # Test with all sections included
        all_sections_options = base_options.copy()
        all_sections_options.update({
            "include_overview": True,
            "include_data_summary": True,
            "include_quality_assessment": True
        })
        
        html_content_full = self.export_manager._create_report_content(all_sections_options)
        assert 'System Overview' in html_content_full
        assert 'Data Summary' in html_content_full
        assert 'Quality Assessment' in html_content_full
    
    def test_sample_data_consistency(self):
        """Test that sample data generation is consistent"""
        # Generate sample data multiple times
        data1 = self.export_manager._create_sample_export_data()
        data2 = self.export_manager._create_sample_export_data()
        
        # Should be identical due to fixed random seed
        pd.testing.assert_frame_equal(data1, data2)
        
        # Check data quality
        assert not data1.isnull().all().any()  # No completely null columns
        assert len(data1) > 0  # Has data
        assert len(data1.columns) > 5  # Has multiple columns

if __name__ == "__main__":
    pytest.main([__file__])