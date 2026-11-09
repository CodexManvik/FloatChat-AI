"""
Simple test script for data manager component
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock

def test_data_manager_imports():
    """Test that data manager components can be imported"""
    try:
        from components.data_manager import DataManager
        print("✅ DataManager imported successfully")
        
        # Test with mock API client
        mock_api = Mock()
        data_manager = DataManager(mock_api)
        print("✅ DataManager instantiated successfully")
        
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_default_filters():
    """Test default filter configuration"""
    try:
        from components.data_manager import DataManager
        
        data_manager = DataManager(None)
        default_filters = data_manager._get_default_filters()
        
        print("✅ Default filters loaded successfully")
        print(f"   Filter keys: {list(default_filters.keys())}")
        
        # Check required keys
        required_keys = ['date_mode', 'date_range', 'region_mode', 'depth_mode', 'quality_levels']
        for key in required_keys:
            assert key in default_filters, f"Missing required filter key: {key}"
        
        print("✅ All required filter keys present")
        
        return True
    except Exception as e:
        print(f"❌ Error testing default filters: {e}")
        return False

def test_predefined_regions():
    """Test predefined region bounds"""
    try:
        from components.data_manager import DataManager
        
        data_manager = DataManager(None)
        
        # Test known regions
        regions = ["Indian Ocean", "Arabian Sea", "Bay of Bengal"]
        
        for region in regions:
            bounds = data_manager._get_predefined_region_bounds(region)
            
            if bounds:
                print(f"✅ {region}: {bounds}")
                
                # Validate bounds structure
                required_keys = ['north', 'south', 'east', 'west']
                assert all(key in bounds for key in required_keys)
                assert bounds['north'] > bounds['south']
                assert bounds['east'] > bounds['west']
            else:
                print(f"⚠️ No bounds defined for {region}")
        
        # Test unknown region
        unknown_bounds = data_manager._get_predefined_region_bounds("Unknown Ocean")
        assert unknown_bounds is None
        print("✅ Unknown region handled correctly")
        
        return True
    except Exception as e:
        print(f"❌ Error testing predefined regions: {e}")
        return False

def test_filter_application():
    """Test filter application on sample data"""
    try:
        from components.data_manager import DataManager
        
        data_manager = DataManager(None)
        
        # Create sample data
        sample_data = pd.DataFrame({
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
        
        print(f"✅ Sample data created: {len(sample_data)} records")
        
        # Test temporal filtering
        temporal_filters = {
            "date_range": (
                (datetime.now() - timedelta(days=25)).date(),
                (datetime.now() - timedelta(days=5)).date()
            )
        }
        
        filtered_data, log = data_manager._apply_temporal_filters(sample_data, temporal_filters)
        print(f"✅ Temporal filtering: {len(sample_data)} -> {len(filtered_data)} records")
        
        # Test geographic filtering
        geographic_filters = {
            "region_bounds": {
                "north": 20.0,
                "south": 5.0,
                "east": 85.0,
                "west": 70.0
            }
        }
        
        filtered_data, log = data_manager._apply_geographic_filters(sample_data, geographic_filters)
        print(f"✅ Geographic filtering: {len(sample_data)} -> {len(filtered_data)} records")
        
        # Test physical filtering
        physical_filters = {
            "depth_range": (0, 100),
            "enable_temp_filter": True,
            "temp_range": (20.0, 30.0)
        }
        
        filtered_data, log = data_manager._apply_physical_filters(sample_data, physical_filters)
        print(f"✅ Physical filtering: {len(sample_data)} -> {len(filtered_data)} records")
        
        return True
    except Exception as e:
        print(f"❌ Error testing filter application: {e}")
        return False

def test_data_quality_assessment():
    """Test data quality assessment"""
    try:
        from components.data_manager import DataManager
        
        data_manager = DataManager(None)
        
        # Create sample data with some quality issues
        sample_data = pd.DataFrame({
            'id': [1, 2, 3, 4, 5],
            'temperature': [25.5, np.nan, 22.1, 18.5, 12.3],  # Missing value
            'salinity': [35.2, 35.1, np.nan, 34.9, 34.8],     # Missing value
            'lat': [10.5, 10.7, 15.2, 95.0, -5.8],            # Invalid coordinate
            'lon': [75.3, 75.5, 80.1, 80.0, 185.7],           # Invalid coordinate
            'time': [
                datetime.now() - timedelta(days=10),
                datetime.now() - timedelta(days=5),
                datetime.now() + timedelta(days=5),  # Future date
                datetime.now() - timedelta(days=20),
                datetime.now() - timedelta(days=30)
            ]
        })
        
        quality_assessment = data_manager.assess_data_quality(sample_data)
        
        print("✅ Data quality assessment completed")
        print(f"   Status: {quality_assessment.get('status', 'unknown')}")
        print(f"   Score: {quality_assessment.get('score', 0):.2f}")
        print(f"   Issues: {len(quality_assessment.get('issues', []))}")
        
        # Test additional quality checks
        additional_checks = data_manager._perform_additional_quality_checks(sample_data)
        
        print("✅ Additional quality checks completed")
        for check, value in additional_checks.items():
            print(f"   {check}: {value}")
        
        return True
    except Exception as e:
        print(f"❌ Error testing data quality assessment: {e}")
        return False

def test_filter_counting():
    """Test active filter counting"""
    try:
        from components.data_manager import DataManager
        
        data_manager = DataManager(None)
        
        # Test default filters
        default_filters = data_manager._get_default_filters()
        default_count = data_manager._count_active_filters(default_filters)
        
        print(f"✅ Default filters active count: {default_count}")
        
        # Test filters with active settings
        active_filters = {
            "date_mode": "Relative Period",
            "predefined_region": "Arabian Sea",
            "enable_temp_filter": True,
            "temp_range": (20.0, 30.0),
            "float_selection_mode": "Specific Float IDs",
            "quality_levels": ["Excellent"]
        }
        
        active_count = data_manager._count_active_filters(active_filters)
        
        print(f"✅ Active filters count: {active_count}")
        assert active_count > default_count
        
        return True
    except Exception as e:
        print(f"❌ Error testing filter counting: {e}")
        return False

def test_comprehensive_filtering():
    """Test comprehensive filter application"""
    try:
        from components.data_manager import DataManager
        
        data_manager = DataManager(None)
        
        # Create larger sample dataset
        np.random.seed(42)
        n_records = 100
        
        sample_data = pd.DataFrame({
            'id': range(1, n_records + 1),
            'float_id': [f'ARGO_{i//10:03d}' for i in range(n_records)],
            'time': [datetime.now() - timedelta(days=np.random.randint(0, 365)) for _ in range(n_records)],
            'lat': np.random.uniform(-30, 30, n_records),
            'lon': np.random.uniform(40, 120, n_records),
            'depth': np.random.uniform(0, 2000, n_records),
            'temperature': np.random.uniform(5, 30, n_records),
            'salinity': np.random.uniform(34, 37, n_records),
            'cycle_number': np.random.randint(1, 200, n_records)
        })
        
        print(f"✅ Large sample dataset created: {len(sample_data)} records")
        
        # Apply comprehensive filters
        comprehensive_filters = {
            "date_range": (
                (datetime.now() - timedelta(days=180)).date(),
                datetime.now().date()
            ),
            "region_bounds": {
                "north": 25.0,
                "south": -10.0,
                "east": 100.0,
                "west": 60.0
            },
            "depth_range": (0, 1000),
            "enable_temp_filter": True,
            "temp_range": (15.0, 28.0),
            "enable_sal_filter": True,
            "sal_range": (34.5, 36.5)
        }
        
        filtered_data = data_manager.apply_filters(sample_data, comprehensive_filters)
        
        print(f"✅ Comprehensive filtering: {len(sample_data)} -> {len(filtered_data)} records")
        
        # Verify filtering worked
        if not filtered_data.empty:
            print("   Filter verification:")
            print(f"   - Depth range: {filtered_data['depth'].min():.1f} - {filtered_data['depth'].max():.1f}m")
            print(f"   - Temperature range: {filtered_data['temperature'].min():.1f} - {filtered_data['temperature'].max():.1f}°C")
            print(f"   - Salinity range: {filtered_data['salinity'].min():.2f} - {filtered_data['salinity'].max():.2f} PSU")
        
        return True
    except Exception as e:
        print(f"❌ Error testing comprehensive filtering: {e}")
        return False

def main():
    """Run all data manager component tests"""
    print("🧪 Testing Data Manager Components")
    print("=" * 50)
    
    tests = [
        ("Data Manager Imports", test_data_manager_imports),
        ("Default Filters", test_default_filters),
        ("Predefined Regions", test_predefined_regions),
        ("Filter Application", test_filter_application),
        ("Data Quality Assessment", test_data_quality_assessment),
        ("Filter Counting", test_filter_counting),
        ("Comprehensive Filtering", test_comprehensive_filtering)
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
        print("🎉 All data manager component tests passed!")
        return 0
    else:
        print("⚠️ Some tests failed.")
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(main())