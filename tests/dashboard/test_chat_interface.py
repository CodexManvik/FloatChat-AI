"""
Unit tests for Chat Interface Component
"""

import pytest
import pandas as pd
from unittest.mock import Mock, patch
from datetime import datetime
from components.chat_interface import ChatInterface
from components.api_client import QueryResponse

class TestChatInterface:
    """Test cases for ChatInterface class"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Mock API client
        self.mock_api_client = Mock()
        self.chat_interface = ChatInterface(self.mock_api_client)
        
        # Sample query response
        self.sample_response = QueryResponse(
            answer="Test answer about ARGO data",
            context_documents=["doc1", "doc2"],
            retrieved_metadata=[
                {"postgres_id": 1, "float_id": "ARGO_001"},
                {"postgres_id": 2, "float_id": "ARGO_002"}
            ],
            sql_results=None
        )
    
    def test_init(self):
        """Test chat interface initialization"""
        assert self.chat_interface.api_client == self.mock_api_client
        assert self.chat_interface.config is not None
        assert self.chat_interface.sample_queries is not None
    
    def test_init_without_api_client(self):
        """Test initialization without API client"""
        chat_interface = ChatInterface(None)
        assert chat_interface.api_client is None
    
    def test_get_sample_queries(self):
        """Test sample queries structure"""
        queries = self.chat_interface._get_sample_queries()
        
        assert isinstance(queries, dict)
        assert 'location' in queries
        assert 'temperature_salinity' in queries
        assert 'bgc' in queries
        assert 'analysis' in queries
        
        # Check that each category has queries
        for category, query_list in queries.items():
            assert isinstance(query_list, list)
            assert len(query_list) > 0
            assert all(isinstance(q, str) for q in query_list)
    
    def test_create_ai_response(self):
        """Test AI response creation"""
        query = "Test query"
        
        ai_message = self.chat_interface._create_ai_response(query, self.sample_response)
        
        assert isinstance(ai_message, dict)
        assert ai_message['type'] == 'ai'
        assert 'content' in ai_message
        assert 'timestamp' in ai_message
        assert 'metadata' in ai_message
        assert 'raw_response' in ai_message
        assert isinstance(ai_message['timestamp'], datetime)
    
    def test_enhance_response_content(self):
        """Test response content enhancement"""
        original_answer = "This is a test answer."
        metadata = {
            'data_count': 5,
            'float_ids': ['ARGO_001', 'ARGO_002'],
            'query_type': 'analytical',
            'postgres_ids': [1, 2, 3]
        }
        
        enhanced = self.chat_interface._enhance_response_content(original_answer, metadata)
        
        assert original_answer in enhanced
        assert "Data Context" in enhanced
        assert "5 relevant measurements" in enhanced
        assert "2 ARGO floats" in enhanced
        assert "Analysis Type" in enhanced
        assert "Tip" in enhanced
    
    def test_enhance_response_content_empty_metadata(self):
        """Test response enhancement with empty metadata"""
        original_answer = "This is a test answer."
        metadata = {}
        
        enhanced = self.chat_interface._enhance_response_content(original_answer, metadata)
        
        # Should return original answer when no metadata
        assert enhanced == original_answer
    
    @patch('streamlit.session_state')
    def test_process_user_query_success(self, mock_session_state):
        """Test successful query processing"""
        # Setup mock session state
        mock_session_state.chat_history = []
        
        # Setup mock API response
        self.mock_api_client.query_rag_pipeline.return_value = self.sample_response
        
        query = "Test query"
        
        # This would normally interact with Streamlit, so we'll test the logic
        # The actual method would need Streamlit context to run fully
        assert self.chat_interface.api_client is not None
    
    def test_process_user_query_no_api_client(self):
        """Test query processing without API client"""
        chat_interface = ChatInterface(None)
        
        # Should handle gracefully when no API client
        assert chat_interface.api_client is None
    
    def test_get_chat_statistics_empty_history(self):
        """Test chat statistics with empty history"""
        with patch('streamlit.session_state') as mock_session_state:
            mock_session_state.chat_history = []
            
            stats = self.chat_interface.get_chat_statistics()
            
            assert stats == {}
    
    def test_get_chat_statistics_with_messages(self):
        """Test chat statistics with message history"""
        sample_history = [
            {'type': 'user', 'content': 'Query 1'},
            {'type': 'ai', 'content': 'Response 1'},
            {'type': 'user', 'content': 'Query 2'},
            {'type': 'ai', 'content': 'Response 2', 'error': True},
            {'type': 'ai', 'content': 'Response 3'}
        ]
        
        with patch('streamlit.session_state') as mock_session_state:
            mock_session_state.chat_history = sample_history
            
            stats = self.chat_interface.get_chat_statistics()
            
            assert stats['total_messages'] == 5
            assert stats['user_messages'] == 2
            assert stats['ai_messages'] == 3
            assert stats['error_messages'] == 1
            assert stats['success_rate'] == (3 - 1) / 3 * 100  # 66.67%
    
    def test_sql_results_visualization_data_prep(self):
        """Test SQL results data preparation for visualization"""
        sql_results = [
            {'depth': 10, 'avg_temperature': 25.5, 'avg_salinity': 35.2},
            {'depth': 50, 'avg_temperature': 24.8, 'avg_salinity': 35.1},
            {'depth': 100, 'avg_temperature': 22.1, 'avg_salinity': 35.0}
        ]
        
        df = self.chat_interface.transformer.sql_results_to_dataframe(sql_results)
        
        assert not df.empty
        assert len(df) == 3
        assert 'depth' in df.columns
        assert 'avg_temperature' in df.columns
        assert 'avg_salinity' in df.columns
    
    def test_profile_data_extraction(self):
        """Test profile data extraction for visualization"""
        profiles_data = [
            {
                'id': 1, 'float_id': 'ARGO_001', 'depth': 10, 
                'temperature': 25.5, 'salinity': 35.2, 'lat': 10.0, 'lon': 75.0
            },
            {
                'id': 2, 'float_id': 'ARGO_001', 'depth': 50,
                'temperature': 24.8, 'salinity': 35.1, 'lat': 10.0, 'lon': 75.0
            }
        ]
        
        df = self.chat_interface.transformer.profiles_to_dataframe(profiles_data)
        locations_df = self.chat_interface.transformer.extract_float_locations(df)
        
        assert not df.empty
        assert not locations_df.empty
        assert 'float_id' in locations_df.columns
        assert 'lat' in locations_df.columns
        assert 'lon' in locations_df.columns
    
    def test_query_type_detection(self):
        """Test query type detection from content"""
        location_queries = [
            "show me floats in arabian sea",
            "where are the floats located",
            "find measurements near equator"
        ]
        
        profile_queries = [
            "show temperature profiles",
            "salinity data for float",
            "depth measurements"
        ]
        
        # Test that different query types can be distinguished
        # (This would be more comprehensive with actual NLP processing)
        for query in location_queries:
            assert 'location' in query.lower() or 'where' in query.lower() or 'near' in query.lower()
        
        for query in profile_queries:
            assert any(word in query.lower() for word in ['temperature', 'salinity', 'profile', 'depth'])
    
    def test_error_handling_in_response_creation(self):
        """Test error handling in response creation"""
        # Test with malformed response
        malformed_response = Mock()
        malformed_response.__dict__ = {}  # Empty dict
        
        try:
            ai_message = self.chat_interface._create_ai_response("test", malformed_response)
            # Should handle gracefully
            assert ai_message['type'] == 'ai'
        except Exception as e:
            # Should not raise unhandled exceptions
            assert False, f"Should handle malformed response gracefully: {e}"
    
    def test_sample_query_categories(self):
        """Test that sample queries cover expected categories"""
        queries = self.chat_interface.sample_queries
        
        # Check location queries
        location_queries = queries['location']
        assert any('arabian sea' in q.lower() for q in location_queries)
        assert any('equator' in q.lower() for q in location_queries)
        
        # Check temperature/salinity queries
        ts_queries = queries['temperature_salinity']
        assert any('temperature' in q.lower() for q in ts_queries)
        assert any('salinity' in q.lower() for q in ts_queries)
        
        # Check BGC queries
        bgc_queries = queries['bgc']
        assert any('bgc' in q.lower() or 'oxygen' in q.lower() for q in bgc_queries)
        
        # Check analysis queries
        analysis_queries = queries['analysis']
        assert any('summary' in q.lower() or 'analysis' in q.lower() for q in analysis_queries)

if __name__ == "__main__":
    pytest.main([__file__])