"""
Unit tests for Connection Monitor Component
"""

import pytest
import requests
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import json
import sys
import os

# Add the parent directory to the path to import components
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from components.connection_monitor import (
    ConnectionMonitor, ConnectionStatus, ServiceType, ServiceHealth, ConnectionEvent,
    setup_default_monitoring, get_connection_monitor
)

class TestConnectionMonitor:
    """Test cases for ConnectionMonitor class."""
    
    @pytest.fixture
    def connection_monitor(self):
        """Create a ConnectionMonitor instance for testing."""
        return ConnectionMonitor(check_interval=30)
    
    @pytest.fixture
    def mock_streamlit(self):
        """Mock Streamlit functions."""
        with patch.multiple(
            'streamlit',
            session_state=Mock(),
            success=Mock(),
            error=Mock(),
            warning=Mock(),
            info=Mock(),
            subheader=Mock(),
            columns=Mock(),
            button=Mock(),
            caption=Mock(),
            metric=Mock(),
            expander=Mock(),
            write=Mock(),
            rerun=Mock()
        ) as mocks:
            # Initialize session state mock
            mocks['session_state'].__contains__ = Mock(return_value=False)
            mocks['session_state'].__getitem__ = Mock(return_value={})
            mocks['session_state'].__setitem__ = Mock()
            mocks['session_state'].get = Mock(return_value={})
            yield mocks
    
    def test_initialization(self, connection_monitor):
        """Test ConnectionMonitor initialization."""
        assert isinstance(connection_monitor, ConnectionMonitor)
        assert connection_monitor.check_interval == 30
        assert connection_monitor.services == {}
        assert connection_monitor.connection_events == []
        assert connection_monitor.monitoring_active is False
        assert connection_monitor.monitor_thread is None
    
    def test_register_service(self, connection_monitor):
        """Test service registration."""
        service_name = "test_api"
        service_type = ServiceType.API
        health_url = "http://localhost:8000/health"
        timeout = 10
        
        connection_monitor.register_service(service_name, service_type, health_url, timeout)
        
        assert service_name in connection_monitor.services
        service_config = connection_monitor.services[service_name]
        assert service_config['type'] == service_type
        assert service_config['health_url'] == health_url
        assert service_config['timeout'] == timeout
        assert isinstance(service_config['health'], ServiceHealth)
        assert service_config['health'].service_name == service_name
        assert service_config['health'].status == ConnectionStatus.UNKNOWN
    
    @patch('requests.get')
    @patch('streamlit.session_state', {})
    def test_check_service_health_success(self, mock_get, connection_monitor):
        """Test successful service health check."""
        # Register a service
        service_name = "test_api"
        connection_monitor.register_service(
            service_name, ServiceType.API, "http://localhost:8000/health", 10
        )
        
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "healthy"}
        mock_get.return_value = mock_response
        
        health = connection_monitor.check_service_health(service_name)
        
        assert health.status == ConnectionStatus.CONNECTED
        assert health.error_message is None
        assert health.consecutive_failures == 0
        assert health.response_time is not None
        assert health.response_time > 0
    
    @patch('requests.get')
    @patch('streamlit.session_state', {})
    def test_check_service_health_unhealthy_response(self, mock_get, connection_monitor):
        """Test service health check with unhealthy response."""
        # Register a service
        service_name = "test_api"
        connection_monitor.register_service(
            service_name, ServiceType.API, "http://localhost:8000/health", 10
        )
        
        # Mock unhealthy response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "unhealthy", "message": "Database down"}
        mock_get.return_value = mock_response
        
        health = connection_monitor.check_service_health(service_name)
        
        assert health.status == ConnectionStatus.ERROR
        assert "Database down" in health.error_message
        assert health.consecutive_failures == 1
    
    @patch('requests.get')
    @patch('streamlit.session_state', {})
    def test_check_service_health_http_error(self, mock_get, connection_monitor):
        """Test service health check with HTTP error."""
        # Register a service
        service_name = "test_api"
        connection_monitor.register_service(
            service_name, ServiceType.API, "http://localhost:8000/health", 10
        )
        
        # Mock HTTP error response
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.reason = "Internal Server Error"
        mock_get.return_value = mock_response
        
        health = connection_monitor.check_service_health(service_name)
        
        assert health.status == ConnectionStatus.ERROR
        assert "HTTP 500" in health.error_message
        assert health.consecutive_failures == 1
    
    @patch('requests.get')
    @patch('streamlit.session_state', {})
    def test_check_service_health_timeout(self, mock_get, connection_monitor):
        """Test service health check with timeout."""
        # Register a service
        service_name = "test_api"
        connection_monitor.register_service(
            service_name, ServiceType.API, "http://localhost:8000/health", 10
        )
        
        # Mock timeout exception
        mock_get.side_effect = requests.exceptions.Timeout("Request timed out")
        
        health = connection_monitor.check_service_health(service_name)
        
        assert health.status == ConnectionStatus.DISCONNECTED
        assert "timeout" in health.error_message.lower()
        assert health.consecutive_failures == 1
        assert health.response_time == 10  # Should be set to timeout value
    
    @patch('requests.get')
    @patch('streamlit.session_state', {})
    def test_check_service_health_connection_error(self, mock_get, connection_monitor):
        """Test service health check with connection error."""
        # Register a service
        service_name = "test_api"
        connection_monitor.register_service(
            service_name, ServiceType.API, "http://localhost:8000/health", 10
        )
        
        # Mock connection error
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection refused")
        
        health = connection_monitor.check_service_health(service_name)
        
        assert health.status == ConnectionStatus.DISCONNECTED
        assert "refused" in health.error_message.lower()
        assert health.consecutive_failures == 1
        assert health.response_time is None
    
    def test_check_service_health_unregistered_service(self, connection_monitor):
        """Test checking health of unregistered service."""
        with pytest.raises(ValueError, match="Service nonexistent not registered"):
            connection_monitor.check_service_health("nonexistent")
    
    @patch('streamlit.session_state', {})
    def test_check_all_services(self, connection_monitor):
        """Test checking all registered services."""
        # Register multiple services
        connection_monitor.register_service(
            "api1", ServiceType.API, "http://localhost:8000/health", 10
        )
        connection_monitor.register_service(
            "api2", ServiceType.DATABASE, "http://localhost:8001/health", 10
        )
        
        with patch.object(connection_monitor, 'check_service_health') as mock_check:
            mock_health1 = ServiceHealth(
                "api1", ServiceType.API, ConnectionStatus.CONNECTED,
                datetime.now(), 0.1, None, 0, 100.0
            )
            mock_health2 = ServiceHealth(
                "api2", ServiceType.DATABASE, ConnectionStatus.DISCONNECTED,
                datetime.now(), None, "Connection failed", 1, 95.0
            )
            mock_check.side_effect = [mock_health1, mock_health2]
            
            results = connection_monitor.check_all_services()
            
            assert len(results) == 2
            assert "api1" in results
            assert "api2" in results
            assert results["api1"].status == ConnectionStatus.CONNECTED
            assert results["api2"].status == ConnectionStatus.DISCONNECTED
    
    def test_get_overall_status_all_connected(self, connection_monitor):
        """Test overall status when all services are connected."""
        # Register services and set their health status
        connection_monitor.register_service(
            "api1", ServiceType.API, "http://localhost:8000/health", 10
        )
        connection_monitor.register_service(
            "api2", ServiceType.DATABASE, "http://localhost:8001/health", 10
        )
        
        # Set both services as connected
        connection_monitor.services["api1"]["health"].status = ConnectionStatus.CONNECTED
        connection_monitor.services["api2"]["health"].status = ConnectionStatus.CONNECTED
        
        overall_status = connection_monitor.get_overall_status()
        assert overall_status == ConnectionStatus.CONNECTED
    
    def test_get_overall_status_all_disconnected(self, connection_monitor):
        """Test overall status when all services are disconnected."""
        # Register services and set their health status
        connection_monitor.register_service(
            "api1", ServiceType.API, "http://localhost:8000/health", 10
        )
        connection_monitor.register_service(
            "api2", ServiceType.DATABASE, "http://localhost:8001/health", 10
        )
        
        # Set both services as disconnected
        connection_monitor.services["api1"]["health"].status = ConnectionStatus.DISCONNECTED
        connection_monitor.services["api2"]["health"].status = ConnectionStatus.DISCONNECTED
        
        overall_status = connection_monitor.get_overall_status()
        assert overall_status == ConnectionStatus.DISCONNECTED
    
    def test_get_overall_status_partial_connectivity(self, connection_monitor):
        """Test overall status with partial connectivity."""
        # Register services and set their health status
        connection_monitor.register_service(
            "api1", ServiceType.API, "http://localhost:8000/health", 10
        )
        connection_monitor.register_service(
            "api2", ServiceType.DATABASE, "http://localhost:8001/health", 10
        )
        
        # Set one connected, one disconnected
        connection_monitor.services["api1"]["health"].status = ConnectionStatus.CONNECTED
        connection_monitor.services["api2"]["health"].status = ConnectionStatus.DISCONNECTED
        
        overall_status = connection_monitor.get_overall_status()
        assert overall_status == ConnectionStatus.ERROR
    
    def test_get_overall_status_no_services(self, connection_monitor):
        """Test overall status with no registered services."""
        overall_status = connection_monitor.get_overall_status()
        assert overall_status == ConnectionStatus.UNKNOWN
    
    def test_log_connection_event(self, connection_monitor):
        """Test logging connection events."""
        service_name = "test_api"
        event_type = "connected"
        details = "Successfully connected"
        
        connection_monitor._log_connection_event(service_name, event_type, details)
        
        assert len(connection_monitor.connection_events) == 1
        event = connection_monitor.connection_events[0]
        assert event.service_name == service_name
        assert event.event_type == event_type
        assert event.details == details
        assert isinstance(event.timestamp, datetime)
    
    def test_log_connection_event_limit(self, connection_monitor):
        """Test connection event logging with limit."""
        # Add more than 100 events
        for i in range(105):
            connection_monitor._log_connection_event(f"service_{i}", "test", f"event_{i}")
        
        # Should keep only last 100 events
        assert len(connection_monitor.connection_events) == 100
        
        # Should have the most recent events
        last_event = connection_monitor.connection_events[-1]
        assert last_event.service_name == "service_104"
    
    @patch('streamlit.session_state', {'offline_mode': False})
    def test_enable_offline_mode(self, connection_monitor):
        """Test enabling offline mode."""
        with patch('streamlit.warning') as mock_warning:
            connection_monitor.enable_offline_mode()
            mock_warning.assert_called_once()
    
    @patch('streamlit.session_state', {'offline_mode': True})
    def test_disable_offline_mode(self, connection_monitor):
        """Test disabling offline mode."""
        with patch('streamlit.success') as mock_success:
            connection_monitor.disable_offline_mode()
            mock_success.assert_called_once()
    
    @patch('streamlit.session_state', {'offline_mode': True})
    def test_is_offline_mode_true(self, connection_monitor):
        """Test checking offline mode when enabled."""
        assert connection_monitor.is_offline_mode() is True
    
    @patch('streamlit.session_state', {'offline_mode': False})
    def test_is_offline_mode_false(self, connection_monitor):
        """Test checking offline mode when disabled."""
        assert connection_monitor.is_offline_mode() is False
    
    def test_get_connection_history(self, connection_monitor):
        """Test getting connection history."""
        # Add events with different timestamps
        now = datetime.now()
        
        # Recent event (within 24 hours)
        recent_event = ConnectionEvent(
            timestamp=now - timedelta(hours=1),
            service_name="api1",
            event_type="connected",
            details="Recent connection"
        )
        
        # Old event (older than 24 hours)
        old_event = ConnectionEvent(
            timestamp=now - timedelta(hours=25),
            service_name="api1",
            event_type="disconnected",
            details="Old disconnection"
        )
        
        connection_monitor.connection_events = [old_event, recent_event]
        
        # Get history for last 24 hours
        history = connection_monitor.get_connection_history(hours=24)
        
        assert len(history) == 1
        assert history[0] == recent_event
    
    def test_render_connection_status_all_connected(self, connection_monitor, mock_streamlit):
        """Test rendering connection status when all services are connected."""
        # Register a service and set it as connected
        connection_monitor.register_service(
            "api1", ServiceType.API, "http://localhost:8000/health", 10
        )
        connection_monitor.services["api1"]["health"].status = ConnectionStatus.CONNECTED
        
        # Mock columns
        mock_col1, mock_col2, mock_col3 = Mock(), Mock(), Mock()
        mock_streamlit['columns'].return_value = [mock_col1, mock_col2, mock_col3]
        
        # Mock column context managers
        for col in [mock_col1, mock_col2, mock_col3]:
            col.__enter__ = Mock(return_value=col)
            col.__exit__ = Mock(return_value=None)
        
        connection_monitor.render_connection_status()
        
        # Should call success for all connected
        mock_streamlit['success'].assert_called_once()
    
    def test_render_connection_status_all_disconnected(self, connection_monitor, mock_streamlit):
        """Test rendering connection status when all services are disconnected."""
        # Register a service and set it as disconnected
        connection_monitor.register_service(
            "api1", ServiceType.API, "http://localhost:8000/health", 10
        )
        connection_monitor.services["api1"]["health"].status = ConnectionStatus.DISCONNECTED
        
        # Mock columns
        mock_col1, mock_col2, mock_col3 = Mock(), Mock(), Mock()
        mock_streamlit['columns'].return_value = [mock_col1, mock_col2, mock_col3]
        
        # Mock column context managers
        for col in [mock_col1, mock_col2, mock_col3]:
            col.__enter__ = Mock(return_value=col)
            col.__exit__ = Mock(return_value=None)
        
        connection_monitor.render_connection_status()
        
        # Should call error for all disconnected
        mock_streamlit['error'].assert_called_once()
    
    def test_render_connection_indicator_connected(self, connection_monitor, mock_streamlit):
        """Test rendering connection indicator when connected."""
        # Register a service and set it as connected
        connection_monitor.register_service(
            "api1", ServiceType.API, "http://localhost:8000/health", 10
        )
        connection_monitor.services["api1"]["health"].status = ConnectionStatus.CONNECTED
        
        connection_monitor.render_connection_indicator()
        
        # Should call success
        mock_streamlit['success'].assert_called_once()
    
    def test_render_connection_indicator_disconnected(self, connection_monitor, mock_streamlit):
        """Test rendering connection indicator when disconnected."""
        # Register a service and set it as disconnected
        connection_monitor.register_service(
            "api1", ServiceType.API, "http://localhost:8000/health", 10
        )
        connection_monitor.services["api1"]["health"].status = ConnectionStatus.DISCONNECTED
        
        connection_monitor.render_connection_indicator()
        
        # Should call error
        mock_streamlit['error'].assert_called_once()
    
    @patch('streamlit.session_state', {'offline_mode': True})
    def test_render_offline_banner(self, connection_monitor, mock_streamlit):
        """Test rendering offline banner."""
        # Mock columns
        mock_col1, mock_col2 = Mock(), Mock()
        mock_streamlit['columns'].return_value = [mock_col1, mock_col2]
        
        # Mock column context managers
        for col in [mock_col1, mock_col2]:
            col.__enter__ = Mock(return_value=col)
            col.__exit__ = Mock(return_value=None)
        
        # Mock button not clicked
        mock_streamlit['button'].return_value = False
        
        connection_monitor.render_offline_banner()
        
        # Should show warning for offline mode
        mock_streamlit['warning'].assert_called_once()
    
    def test_auto_check_connections_all_healthy(self, connection_monitor):
        """Test auto check connections when all services are healthy."""
        # Register services
        connection_monitor.register_service(
            "api1", ServiceType.API, "http://localhost:8000/health", 10
        )
        
        # Mock healthy response
        mock_health = ServiceHealth(
            "api1", ServiceType.API, ConnectionStatus.CONNECTED,
            datetime.now(), 0.1, None, 0, 100.0
        )
        
        with patch.object(connection_monitor, 'check_all_services', return_value={"api1": mock_health}), \
             patch.object(connection_monitor, 'is_offline_mode', return_value=True), \
             patch.object(connection_monitor, 'disable_offline_mode') as mock_disable, \
             patch('streamlit.session_state', {'connection_alerts': []}):
            
            connection_monitor.auto_check_connections()
            
            # Should disable offline mode if it was enabled
            mock_disable.assert_called_once()
    
    def test_auto_check_connections_all_failed(self, connection_monitor):
        """Test auto check connections when all services fail."""
        # Register services
        connection_monitor.register_service(
            "api1", ServiceType.API, "http://localhost:8000/health", 10
        )
        
        # Mock failed response
        mock_health = ServiceHealth(
            "api1", ServiceType.API, ConnectionStatus.DISCONNECTED,
            datetime.now(), None, "Connection failed", 3, 50.0
        )
        
        with patch.object(connection_monitor, 'check_all_services', return_value={"api1": mock_health}), \
             patch.object(connection_monitor, 'is_offline_mode', return_value=False), \
             patch.object(connection_monitor, 'enable_offline_mode') as mock_enable, \
             patch('streamlit.session_state', {'connection_alerts': []}), \
             patch('streamlit.error'):
            
            connection_monitor.auto_check_connections()
            
            # Should enable offline mode
            mock_enable.assert_called_once()

class TestUtilityFunctions:
    """Test cases for utility functions."""
    
    def test_setup_default_monitoring(self):
        """Test setting up default monitoring configuration."""
        api_base_url = "http://localhost:8000"
        
        monitor = setup_default_monitoring(api_base_url)
        
        assert isinstance(monitor, ConnectionMonitor)
        assert "ARGO API" in monitor.services
        assert "Database" in monitor.services
        assert "ChromaDB" in monitor.services
        
        # Check service configurations
        api_service = monitor.services["ARGO API"]
        assert api_service['type'] == ServiceType.API
        assert api_service['health_url'] == f"{api_base_url}/health"
        assert api_service['timeout'] == 10
    
    @patch('streamlit.session_state', {})
    def test_get_connection_monitor_new(self):
        """Test getting connection monitor when not exists."""
        monitor = get_connection_monitor()
        
        assert isinstance(monitor, ConnectionMonitor)
    
    @patch('streamlit.session_state', {'connection_monitor': ConnectionMonitor()})
    def test_get_connection_monitor_existing(self):
        """Test getting existing connection monitor."""
        existing_monitor = ConnectionMonitor()
        
        with patch('streamlit.session_state', {'connection_monitor': existing_monitor}):
            monitor = get_connection_monitor()
            
            assert monitor is existing_monitor

if __name__ == "__main__":
    pytest.main([__file__])