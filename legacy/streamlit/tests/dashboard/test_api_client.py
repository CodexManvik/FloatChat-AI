"""
Unit tests for API Client
"""

import pytest
import requests
from unittest.mock import Mock, patch, MagicMock
import json
from components.api_client import APIClient, APIException, QueryResponse, FloatInfo

class TestAPIClient:
    """Test cases for APIClient class"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.client = APIClient(base_url="http://test-api:8000")
    
    def test_init(self):
        """Test client initialization"""
        assert self.client.base_url == "http://test-api:8000"
        assert self.client.max_retries == 3
        assert not self.client.is_connected
    
    @patch('requests.Session.request')
    def test_health_check_success(self, mock_request):
        """Test successful health check"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "healthy",
            "database": "connected",
            "chromadb": "connected"
        }
        mock_request.return_value = mock_response
        
        result = self.client.health_check()
        
        assert result["status"] == "healthy"
        assert self.client.is_connected
    
    @patch('requests.Session.request')
    def test_health_check_failure(self, mock_request):
        """Test health check failure"""
        mock_request.side_effect = requests.exceptions.ConnectionError("Connection failed")
        
        result = self.client.health_check()
        
        assert result["status"] == "error"
        assert not self.client.is_connected
    
    @patch('requests.Session.request')
    def test_query_rag_pipeline_success(self, mock_request):
        """Test successful RAG query"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "answer": "Test answer",
            "context_documents": ["doc1", "doc2"],
            "retrieved_metadata": [{"id": 1}],
            "sql_results": [{"temp": 15.5}]
        }
        mock_request.return_value = mock_response
        
        result = self.client.query_rag_pipeline("test query")
        
        assert isinstance(result, QueryResponse)
        assert result.answer == "Test answer"
        assert len(result.context_documents) == 2
    
    def test_query_rag_pipeline_empty_query(self):
        """Test RAG query with empty input"""
        with pytest.raises(APIException, match="Query text cannot be empty"):
            self.client.query_rag_pipeline("")
    
    def test_query_rag_pipeline_long_query(self):
        """Test RAG query with too long input"""
        long_query = "x" * 501
        with pytest.raises(APIException, match="Query text too long"):
            self.client.query_rag_pipeline(long_query)
    
    @patch('requests.Session.request')
    def test_get_profiles_by_ids_success(self, mock_request):
        """Test successful profile data retrieval"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"id": 1, "temperature": 15.5, "depth": 10.0},
            {"id": 2, "temperature": 14.8, "depth": 20.0}
        ]
        mock_request.return_value = mock_response
        
        result = self.client.get_profiles_by_ids([1, 2])
        
        assert len(result) == 2
        assert result[0]["temperature"] == 15.5
    
    def test_get_profiles_by_ids_empty_list(self):
        """Test profile retrieval with empty ID list"""
        result = self.client.get_profiles_by_ids([])
        assert result == []
    
    def test_get_profiles_by_ids_too_many(self):
        """Test profile retrieval with too many IDs"""
        large_list = list(range(10001))
        with pytest.raises(APIException, match="Too many IDs requested"):
            self.client.get_profiles_by_ids(large_list)
    
    def test_get_profiles_by_ids_invalid_ids(self):
        """Test profile retrieval with invalid IDs"""
        with pytest.raises(APIException, match="All IDs must be positive integers"):
            self.client.get_profiles_by_ids([1, -2, 3])
    
    @patch('requests.Session.request')
    def test_get_float_info_success(self, mock_request):
        """Test successful float info retrieval"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "float_info": {"float_id": "ARGO_001", "wmo_id": 5900001},
            "profile_summary": {"total_profiles": 50},
            "measurement_summary": {"total_measurements": 1500}
        }
        mock_request.return_value = mock_response
        
        result = self.client.get_float_info("ARGO_001")
        
        assert isinstance(result, FloatInfo)
        assert result.float_info["float_id"] == "ARGO_001"
    
    def test_get_float_info_empty_id(self):
        """Test float info with empty ID"""
        with pytest.raises(APIException, match="Float ID cannot be empty"):
            self.client.get_float_info("")
    
    @patch('requests.Session.request')
    def test_export_data_success(self, mock_request):
        """Test successful data export"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {'content-type': 'text/csv'}
        mock_response.content = b"id,temperature,salinity\n1,15.5,35.2\n"
        mock_request.return_value = mock_response
        
        result = self.client.export_data([1, 2], "csv")
        
        assert isinstance(result, bytes)
        assert b"temperature" in result
    
    def test_export_data_empty_ids(self):
        """Test export with empty ID list"""
        with pytest.raises(APIException, match="No data IDs provided"):
            self.client.export_data([], "csv")
    
    def test_export_data_invalid_format(self):
        """Test export with invalid format"""
        with pytest.raises(APIException, match="Invalid format"):
            self.client.export_data([1, 2], "invalid")
    
    @patch('requests.Session.request')
    def test_retry_logic(self, mock_request):
        """Test retry logic on connection failure"""
        # First two calls fail, third succeeds
        mock_request.side_effect = [
            requests.exceptions.ConnectionError("Connection failed"),
            requests.exceptions.ConnectionError("Connection failed"),
            Mock(status_code=200, json=lambda: {"status": "healthy"})
        ]
        
        with patch('time.sleep'):  # Mock sleep to speed up test
            result = self.client.health_check()
        
        assert result["status"] == "healthy"
        assert mock_request.call_count == 3
    
    @patch('requests.Session.request')
    def test_max_retries_exceeded(self, mock_request):
        """Test behavior when max retries exceeded"""
        mock_request.side_effect = requests.exceptions.ConnectionError("Connection failed")
        
        with patch('time.sleep'):  # Mock sleep to speed up test
            result = self.client.health_check()
        
        assert result["status"] == "error"
        assert mock_request.call_count == 4  # Initial + 3 retries
    
    def test_connection_status(self):
        """Test connection status tracking"""
        assert not self.client.is_connected
        
        with patch.object(self.client, '_make_request') as mock_request:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "healthy"}
            mock_request.return_value = mock_response
            
            self.client.health_check()
            assert self.client.is_connected

if __name__ == "__main__":
    pytest.main([__file__])