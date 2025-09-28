"""
Simple test script for export manager component
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock

def test_export_manager_imports():
    """Test that export manager components can be imported"""
    try:
        from components.export_manager import ExportManager
        print("✅ ExportManager imported successfully")
        
        # Test with mock API client
        mock_api = Mock()
        export_manager = ExportManager(mock_api)
        print("✅ ExportManager instantiated successfully")
        
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_supported_formats():
    """Test supported export formats"""
    try:
        from components.export_manager import ExportManager
        
        export_manager = ExportManager(None)
        formats = export_manager.supported_formats
        
        print("✅ Supported formats loaded successfully")
        
        for category, format_list in formats.items():
            print(f"   {category}: {', '.join(format_list)}")
        
        # Validate format categories
        assert 'visualization' in formats
        assert 'data' in formats
        assert 'report' in formats
        
        # Validate specific formats
        assert 'PNG' in formats['visualization']
        assert 'CSV' in formats['data']
        assert 'PDF' in formats['report']
        
        print("✅ All expected formats present")
        
        return True
    except Exception as e:
        print(f"❌ Error testing supported formats: {e}")
        return False

def test_sample_data_creation():
    """Test sample data creation for export"""
    try:
        from components.export_manager import ExportManager
        
        export_manager = ExportManager(None)
        sample_data = export_manager._create_sample_export_data()
        
        print("✅ Sample export data created successfully")
        print(f"   Records: {len(sample_data)}")
        print(f"   Columns: {len(sample_data.columns)}")
        print(f"   Columns: {list(sample_data.columns)}")
        
        # Validate data structure
        expected_columns = ['id', 'float_id', 'time', 'lat', 'lon', 'depth', 'temperature', 'salinity']
        for col in expected_columns:
            assert col in sample_data.columns, f"Missing column: {col}"
        
        # Validate data ranges
        assert sample_data['lat'].between(-90, 90).all(), "Invalid latitude values"
        assert sample_data['lon'].between(-180, 180).all(), "Invalid longitude values"
        assert sample_data['depth'].min() >= 0, "Invalid depth values"
        
        print("✅ Data validation passed")
        
        return True
    except Exception as e:
        print(f"❌ Error testing sample data creation: {e}")
        return False

def test_visualization_creation():
    """Test sample visualization creation"""
    try:
        from components.export_manager import ExportManager
        
        export_manager = ExportManager(None)
        
        # Test different visualization types
        viz_types = [
            "Float Location Map",
            "Temperature Profile", 
            "Salinity Profile",
            "Generic Chart"
        ]
        
        for viz_type in viz_types:
            fig = export_manager._create_sample_visualization(viz_type)
            
            print(f"✅ Created {viz_type} visualization")
            
            # Basic validation
            assert hasattr(fig, 'data'), f"Figure missing data for {viz_type}"
            assert hasattr(fig, 'layout'), f"Figure missing layout for {viz_type}"
            assert len(fig.data) > 0, f"Figure has no data traces for {viz_type}"
            assert fig.layout.title.text == viz_type, f"Incorrect title for {viz_type}"
        
        print("✅ All visualization types created successfully")
        
        return True
    except Exception as e:
        print(f"❌ Error testing visualization creation: {e}")
        return False

def test_metadata_creation():
    """Test export metadata creation"""
    try:
        from components.export_manager import ExportManager
        
        export_manager = ExportManager(None)
        
        # Test different export types
        test_cases = [
            ("visualization", {"format": "PNG", "resolution": (800, 600)}),
            ("data", {"format": "CSV", "record_count": 100}),
            ("report", {"format": "HTML", "template": "Government"})
        ]
        
        for export_type, details in test_cases:
            metadata = export_manager._create_export_metadata(export_type, details)
            
            print(f"✅ Created metadata for {export_type} export")
            
            # Validate metadata structure
            required_fields = ['export_type', 'export_timestamp', 'dashboard_version', 
                             'data_source', 'export_details', 'system_info']
            
            for field in required_fields:
                assert field in metadata, f"Missing metadata field: {field}"
            
            assert metadata['export_type'] == export_type
            assert metadata['export_details'] == details
        
        print("✅ All metadata structures validated")
        
        return True
    except Exception as e:
        print(f"❌ Error testing metadata creation: {e}")
        return False

def test_quality_report_creation():
    """Test data quality report creation"""
    try:
        from components.export_manager import ExportManager
        
        export_manager = ExportManager(None)
        
        # Create test data with some quality issues
        test_data = pd.DataFrame({
            'id': [1, 2, 3, 4, 5],
            'temperature': [25.5, np.nan, 22.1, 18.5, 12.3],  # Missing value
            'salinity': [35.2, 35.1, np.nan, 34.9, 34.8],     # Missing value
            'lat': [10.5, 10.7, 15.2, 15.0, -5.8],
            'lon': [75.3, 75.5, 80.1, 80.0, 85.7],
            'depth': [10, 50, 100, 200, 500]
        })
        
        quality_report = export_manager._create_quality_report(test_data)
        
        print("✅ Quality report created successfully")
        print(f"   Report length: {len(quality_report)} characters")
        
        # Validate report content
        assert 'Quality Report' in quality_report
        assert 'Total Records' in quality_report
        assert 'Data Completeness' in quality_report
        
        # Check that all columns are mentioned
        for col in test_data.columns:
            assert col in quality_report, f"Column {col} not mentioned in quality report"
        
        print("✅ Quality report validation passed")
        
        return True
    except Exception as e:
        print(f"❌ Error testing quality report creation: {e}")
        return False

def test_report_content_creation():
    """Test HTML report content creation"""
    try:
        from components.export_manager import ExportManager
        
        export_manager = ExportManager(None)
        
        # Test report options
        options = {
            "custom_title": "Test ARGO Report",
            "custom_author": "Test System",
            "include_overview": True,
            "include_data_summary": True,
            "include_quality_assessment": True
        }
        
        html_content = export_manager._create_report_content(options)
        
        print("✅ HTML report content created successfully")
        print(f"   Content length: {len(html_content)} characters")
        
        # Validate HTML structure
        assert '<!DOCTYPE html>' in html_content
        assert '<html>' in html_content
        assert '</html>' in html_content
        assert options['custom_title'] in html_content
        assert options['custom_author'] in html_content
        
        # Check for included sections
        if options['include_overview']:
            assert 'System Overview' in html_content
        if options['include_data_summary']:
            assert 'Data Summary' in html_content
        if options['include_quality_assessment']:
            assert 'Quality Assessment' in html_content
        
        print("✅ HTML report validation passed")
        
        return True
    except Exception as e:
        print(f"❌ Error testing report content creation: {e}")
        return False

def test_available_visualizations():
    """Test available visualizations list"""
    try:
        from components.export_manager import ExportManager
        
        export_manager = ExportManager(None)
        viz_list = export_manager._get_available_visualizations()
        
        print("✅ Available visualizations retrieved successfully")
        print(f"   Available visualizations: {len(viz_list)}")
        
        for viz in viz_list:
            print(f"   - {viz}")
        
        # Validate list structure
        assert isinstance(viz_list, list)
        assert len(viz_list) > 0
        assert all(isinstance(viz, str) for viz in viz_list)
        
        # Check for expected visualization types
        viz_names_lower = [viz.lower() for viz in viz_list]
        assert any('map' in name for name in viz_names_lower)
        assert any('profile' in name or 'temperature' in name for name in viz_names_lower)
        
        print("✅ Visualization list validation passed")
        
        return True
    except Exception as e:
        print(f"❌ Error testing available visualizations: {e}")
        return False

def main():
    """Run all export manager component tests"""
    print("🧪 Testing Export Manager Components")
    print("=" * 50)
    
    tests = [
        ("Export Manager Imports", test_export_manager_imports),
        ("Supported Formats", test_supported_formats),
        ("Sample Data Creation", test_sample_data_creation),
        ("Visualization Creation", test_visualization_creation),
        ("Metadata Creation", test_metadata_creation),
        ("Quality Report Creation", test_quality_report_creation),
        ("Report Content Creation", test_report_content_creation),
        ("Available Visualizations", test_available_visualizations)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n📋 Testing {test_name}:")
        try:
            if test_func():
                passed += 1
            else:
                print(f"   Test failed for {test_name}")
        except Exception as e:
            print(f"   Test error for {test_name}: {e}")
    
    print(f"\n📊 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All export manager component tests passed!")
        return 0
    else:
        print("⚠️ Some tests failed.")
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(main())