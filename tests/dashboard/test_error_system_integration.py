"""
Integration tests for the complete error handling system
"""

import pytest
import pandas as pd
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import sys
import os

# Add the parent directory to the path to import components
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from components.error_system_integration import (
    IntegratedErrorSystem, ErrorBoundary, 
    get_integrated_error_system, safe_dashboard_operation, dashboard_error_boundary
)
from components.error_handler import ErrorCategory, ErrorSeverity

class TestIntegratedErrorSystem:
    """Test cases for IntegratedErrorSystem class."""
    
    @pytest.fixture
    def error_system(self):
        """Create an IntegratedErrorSystem instance for testing."""
        return IntegratedErrorSystem("http://localhost:8000")
    
    def test_initialization(self, error_system):
        """Test IntegratedErrorSystem initialization."""
        assert isinstance(error_system, IntegratedErrorSystem)
        assert error_system.api_base_url == "http://localhost:8000"
        assert hasattr(error_system, 'error_handler')
        assert hasattr(error_system, 'feedback_system')
        assert hasattr(error_system, 'connection_monitor')
    
    def test_get_error_category_by_component(self, error_system):
        """Test error category determination by component."""
        # API components
        category = error_system._get_error_category('api_client', Exception())
        assert category == ErrorCategory.API_CONNECTION
        
        # Visualization components
        category = error_system._get_error_category('map_visualization', Exception())
        assert category == ErrorCategory.VISUALIZATION
        
        # Data processing components
        category = error_system._get_error_category('data_manager', Exception())
        assert category == ErrorCategory.DATA_PROCESSING
        
        # Chat components
        category = error_system._get_error_category('chat_interface', Exception())
        assert category == ErrorCategory.USER_INPUT
    
    def test_get_error_category_by_type(self, error_system):
        """Test error category determination by error type."""
        # Network errors
        category = error_system._get_error_category('unknown', ConnectionError())
        assert category == ErrorCategory.NETWORK
        
        # Data processing errors
        category = error_system._get_error_category('unknown', ValueError())
        assert category == ErrorCategory.DATA_PROCESSING
        
        # System errors
        category = error_system._get_error_category('unknown', RuntimeError())
        assert category == ErrorCategory.SYSTEM
    
    @patch('streamlit.error')
    def test_handle_dashboard_error_basic(self, mock_error, error_system):
        """Test basic dashboard error handling."""
        test_error = ValueError("Test error")
        fallback_data = "fallback"
        
        with patch.object(error_system.error_handler, 'handle_error', return_value=fallback_data) as mock_handle:
            result = error_system.handle_dashboard_error(
                error=test_error,
                context="test operation",
                component="data_manager",
                fallback_data=fallback_data
            )
            
            assert result == fallback_data
            mock_handle.assert_called_once()
    
    def test_monitor_system_health_healthy(self, error_system):
        """Test system health monitoring with healthy system."""
        mock_api_client = Mock()
        
        with patch.object(error_system.error_handler, 'monitor_connection_status', 
                         return_value={'api': 'connected'}), \
             patch.object(error_system.connection_monitor, 'check_all_services', 
                         return_value={}):
            
            health = error_system.monitor_system_health(mock_api_client)
            
            assert health['overall_status'] == 'healthy'
            assert 'components' in health
            assert 'recommendations' in health
    
    def test_monitor_system_health_degraded(self, error_system):
        """Test system health monitoring with degraded system."""
        mock_api_client = Mock()
        
        # Add some recent errors
        from components.error_handler import ErrorInfo
        recent_errors = [
            ErrorInfo(
                category=ErrorCategory.API_CONNECTION,
                severity=ErrorSeverity.ERROR,
                message="Test error",
                technical_details="Test",
                suggested_actions=[],
                timestamp=datetime.now()
            ) for _ in range(6)  # More than 5 errors
        ]
        error_system.error_handler.error_history = recent_errors
        
        with patch.object(error_system.error_handler, 'monitor_connection_status', 
                         return_value={'api': 'disconnected'}), \
             patch.object(error_system.connection_monitor, 'check_all_services', 
                         return_value={}):
            
            health = error_system.monitor_system_health(mock_api_client)
            
            assert health['overall_status'] == 'degraded'
            assert len(health['recommendations']) > 0
    
    def test_safe_execute_with_feedback_success(self, error_system):
        """Test safe execution with successful operation."""
        def test_operation(x, y):
            return x + y
        
        result = error_system.safe_execute_with_feedback(
            operation=test_operation,
            operation_name="addition",
            component="test",
            x=2, y=3
        )
        
        assert result == 5
    
    def test_safe_execute_with_feedback_error(self, error_system):
        """Test safe execution with failing operation."""
        def failing_operation():
            raise ValueError("Operation failed")
        
        fallback_result = "fallback"
        
        with patch.object(error_system, 'handle_dashboard_error', return_value=fallback_result):
            result = error_system.safe_execute_with_feedback(
                operation=failing_operation,
                operation_name="failing operation",
                component="test",
                fallback_result=fallback_result
            )
            
            assert result == fallback_result
    
    def test_create_error_boundary(self, error_system):
        """Test error boundary creation."""
        boundary = error_system.create_error_boundary("test_component")
        
        assert isinstance(boundary, ErrorBoundary)
        assert boundary.component_name == "test_component"
        assert boundary.error_system is error_system

class TestErrorBoundary:
    """Test cases for ErrorBoundary class."""
    
    @pytest.fixture
    def error_system(self):
        """Create an IntegratedErrorSystem instance for testing."""
        return IntegratedErrorSystem("http://localhost:8000")
    
    def test_error_boundary_success(self, error_system):
        """Test error boundary with successful execution."""
        with error_system.create_error_boundary("test_component"):
            result = 2 + 3
            
        assert result == 5
    
    def test_error_boundary_with_error(self, error_system):
        """Test error boundary with error."""
        with patch.object(error_system, 'handle_dashboard_error') as mock_handle:
            with error_system.create_error_boundary("test_component"):
                raise ValueError("Test error")
            
            # Error should be handled
            mock_handle.assert_called_once()

class TestUtilityFunctions:
    """Test cases for utility functions."""
    
    @patch('streamlit.session_state', {})
    def test_get_integrated_error_system_new(self):
        """Test getting new integrated error system."""
        system = get_integrated_error_system()
        
        assert isinstance(system, IntegratedErrorSystem)
    
    def test_safe_dashboard_operation_success(self):
        """Test safe dashboard operation with success."""
        def test_operation(x, y):
            return x * y
        
        with patch('components.error_system_integration.get_integrated_error_system') as mock_get:
            mock_system = Mock()
            mock_system.safe_execute_with_feedback.return_value = 15
            mock_get.return_value = mock_system
            
            result = safe_dashboard_operation(test_operation, "multiplication", "test", None, 3, 5)
            
            assert result == 15
            mock_system.safe_execute_with_feedback.assert_called_once()
    
    def test_dashboard_error_boundary_decorator(self):
        """Test dashboard error boundary decorator."""
        @dashboard_error_boundary("test_component")
        def test_function(x):
            return x * 2
        
        with patch('components.error_system_integration.get_integrated_error_system') as mock_get:
            mock_system = Mock()
            mock_boundary = Mock()
            mock_boundary.__enter__ = Mock(return_value=mock_boundary)
            mock_boundary.__exit__ = Mock(return_value=False)
            mock_system.create_error_boundary.return_value = mock_boundary
            mock_get.return_value = mock_system
            
            result = test_function(5)
            
            assert result == 10
            mock_system.create_error_boundary.assert_called_once_with("test_component")

class TestIntegrationScenarios:
    """Test cases for complete integration scenarios."""
    
    @pytest.fixture
    def error_system(self):
        """Create an IntegratedErrorSystem instance for testing."""
        return IntegratedErrorSystem("http://localhost:8000")
    
    def test_api_connection_failure_scenario(self, error_system):
        """Test complete scenario of API connection failure."""
        # Simulate API connection failure
        api_error = ConnectionError("Connection refused")
        
        with patch.object(error_system.feedback_system, 'show_notification') as mock_notify:
            result = error_system.handle_dashboard_error(
                error=api_error,
                context="fetching data",
                component="api_client",
                show_feedback=True,
                fallback_data=pd.DataFrame()
            )
            
            # Should show appropriate notification
            mock_notify.assert_called_once()
            
            # Should return fallback data
            assert isinstance(result, pd.DataFrame)
    
    def test_data_processing_error_scenario(self, error_system):
        """Test complete scenario of data processing error."""
        # Simulate data processing error
        data_error = ValueError("Invalid data format")
        
        with patch.object(error_system.feedback_system, 'show_notification') as mock_notify:
            result = error_system.handle_dashboard_error(
                error=data_error,
                context="processing measurements",
                component="data_manager",
                show_feedback=True,
                fallback_data=None
            )
            
            # Should show appropriate notification
            mock_notify.assert_called_once()
    
    def test_visualization_error_scenario(self, error_system):
        """Test complete scenario of visualization error."""
        # Simulate visualization error
        viz_error = RuntimeError("Plot generation failed")
        
        with patch.object(error_system.feedback_system, 'show_notification') as mock_notify:
            result = error_system.handle_dashboard_error(
                error=viz_error,
                context="creating map",
                component="map_visualization",
                show_feedback=True,
                fallback_data="Simple text display"
            )
            
            # Should show appropriate notification
            mock_notify.assert_called_once()
            
            # Should return fallback
            assert result == "Simple text display"
    
    def test_complete_error_recovery_workflow(self, error_system):
        """Test complete error recovery workflow."""
        # Simulate multiple errors and recovery
        errors = [
            (ConnectionError("API down"), "api_client"),
            (ValueError("Bad data"), "data_manager"),
            (RuntimeError("Viz failed"), "map_visualization")
        ]
        
        results = []
        for error, component in errors:
            with patch.object(error_system.feedback_system, 'show_notification'):
                result = error_system.handle_dashboard_error(
                    error=error,
                    context="test operation",
                    component=component,
                    show_feedback=True,
                    fallback_data=f"fallback_{component}"
                )
                results.append(result)
        
        # Should have handled all errors with fallbacks
        assert len(results) == 3
        assert all(result is not None for result in results)
        
        # Should have error history
        assert len(error_system.error_handler.error_history) >= 3
    
    def test_system_health_monitoring_integration(self, error_system):
        """Test integration of system health monitoring."""
        mock_api_client = Mock()
        
        # Simulate mixed health status
        with patch.object(error_system.error_handler, 'monitor_connection_status', 
                         return_value={'api': 'connected'}), \
             patch.object(error_system.connection_monitor, 'check_all_services', 
                         return_value={'service1': Mock(status='connected')}):
            
            health = error_system.monitor_system_health(mock_api_client)
            
            assert 'overall_status' in health
            assert 'components' in health
            assert 'recommendations' in health
            
            # Should include both error handler and connection monitor data
            assert 'api' in health['components']
            assert 'services' in health['components']
            assert 'recent_errors' in health['components']

if __name__ == "__main__":
    pytest.main([__file__])