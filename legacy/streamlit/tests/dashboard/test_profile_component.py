"""
Simple test script for profile visualization component
"""

import pandas as pd
import numpy as np

def test_profile_imports():
    """Test that profile components can be imported"""
    try:
        from components.profile_visualizer import ProfileVisualizer
        print("✅ ProfileVisualizer imported successfully")
        
        profile_viz = ProfileVisualizer()
        print("✅ ProfileVisualizer instantiated successfully")
        
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_profile_creation():
    """Test profile plot creation"""
    try:
        from components.profile_visualizer import ProfileVisualizer
        
        profile_viz = ProfileVisualizer()
        
        # Create sample data
        depths = np.arange(0, 500, 10)
        n_points = len(depths)
        
        sample_data = pd.DataFrame({
            'depth': depths,
            'temperature': 25 - depths * 0.02 + np.random.normal(0, 0.5, n_points),
            'salinity': 35 + depths * 0.001 + np.random.normal(0, 0.1, n_points),
            'oxygen': 6 - depths * 0.005 + np.random.normal(0, 0.2, n_points),
            'ph': 8.1 - depths * 0.0001 + np.random.normal(0, 0.02, n_points),
            'chlorophyll': np.random.exponential(0.5, n_points) * np.exp(-depths/100)
        })
        
        # Ensure positive values
        sample_data['oxygen'] = np.maximum(sample_data['oxygen'], 0.1)
        sample_data['chlorophyll'] = np.maximum(sample_data['chlorophyll'], 0)
        
        # Test T-S profile
        fig = profile_viz.create_ts_profile(sample_data, "ARGO_001")
        print("✅ T-S profile created successfully")
        
        # Test T-S diagram
        ts_fig = profile_viz.create_ts_diagram(sample_data)
        print("✅ T-S diagram created successfully")
        
        # Test BGC plots
        bgc_figs = profile_viz.create_bgc_plots(sample_data, ['oxygen', 'ph', 'chlorophyll'])
        print(f"✅ BGC plots created successfully ({len(bgc_figs)} plots)")
        
        return True
    except Exception as e:
        print(f"❌ Error creating profiles: {e}")
        return False

def test_profile_comparison():
    """Test profile comparison functionality"""
    try:
        from components.profile_visualizer import ProfileVisualizer
        
        profile_viz = ProfileVisualizer()
        
        # Create two different profiles
        depths = np.arange(0, 300, 10)
        n_points = len(depths)
        
        profile1 = pd.DataFrame({
            'depth': depths,
            'temperature': 25 - depths * 0.02 + np.random.normal(0, 0.5, n_points),
            'salinity': 35 + depths * 0.001 + np.random.normal(0, 0.1, n_points)
        })
        
        profile2 = pd.DataFrame({
            'depth': depths,
            'temperature': 27 - depths * 0.025 + np.random.normal(0, 0.3, n_points),
            'salinity': 34.8 + depths * 0.0012 + np.random.normal(0, 0.08, n_points)
        })
        
        # Test comparison plot
        fig = profile_viz.create_comparison_plot([profile1, profile2], ['Float 1', 'Float 2'])
        print("✅ Profile comparison created successfully")
        
        return True
    except Exception as e:
        print(f"❌ Error creating comparison: {e}")
        return False

def test_bgc_parameter_config():
    """Test BGC parameter configuration"""
    try:
        from components.profile_visualizer import ProfileVisualizer
        
        profile_viz = ProfileVisualizer()
        
        # Test known parameters
        oxygen_config = profile_viz._get_bgc_parameter_config('oxygen')
        ph_config = profile_viz._get_bgc_parameter_config('ph')
        
        print(f"✅ Oxygen config: {oxygen_config['name']} ({oxygen_config['unit']})")
        print(f"✅ pH config: {ph_config['name']} ({ph_config['unit']})")
        
        # Test unknown parameter
        unknown_config = profile_viz._get_bgc_parameter_config('unknown')
        print(f"✅ Unknown parameter handled: {unknown_config['name']}")
        
        return True
    except Exception as e:
        print(f"❌ Error testing BGC config: {e}")
        return False

def test_empty_data_handling():
    """Test handling of empty data"""
    try:
        from components.profile_visualizer import ProfileVisualizer
        
        profile_viz = ProfileVisualizer()
        
        # Test with empty DataFrame
        empty_data = pd.DataFrame()
        
        fig = profile_viz.create_ts_profile(empty_data)
        print("✅ Empty data handled for T-S profile")
        
        ts_fig = profile_viz.create_ts_diagram(empty_data)
        print("✅ Empty data handled for T-S diagram")
        
        bgc_figs = profile_viz.create_bgc_plots(empty_data)
        print("✅ Empty data handled for BGC plots")
        
        return True
    except Exception as e:
        print(f"❌ Error handling empty data: {e}")
        return False

def main():
    """Run all profile component tests"""
    print("🧪 Testing Profile Visualization Components")
    print("=" * 50)
    
    tests = [
        ("Profile Imports", test_profile_imports),
        ("Profile Creation", test_profile_creation),
        ("Profile Comparison", test_profile_comparison),
        ("BGC Parameter Config", test_bgc_parameter_config),
        ("Empty Data Handling", test_empty_data_handling)
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
        print("🎉 All profile component tests passed!")
        return 0
    else:
        print("⚠️ Some tests failed.")
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(main())