"""
Unit tests for Error Handler Component
"""

import pytest
import streamlit as st
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import sys
import os

# Add the parent directory to the path to import components
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from components.error_handler import (
    ErrorHandler, ErrorSeverity, ErrorCategory, ErrorInfo,
    error_handler_decorator, safe_api_call, safe_data_operation
)

class TestErrorHandler:
    """Test cases for ErrorHandler class."""
    
    @pytest.fixture
    def error_handler(self):
        """Create an ErrorHandler instance for testing."""
        return ErrorHandler()
    
    @pytest.fixture
    def mock_streamlit(self):
        """Mock Streamlit functions."""
        with patch.multiple(
            'streamlit',
            error=Mock(),
            warning=Mock(),
            info=Mock(),
            success=Mock(),
            session_state=Mock()
        ) as mocks:
            # Initialize session state mock
            mocks['session_state'].__contains__ = Mock(return_value=False)
            mocks['session_state'].__getitem__ = Mock(return_value=None)
            mocks['session_state'].__setitem__ = Mock()
            yield mocks
    
    def test_initialization(self, error_handler):
        """Test ErrorHandler initialization."""
        assert isinstance(error_handler, ErrorHandler)
        assert hasattr(error_handler, 'error_history')
        assert hasattr(error_handler, 'connection_status')
        assert hasattr(error_handler, 'cached_data')
        assert hasattr(error_handler, 'cache_timestamps')
        assert error_handler.error_history == []
        assert 'api' in error_handler.connection_status
    
    def test_determine_severity(self, error_handler):
        """Test error severity determination."""
        # Test critical errors
        memory_error = MemoryError("Out of memory")
        severity = error_handler._determine_severity(memory_error, ErrorCategory.SYSTEM)
        assert severity == ErrorSeverity.CRITICAL
        
        # Test API connection errors
        connection_error = ConnectionError("Connection refused")
        severity = error_handler._determine_severity(connection_error, ErrorCategory.API_CONNECTION)
        assert severity == ErrorSeverity.ERROR
        
        # Test timeout errors
        timeout_error = Exception("Request timeout")
        severity = error_handler._determine_severity(timeout_error, ErrorCategory.API_CONNECTION)
        assert severity == ErrorSeverity.WARNING
        
        # Test data processing errors
        value_error = ValueError("Invalid value")
        severity = error_handler._determine_severity(value_error, ErrorCategory.DATA_PROCESSING)
        assert severity == ErrorSeverity.WARNING
        
        # Test visualization errors
        plot_error = Exception("Plot failed")
        severity = error_handler._determine_severity(plot_error, ErrorCategory.VISUALIZATION)
        assert severity == ErrorSeverity.WARNING
        
        # Test user input errors
        input_error = Exception("Invalid input")
        severity = error_handler._determine_severity(input_error, ErrorCategory.USER_INPUT)
        assert severity == ErrorSeverity.INFO
    
    def test_create_user_message(self, error_handler):
        """Test user message creation."""
        # Test basic message
        error = Exception("Test error")
        message = error_handler._create_user_message(error, ErrorCategory.API_CONNECTION, "")
        assert "Unable to connect to the data server" in message
        
        # Test message with context
        message = error_handler._create_user_message(error, ErrorCategory.API_CONNECTION, "loading data")
        assert "while loading data" in message
        
        # Test timeout message
        timeout_error = Exception("Request timeout occurred")
        message = error_handler._create_user_message(timeout_error, ErrorCategory.API_CONNECTION, "")
        assert "timed out" in message
        
        # Test connection refused message
        conn_error = Exception("Connection refused by server")
        message = error_handler._create_user_message(conn_error, ErrorCategory.API_CONNECTION, "")
        assert "not responding" in message
    
    def test_get_suggested_actions(self, error_handler):
        """Test suggested actions generation."""
        # Test API connection actions
        error = Exception("Connection failed")
        actions = error_handler._get_suggested_actions(error, ErrorCategory.API_CONNECTION)
        
        assert len(actions) > 0
        assert any("internet connection" in action.lower() for action in actions)
        assert any("refresh" in action.lower() for action in actions)
        
        # Test data processing actions
        actions = error_handler._get_suggested_actions(error, ErrorCategory.DATA_PROCESSING)
        assert any("data format" in action.lower() for action in actions)
        
        # Test visualization actions
        actions = error_handler._get_suggested_actions(error, ErrorCategory.VISUALIZATION)
        assert any("visualization" in action.lower() for action in actions)
        
        # Test user input actions
        actions = error_handler._get_suggested_actions(error, ErrorCategory.USER_INPUT)
        assert any("input" in action.lower() for action in actions)
    
    @patch('streamlit.warning')  # Changed from error to warning since ValueError gets WARNING severity
    @patch('streamlit.session_state', new_callable=lambda: {'error_count': 0, 'last_error_time': None})
    def test_handle_error_basic(self, mock_session_state, mock_st_warning, error_handler):
        """Test basic error handling."""
        test_error = ValueError("Test error")
        
        result = error_handler.handle_error(
            error=test_error,
            category=ErrorCategory.DATA_PROCESSING,
            context="test operation",
            show_to_user=True
        )
        
        # Check that error was logged
        assert len(error_handler.error_history) == 1
        
        error_info = error_handler.error_history[0]
        assert error_info.category == ErrorCategory.DATA_PROCESSING
        assert error_info.severity == ErrorSeverity.WARNING
        assert "Test error" in error_info.technical_details
        
        # Check that Streamlit warning was called (since ValueError gets WARNING severity)
        mock_st_warning.assert_called_once()
    
    def test_handle_error_with_fallback(self, error_handler):
        """Test error handling with fallback action."""
        test_error = Exception("Test error")
        fallback_result = "fallback_value"
        
        def fallback_action():
            return fallback_result
        
        with patch('streamlit.session_state', {'error_count': 0, 'last_error_time': None}):
            result = error_handler.handle_error(
                error=test_error,
                category=ErrorCategory.SYSTEM,
                show_to_user=False,
                fallback_action=fallback_action
            )
        
        assert result == fallback_result
    
    def test_handle_error_fallback_failure(self, error_handler):
        """Test error handling when fallback action fails."""
        test_error = Exception("Test error")
        
        def failing_fallback():
            raise Exception("Fallback failed")
        
        with patch('streamlit.session_state', {'error_count': 0, 'last_error_time': None}):
            result = error_handler.handle_error(
                error=test_error,
                category=ErrorCategory.SYSTEM,
                show_to_user=False,
                fallback_action=failing_fallback
            )
        
        assert result is None
    
    def test_cache_data(self, error_handler):
        """Test data caching functionality."""
        test_data = {"key": "value", "number": 42}
        cache_key = "test_data"
        
        # Cache data
        error_handler.cache_data(cache_key, test_data, ttl_minutes=60)
        
        # Verify data is cached
        assert cache_key in error_handler.cached_data
        assert error_handler.cached_data[cache_key] == test_data
        assert cache_key in error_handler.cache_timestamps
    
    def test_get_cached_data_valid(self, error_handler):
        """Test retrieving valid cached data."""
        test_data = {"cached": True}
        cache_key = "valid_data"
        
        # Cache data
        error_handler.cache_data(cache_key, test_data, ttl_minutes=60)
        
        # Retrieve data
        retrieved_data = error_handler.get_cached_data(cache_key, ttl_minutes=60)
        
        assert retrieved_data == test_data
    
    def test_get_cached_data_expired(self, error_handler):
        """Test retrieving expired cached data."""
        test_data = {"expired": True}
        cache_key = "expired_data"
        
        # Cache data with past timestamp
        error_handler.cached_data[cache_key] = test_data
        error_handler.cache_timestamps[cache_key] = datetime.now() - timedelta(hours=2)
        
        # Try to retrieve with 1 hour TTL
        retrieved_data = error_handler.get_cached_data(cache_key, ttl_minutes=60)
        
        assert retrieved_data is None
        assert cache_key not in error_handler.cached_data
    
    def test_get_cached_data_nonexistent(self, error_handler):
        """Test retrieving non-existent cached data."""
        retrieved_data = error_handler.get_cached_data("nonexistent_key", ttl_minutes=60)
        assert retrieved_data is None
    
    def test_clean_cache(self, error_handler):
        """Test cache cleaning functionality."""
        # Add some test data with different timestamps
        current_time = datetime.now()
        
        error_handler.cached_data["fresh"] = "fresh_data"
        error_handler.cache_timestamps["fresh"] = current_time
        
        error_handler.cached_data["old"] = "old_data"
        error_handler.cache_timestamps["old"] = current_time - timedelta(hours=2)
        
        # Clean cache with 1 hour TTL
        error_handler._clean_cache(ttl_minutes=60)
        
        # Fresh data should remain, old data should be removed
        assert "fresh" in error_handler.cached_data
        assert "old" not in error_handler.cached_data
    
    def test_monitor_connection_status_success(self, error_handler):
        """Test connection monitoring with successful API client."""
        mock_api_client = Mock()
        mock_api_client.health_check.return_value = {"status": "healthy"}
        
        status = error_handler.monitor_connection_status(mock_api_client)
        
        assert status['api'] == 'connected'
        assert status['consecutive_failures'] == 0
        assert 'last_check' in status
    
    def test_monitor_connection_status_failure(self, error_handler):
        """Test connection monitoring with failed API client."""
        mock_api_client = Mock()
        mock_api_client.health_check.side_effect = Exception("Connection failed")
        
        status = error_handler.monitor_connection_status(mock_api_client)
        
        assert status['api'] == 'disconnected'
        assert status['consecutive_failures'] > 0
    
    def test_monitor_connection_status_unhealthy_response(self, error_handler):
        """Test connection monitoring with unhealthy response."""
        mock_api_client = Mock()
        mock_api_client.health_check.return_value = {"status": "unhealthy", "message": "Database down"}
        
        status = error_handler.monitor_connection_status(mock_api_client)
        
        assert status['api'] == 'disconnected'
        assert status['consecutive_failures'] > 0

class TestErrorHandlerDecorator:
    """Test cases for error handler decorator."""
    
    def test_decorator_success(self):
        """Test decorator with successful function execution."""
        @error_handler_decorator(ErrorCategory.DATA_PROCESSING, "test function")
        def successful_function(x, y):
            return x + y
        
        with patch('streamlit.session_state', {'error_handler': ErrorHandler()}):
            result = successful_function(2, 3)
            assert result == 5
    
    def test_decorator_with_error(self):
        """Test decorator with function that raises error."""
        @error_handler_decorator(
            ErrorCategory.DATA_PROCESSING, 
            "test function",
            fallback_value="fallback"
        )
        def failing_function():
            raise ValueError("Function failed")
        
        with patch('streamlit.session_state', {'error_handler': ErrorHandler()}):
            with patch('streamlit.warning'):  # Mock streamlit warning
                result = failing_function()
                assert result == "fallback"

class TestUtilityFunctions:
    """Test cases for utility functions."""
    
    @patch('requests.get')
    def test_safe_api_call_success(self, mock_get):
        """Test successful API call."""
        mock_response = Mock()
        mock_response.json.return_value = {"data": "success"}
        mock_get.return_value = mock_response
        
        def api_function():
            return mock_response.json()
        
        with patch('streamlit.warning'), patch('streamlit.error'):
            result = safe_api_call(api_function)
            assert result == {"data": "success"}
    
    def test_safe_api_call_timeout(self):
        """Test API call with timeout."""
        import requests
        
        def timeout_function():
            raise requests.exceptions.Timeout("Request timed out")
        
        with patch('streamlit.warning') as mock_warning:
            result = safe_api_call(timeout_function)
            assert result is None
            mock_warning.assert_called_once()
    
    def test_safe_api_call_connection_error(self):
        """Test API call with connection error."""
        import requests
        
        def connection_error_function():
            raise requests.exceptions.ConnectionError("Connection failed")
        
        with patch('streamlit.error') as mock_error:
            result = safe_api_call(connection_error_function)
            assert result is None
            mock_error.assert_called_once()
    
    def test_safe_data_operation_success(self):
        """Test successful data operation."""
        import pandas as pd
        
        test_data = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
        
        def data_operation(data):
            return data.sum()
        
        with patch('streamlit.warning'), patch('streamlit.error'):
            result = safe_data_operation(data_operation, test_data, "sum operation")
            assert result is not None
    
    def test_safe_data_operation_empty_data(self):
        """Test data operation with empty data."""
        import pandas as pd
        
        empty_data = pd.DataFrame()
        
        def data_operation(data):
            return data.sum()
        
        with patch('streamlit.warning') as mock_warning:
            result = safe_data_operation(data_operation, empty_data, "sum operation")
            assert result is None
            mock_warning.assert_called_once()
    
    def test_safe_data_operation_none_data(self):
        """Test data operation with None data."""
        def data_operation(data):
            return data.sum()
        
        with patch('streamlit.warning') as mock_warning:
            result = safe_data_operation(data_operation, None, "sum operation")
            assert result is None
            mock_warning.assert_called_once()
    
    def test_safe_data_operation_value_error(self):
        """Test data operation with ValueError."""
        import pandas as pd
        
        test_data = pd.DataFrame({"a": [1, 2, 3]})
        
        def failing_operation(data):
            raise ValueError("Invalid operation")
        
        with patch('streamlit.error') as mock_error:
            result = safe_data_operation(failing_operation, test_data, "failing operation")
            assert result is None
            mock_error.assert_called_once()

class TestLoadingContext:
    """Test cases for LoadingContext."""
    
    def test_loading_context_basic(self):
        """Test basic loading context functionality."""
        from components.error_handler import LoadingContext
        
        with patch('streamlit.container') as mock_container, \
             patch('streamlit.empty') as mock_empty, \
             patch('streamlit.progress') as mock_progress:
            
            mock_container.return_value.__enter__ = Mock(return_value=None)
            mock_container.return_value.__exit__ = Mock(return_value=None)
            mock_container.return_value.empty = Mock()
            
            with LoadingContext("Test loading", show_progress=True) as ctx:
                assert ctx is not None
                
                # Test progress update
                ctx.update_progress(0.5, "Half done")
                ctx.update_message("Updated message")
    
    def test_loading_context_without_progress(self):
        """Test loading context without progress bar."""
        from components.error_handler import LoadingContext
        
        with patch('streamlit.container') as mock_container, \
             patch('streamlit.empty') as mock_empty:
            
            mock_container.return_value.__enter__ = Mock(return_value=None)
            mock_container.return_value.__exit__ = Mock(return_value=None)
            mock_container.return_value.empty = Mock()
            
            with LoadingContext("Test loading", show_progress=False) as ctx:
                assert ctx is not None
                assert ctx.progress_bar is None

if __name__ == "__main__":
    pytest.main([__file__])