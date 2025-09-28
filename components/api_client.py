"""
API Client for FastAPI Backend Integration
Handles all communication with the ARGO Float data backend
"""

import requests
import pandas as pd
from typing import Dict, List, Optional, Any, Union
import logging
from dataclasses import dataclass
from datetime import datetime
import time
import json
from urllib.parse import urljoin
import config

logger = logging.getLogger(__name__)

@dataclass
class QueryResponse:
    """Response model for RAG pipeline queries"""
    answer: str
    context_documents: List[str]
    retrieved_metadata: List[dict]
    sql_results: Optional[List[dict]] = None

@dataclass
class FloatInfo:
    """Float information model"""
    float_info: dict
    profile_summary: dict
    measurement_summary: dict

class APIException(Exception):
    """Custom exception for API errors"""
    def __init__(self, message: str, status_code: Optional[int] = None, response_data: Optional[dict] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data

class APIClient:
    """Client for interacting with the FastAPI backend"""
    
    def __init__(self, base_url: str = "http://localhost:8000", max_retries: int = 3, retry_delay: float = 1.0):
        self.base_url = base_url.rstrip('/')
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': 'ARGO-Dashboard/1.0'
        })
        
        # Connection status
        self._is_connected = False
        self._last_health_check = None
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make HTTP request with retry logic and error handling"""
        url = urljoin(self.base_url + '/', endpoint.lstrip('/'))
        
        for attempt in range(self.max_retries + 1):
            try:
                response = self.session.request(method, url, **kwargs)
                
                # Update connection status on successful request
                if response.status_code < 500:
                    self._is_connected = True
                
                return response
                
            except requests.exceptions.ConnectionError as e:
                self._is_connected = False
                if attempt == self.max_retries:
                    raise APIException(f"Connection failed after {self.max_retries + 1} attempts: {str(e)}")
                
                logger.warning(f"Connection attempt {attempt + 1} failed, retrying in {self.retry_delay}s...")
                time.sleep(self.retry_delay * (attempt + 1))  # Exponential backoff
                
            except requests.exceptions.Timeout as e:
                if attempt == self.max_retries:
                    raise APIException(f"Request timeout after {self.max_retries + 1} attempts: {str(e)}")
                
                logger.warning(f"Timeout attempt {attempt + 1}, retrying...")
                time.sleep(self.retry_delay)
                
            except requests.exceptions.RequestException as e:
                raise APIException(f"Request failed: {str(e)}")
        
        raise APIException("Max retries exceeded")
    
    def _validate_response(self, response: requests.Response) -> Dict[str, Any]:
        """Validate and parse response"""
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            try:
                error_data = response.json()
                error_message = error_data.get('detail', str(e))
            except (json.JSONDecodeError, ValueError):
                error_message = f"HTTP {response.status_code}: {response.text}"
            
            raise APIException(error_message, response.status_code, error_data if 'error_data' in locals() else None)
        
        try:
            return response.json()
        except (json.JSONDecodeError, ValueError) as e:
            raise APIException(f"Invalid JSON response: {str(e)}")
    
    @property
    def is_connected(self) -> bool:
        """Check if client is connected to backend"""
        return self._is_connected
    
    def health_check(self) -> Dict[str, Any]:
        """Check backend health status"""
        try:
            response = self._make_request('GET', '/health', timeout=5)
            data = self._validate_response(response)
            self._last_health_check = datetime.now()
            return data
        except APIException as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "error", 
                "message": str(e),
                "database": "disconnected",
                "chromadb": "disconnected"
            }
    
    def query_rag_pipeline(self, query_text: str) -> Optional[QueryResponse]:
        """Send query to RAG pipeline"""
        if not query_text or len(query_text.strip()) == 0:
            raise APIException("Query text cannot be empty")
        
        if len(query_text) > 500:  # Max query length
            raise APIException("Query text too long (max 500 characters)")
        
        try:
            payload = {"query_text": query_text.strip()}
            response = self._make_request('POST', '/query', json=payload, timeout=30)
            data = self._validate_response(response)
            
            return QueryResponse(
                answer=data.get("answer", ""),
                context_documents=data.get("context_documents", []),
                retrieved_metadata=data.get("retrieved_metadata", []),
                sql_results=data.get("sql_results")
            )
        except APIException as e:
            logger.error(f"RAG query failed: {e}")
            raise e
    
    def get_profiles_by_ids(self, ids: List[int]) -> List[dict]:
        """Get profile data by measurement IDs"""
        if not ids:
            return []
        
        if len(ids) > 10000:  # Reasonable limit
            raise APIException("Too many IDs requested (max 10,000)")
        
        # Validate IDs are positive integers
        if not all(isinstance(id_val, int) and id_val > 0 for id_val in ids):
            raise APIException("All IDs must be positive integers")
        
        try:
            payload = {"ids": ids}
            response = self._make_request('POST', '/get_profiles', json=payload, timeout=30)
            data = self._validate_response(response)
            
            if isinstance(data, list):
                return data
            else:
                raise APIException("Invalid response format: expected list")
                
        except APIException as e:
            logger.error(f"Profile data request failed: {e}")
            raise e
    
    def get_float_info(self, float_id: str) -> FloatInfo:
        """Get comprehensive float information"""
        if not float_id or not float_id.strip():
            raise APIException("Float ID cannot be empty")
        
        try:
            response = self._make_request('GET', f'/float/{float_id.strip()}', timeout=10)
            data = self._validate_response(response)
            
            if "error" in data:
                raise APIException(f"Float info error: {data['error']}")
                
            return FloatInfo(
                float_info=data.get("float_info", {}),
                profile_summary=data.get("profile_summary", {}),
                measurement_summary=data.get("measurement_summary", {})
            )
        except APIException as e:
            logger.error(f"Float info request failed: {e}")
            raise e
    
    def get_float_profiles(self, float_id: str) -> List[dict]:
        """Get all profiles for a specific float"""
        if not float_id or not float_id.strip():
            raise APIException("Float ID cannot be empty")
        
        try:
            response = self._make_request('GET', f'/profiles/float/{float_id.strip()}', timeout=15)
            data = self._validate_response(response)
            
            if isinstance(data, dict) and "error" in data:
                raise APIException(f"Float profiles error: {data['error']}")
            
            if isinstance(data, list):
                return data
            else:
                raise APIException("Invalid response format: expected list")
                
        except APIException as e:
            logger.error(f"Float profiles request failed: {e}")
            raise e
    
    def export_data(self, data_ids: List[int], format: str) -> bytes:
        """Export data in specified format"""
        if not data_ids:
            raise APIException("No data IDs provided for export")
        
        if len(data_ids) > 100000:  # Reasonable export limit
            raise APIException("Too many records for export (max 100,000)")
        
        valid_formats = ['ascii', 'netcdf', 'csv']
        if format.lower() not in valid_formats:
            raise APIException(f"Invalid format '{format}'. Supported: {', '.join(valid_formats)}")
        
        try:
            payload = {"data_ids": data_ids, "format": format.lower()}
            response = self._make_request('POST', '/export', json=payload, timeout=60)
            
            # Check if response is JSON (error) or binary (success)
            content_type = response.headers.get('content-type', '')
            if 'application/json' in content_type:
                error_data = response.json()
                raise APIException(f"Export error: {error_data.get('error', 'Unknown error')}")
            
            response.raise_for_status()
            return response.content
            
        except APIException as e:
            logger.error(f"Data export failed: {e}")
            raise e
    
    def get_sample_queries(self) -> Dict[str, Any]:
        """Get sample queries for user guidance"""
        try:
            response = self._make_request('GET', '/sample-queries', timeout=10)
            data = self._validate_response(response)
            return data
        except APIException as e:
            logger.error(f"Sample queries request failed: {e}")
            # Return fallback sample queries
            return {
                "analytical_queries": {
                    "Basic Analysis": [
                        "What is the average temperature at different depths?",
                        "Show me salinity profiles by region",
                        "Compare temperature trends over time"
                    ]
                },
                "semantic_queries": {
                    "Current Data": [
                        "Show me temperature measurements near the equator",
                        "Tell me about salinity profiles in deep water",
                        "What ARGO floats are active in the Indian Ocean?"
                    ]
                }
            }
    
    def get_extensibility_status(self) -> Dict[str, Any]:
        """Get extensibility framework status"""
        try:
            response = self._make_request('GET', '/extensibility/status', timeout=10)
            data = self._validate_response(response)
            return data
        except APIException as e:
            logger.error(f"Extensibility status request failed: {e}")
            return {"status": "error", "message": str(e)}
    
    def test_connection(self) -> bool:
        """Test connection to backend"""
        try:
            health_data = self.health_check()
            return health_data.get("status") == "healthy"
        except Exception:
            return False
    
    def get_system_statistics(self) -> Dict[str, Any]:
        """Get system-wide statistics"""
        try:
            response = self._make_request('GET', '/statistics/system', timeout=30)
            data = self._validate_response(response)
            return data
        except APIException as e:
            logger.error(f"System statistics request failed: {e}")
            # Return fallback data
            return {
                'active_floats': 'N/A',
                'total_profiles': 'N/A', 
                'total_measurements': 0,
                'data_quality': 0.0,
                'recent_activity': []
            }
    
    def get_available_regions(self) -> List[str]:
        """Get list of available geographic regions"""
        try:
            response = self._make_request('GET', '/data/regions', timeout=15)
            data = self._validate_response(response)
            return data.get('regions', [])
        except APIException as e:
            logger.error(f"Available regions request failed: {e}")
            # Return fallback regions
            return [
                'Arabian Sea',
                'Bay of Bengal', 
                'Indian Ocean',
                'Equatorial Indian Ocean',
                'Southern Indian Ocean'
            ]