"""
Simple test script for chat interface component
"""

from unittest.mock import Mock

def test_chat_imports():
    """Test that chat components can be imported"""
    try:
        from components.chat_interface import ChatInterface
        print("✅ ChatInterface imported successfully")
        
        # Test with mock API client
        mock_api = Mock()
        chat_interface = ChatInterface(mock_api)
        print("✅ ChatInterface instantiated successfully")
        
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_sample_queries():
    """Test sample queries functionality"""
    try:
        from components.chat_interface import ChatInterface
        
        chat_interface = ChatInterface(None)
        queries = chat_interface._get_sample_queries()
        
        print(f"✅ Sample queries loaded: {len(queries)} categories")
        
        for category, query_list in queries.items():
            print(f"   - {category}: {len(query_list)} queries")
        
        # Test specific categories
        assert 'location' in queries
        assert 'temperature_salinity' in queries
        assert 'bgc' in queries
        assert 'analysis' in queries
        
        print("✅ All expected query categories present")
        
        return True
    except Exception as e:
        print(f"❌ Error testing sample queries: {e}")
        return False

def test_response_enhancement():
    """Test response content enhancement"""
    try:
        from components.chat_interface import ChatInterface
        
        chat_interface = ChatInterface(None)
        
        # Test basic enhancement
        original = "This is a test response."
        metadata = {
            'data_count': 5,
            'float_ids': ['ARGO_001', 'ARGO_002'],
            'query_type': 'analytical'
        }
        
        enhanced = chat_interface._enhance_response_content(original, metadata)
        
        print("✅ Response enhancement working")
        print(f"   Original length: {len(original)}")
        print(f"   Enhanced length: {len(enhanced)}")
        
        # Check that enhancement adds content
        assert len(enhanced) > len(original)
        assert "Data Context" in enhanced
        
        return True
    except Exception as e:
        print(f"❌ Error testing response enhancement: {e}")
        return False

def test_chat_statistics():
    """Test chat statistics functionality"""
    try:
        from components.chat_interface import ChatInterface
        
        chat_interface = ChatInterface(None)
        
        # Test with empty history (mock session state)
        import streamlit as st
        if hasattr(st, 'session_state'):
            # If running in Streamlit context
            st.session_state.chat_history = []
            stats = chat_interface.get_chat_statistics()
            print("✅ Empty chat statistics handled")
        else:
            # Mock the session state
            with unittest.mock.patch('streamlit.session_state') as mock_session:
                mock_session.chat_history = [
                    {'type': 'user', 'content': 'Test query'},
                    {'type': 'ai', 'content': 'Test response'},
                    {'type': 'ai', 'content': 'Error response', 'error': True}
                ]
                
                stats = chat_interface.get_chat_statistics()
                
                print("✅ Chat statistics calculated")
                print(f"   Total messages: {stats.get('total_messages', 0)}")
                print(f"   Success rate: {stats.get('success_rate', 0):.1f}%")
        
        return True
    except Exception as e:
        print(f"❌ Error testing chat statistics: {e}")
        return False

def test_data_transformer_integration():
    """Test integration with data transformer"""
    try:
        from components.chat_interface import ChatInterface
        from components.api_client import QueryResponse
        
        chat_interface = ChatInterface(None)
        
        # Test metadata extraction
        mock_response = QueryResponse(
            answer="Test answer",
            context_documents=["doc1"],
            retrieved_metadata=[
                {"postgres_id": 1, "float_id": "ARGO_001"},
                {"postgres_id": 2, "float_id": "ARGO_002"}
            ]
        )
        
        metadata = chat_interface.transformer.extract_metadata_for_chat(mock_response.__dict__)
        
        print("✅ Data transformer integration working")
        print(f"   Extracted metadata keys: {list(metadata.keys())}")
        
        assert 'postgres_ids' in metadata
        assert 'float_ids' in metadata
        
        return True
    except Exception as e:
        print(f"❌ Error testing data transformer integration: {e}")
        return False

def test_visualization_components_integration():
    """Test integration with visualization components"""
    try:
        from components.chat_interface import ChatInterface
        
        chat_interface = ChatInterface(None)
        
        # Test that visualization components are accessible
        assert chat_interface.map_viz is not None
        assert chat_interface.profile_viz is not None
        
        print("✅ Visualization components integrated")
        print("   - Map visualization component available")
        print("   - Profile visualization component available")
        
        return True
    except Exception as e:
        print(f"❌ Error testing visualization integration: {e}")
        return False

def main():
    """Run all chat component tests"""
    print("🧪 Testing Chat Interface Components")
    print("=" * 50)
    
    tests = [
        ("Chat Imports", test_chat_imports),
        ("Sample Queries", test_sample_queries),
        ("Response Enhancement", test_response_enhancement),
        ("Chat Statistics", test_chat_statistics),
        ("Data Transformer Integration", test_data_transformer_integration),
        ("Visualization Integration", test_visualization_components_integration)
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
        print("🎉 All chat component tests passed!")
        return 0
    else:
        print("⚠️ Some tests failed.")
        return 1

if __name__ == "__main__":
    import sys
    import unittest.mock
    sys.exit(main())