"""
Simple test script for map visualization component
"""

def test_map_imports():
    """Test that map components can be imported"""
    try:
        from components.map_visualization import InteractiveMap
        print("✅ InteractiveMap imported successfully")
        
        map_viz = InteractiveMap()
        print("✅ InteractiveMap instantiated successfully")
        
        # Test base map creation
        fig = map_viz.create_base_map()
        print("✅ Base map created successfully")
        
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_data_fetcher():
    """Test data fetcher component"""
    try:
        from components.data_fetcher import DataFetcher
        print("✅ DataFetcher imported successfully")
        
        fetcher = DataFetcher()
        print("✅ DataFetcher instantiated successfully")
        
        # Test sample data creation
        sample_data = fetcher._create_sample_float_data(10)
        print(f"✅ Sample data created: {len(sample_data)} floats")
        
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_map_with_data():
    """Test map with sample data"""
    try:
        from components.map_visualization import InteractiveMap
        from components.data_fetcher import DataFetcher
        
        map_viz = InteractiveMap()
        fetcher = DataFetcher()
        
        # Create sample data
        float_data = fetcher._create_sample_float_data(5)
        trajectory_data = fetcher._create_sample_trajectory_data(2)
        
        # Create map with data
        fig = map_viz.create_base_map()
        fig = map_viz.add_float_markers(fig, float_data)
        fig = map_viz.add_trajectories(fig, trajectory_data)
        
        print("✅ Map created with sample data successfully")
        print(f"   - {len(float_data)} float markers")
        print(f"   - {len(trajectory_data)} trajectory points")
        
        return True
    except Exception as e:
        print(f"❌ Error creating map with data: {e}")
        return False

def test_predefined_regions():
    """Test predefined regions functionality"""
    try:
        from components.map_visualization import InteractiveMap
        
        map_viz = InteractiveMap()
        regions = map_viz.get_predefined_regions()
        
        print(f"✅ Retrieved {len(regions)} predefined regions:")
        for region_name in regions.keys():
            print(f"   - {region_name}")
        
        return True
    except Exception as e:
        print(f"❌ Error testing regions: {e}")
        return False

def main():
    """Run all map component tests"""
    print("🧪 Testing Map Visualization Components")
    print("=" * 50)
    
    tests = [
        ("Map Imports", test_map_imports),
        ("Data Fetcher", test_data_fetcher),
        ("Map with Data", test_map_with_data),
        ("Predefined Regions", test_predefined_regions)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n📋 Testing {test_name}:")
        if test_func():
            passed += 1
        else:
            print(f"   Test failed for {test_name}")
    
    print(f"\n📊 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All map component tests passed!")
        return 0
    else:
        print("⚠️ Some tests failed.")
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(main())