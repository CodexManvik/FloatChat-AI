"""
Simple test script for layout components
Run this to test the layout manager without full Streamlit app
"""

def test_layout_imports():
    """Test that layout components can be imported"""
    try:
        from components.layout_manager import DashboardLayout
        print("✅ DashboardLayout imported successfully")
        
        layout = DashboardLayout()
        print("✅ DashboardLayout instantiated successfully")
        
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_theme_imports():
    """Test that theme components can be imported"""
    try:
        from styles.government_theme import GovernmentTheme
        print("✅ GovernmentTheme imported successfully")
        
        css = GovernmentTheme.get_css()
        print(f"✅ CSS generated successfully ({len(css)} characters)")
        
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_config_access():
    """Test configuration access"""
    try:
        from dashboard_config import dashboard_config
        print("✅ Dashboard config imported successfully")
        
        print(f"✅ API Base URL: {dashboard_config.API_BASE_URL}")
        print(f"✅ Map Center: {dashboard_config.DEFAULT_MAP_CENTER}")
        
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    """Run all layout tests"""
    print("🧪 Testing Layout Components")
    print("=" * 40)
    
    tests = [
        ("Layout Manager", test_layout_imports),
        ("Government Theme", test_theme_imports),
        ("Configuration", test_config_access)
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
        print("🎉 All layout tests passed!")
        return 0
    else:
        print("⚠️ Some tests failed.")
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(main())