"""
Test script to verify dashboard setup and dependencies
"""

import sys
import importlib
from typing import List, Tuple

def test_imports() -> List[Tuple[str, bool, str]]:
    """Test all required imports"""
    required_packages = [
        ('streamlit', 'Streamlit web framework'),
        ('plotly', 'Plotly visualization library'),
        ('pandas', 'Data manipulation library'),
        ('numpy', 'Numerical computing library'),
        ('requests', 'HTTP library for API calls'),
        ('datetime', 'Date and time utilities'),
        ('typing', 'Type hints support'),
        ('logging', 'Logging utilities')
    ]
    
    results = []
    
    for package, description in required_packages:
        try:
            importlib.import_module(package)
            results.append((package, True, f"✅ {description}"))
        except ImportError as e:
            results.append((package, False, f"❌ {description} - {str(e)}"))
    
    return results

def test_custom_modules() -> List[Tuple[str, bool, str]]:
    """Test custom dashboard modules"""
    custom_modules = [
        ('components.api_client', 'API client for backend integration'),
        ('dashboard_config', 'Dashboard configuration'),
        ('utils.dashboard_utils', 'Dashboard utility functions')
    ]
    
    results = []
    
    for module, description in custom_modules:
        try:
            importlib.import_module(module)
            results.append((module, True, f"✅ {description}"))
        except ImportError as e:
            results.append((module, False, f"❌ {description} - {str(e)}"))
    
    return results

def test_config_access():
    """Test configuration access"""
    try:
        import config
        import dashboard_config
        
        # Test main config
        assert hasattr(config, 'DATABASE_URL'), "DATABASE_URL not found in config"
        assert hasattr(config, 'OLLAMA_HOST'), "OLLAMA_HOST not found in config"
        
        # Test dashboard config
        assert hasattr(dashboard_config, 'DashboardConfig'), "DashboardConfig class not found"
        
        return True, "✅ Configuration files accessible"
    except Exception as e:
        return False, f"❌ Configuration error: {str(e)}"

def main():
    """Run all tests"""
    print("🧪 Testing Dashboard Setup")
    print("=" * 50)
    
    # Test package imports
    print("\n📦 Testing Package Imports:")
    import_results = test_imports()
    for package, success, message in import_results:
        print(f"  {message}")
    
    # Test custom modules
    print("\n🔧 Testing Custom Modules:")
    module_results = test_custom_modules()
    for module, success, message in module_results:
        print(f"  {message}")
    
    # Test configuration
    print("\n⚙️ Testing Configuration:")
    config_success, config_message = test_config_access()
    print(f"  {config_message}")
    
    # Summary
    print("\n📊 Test Summary:")
    total_tests = len(import_results) + len(module_results) + 1
    passed_tests = sum([1 for _, success, _ in import_results if success]) + \
                   sum([1 for _, success, _ in module_results if success]) + \
                   (1 if config_success else 0)
    
    print(f"  Passed: {passed_tests}/{total_tests}")
    
    if passed_tests == total_tests:
        print("  🎉 All tests passed! Dashboard setup is ready.")
        return 0
    else:
        print("  ⚠️ Some tests failed. Please check the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())