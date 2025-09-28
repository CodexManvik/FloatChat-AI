"""
Connection Monitor Component for ARGO Float Dashboard

This component monitors API connections, handles offline scenarios,
and provides connection status feedback to users.
"""

import streamlit as st
import requests
import time
import threading
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass
import logging
import json

logger = logging.getLogger(__name__)

class ConnectionStatus(Enum):
    """Connection status states"""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    ERROR = "error"
    UNKNOWN = "unknown"

class ServiceType(Enum):
    """Types of services to monitor"""
    API = "api"
    DATABASE = "database"
    CHROMADB = "chromadb"
    EXTERNAL = "external"

@dataclass
class ServiceHealth:
    """Health information for a service"""
    service_name: str
    service_type: ServiceType
    status: ConnectionStatus
    last_check: datetime
    response_time: Optional[float]
    error_message: Optional[str]
    consecutive_failures: int
    uptime_percentage: float

@dataclass
class ConnectionEvent:
    """Connection event for logging"""
    timestamp: datetime
    service_name: str
    event_type: str  # connected, disconnected, error, timeout
    details: str

class ConnectionMonitor:
    """Comprehensive connection monitoring system"""
    
    def __init__(self, check_interval: int = 30):
        """
        Initialize connection monitor
        
        Args:
            check_interval: Interval between health checks in seconds
        """
        self.check_interval = check_interval
        self.services = {}
        self.connection_events = []
        self.monitoring_active = False
        self.monitor_thread = None
        
        # Initialize session state
        try:
            if hasattr(st.session_state, '__contains__') and 'connection_monitor_initialized' not in st.session_state:
                st.session_state.connection_monitor_initialized = True
                st.session_state.connection_status = {}
                st.session_state.last_health_check = None
                st.session_state.offline_mode = False
                st.session_state.connection_alerts = []
        except (AttributeError, TypeError):
            # Session state not available (e.g., in tests)
            pass
    
    def register_service(self, 
                        service_name: str,
                        service_type: ServiceType,
                        health_check_url: str,
                        timeout: int = 10) -> None:
        """
        Register a service for monitoring
        
        Args:
            service_name: Name of the service
            service_type: Type of service
            health_check_url: URL for health check
            timeout: Request timeout in seconds
        """
        try:
            self.services[service_name] = {
                'type': service_type,
                'health_url': health_check_url,
                'timeout': timeout,
                'health': ServiceHealth(
                    service_name=service_name,
                    service_type=service_type,
                    status=ConnectionStatus.UNKNOWN,
                    last_check=datetime.now(),
                    response_time=None,
                    error_message=None,
                    consecutive_failures=0,
                    uptime_percentage=100.0
                )
            }
            
            logger.info(f"Registered service for monitoring: {service_name}")
            
        except Exception as e:
            logger.error(f"Error registering service {service_name}: {e}")
    
    def check_service_health(self, service_name: str) -> ServiceHealth:
        """
        Check health of a specific service
        
        Args:
            service_name: Name of the service to check
            
        Returns:
            ServiceHealth object with current status
        """
        try:
            if service_name not in self.services:
                raise ValueError(f"Service {service_name} not registered")
            
            service_config = self.services[service_name]
            health = service_config['health']
            
            # Record check time
            check_start = time.time()
            health.last_check = datetime.now()
            
            try:
                # Make health check request
                response = requests.get(
                    service_config['health_url'],
                    timeout=service_config['timeout']
                )
                
                response_time = time.time() - check_start
                health.response_time = response_time
                
                # Check response
                if response.status_code == 200:
                    # Try to parse JSON response
                    try:
                        health_data = response.json()
                        if health_data.get('status') == 'healthy':
                            health.status = ConnectionStatus.CONNECTED
                            health.error_message = None
                            health.consecutive_failures = 0
                        else:
                            health.status = ConnectionStatus.ERROR
                            health.error_message = f"Service reports unhealthy: {health_data.get('message', 'Unknown')}"
                            health.consecutive_failures += 1
                    except json.JSONDecodeError:
                        # Non-JSON response but 200 status - assume healthy
                        health.status = ConnectionStatus.CONNECTED
                        health.error_message = None
                        health.consecutive_failures = 0
                else:
                    health.status = ConnectionStatus.ERROR
                    health.error_message = f"HTTP {response.status_code}: {response.reason}"
                    health.consecutive_failures += 1
            
            except requests.exceptions.Timeout:
                health.status = ConnectionStatus.DISCONNECTED
                health.error_message = "Request timeout"
                health.consecutive_failures += 1
                health.response_time = service_config['timeout']
            
            except requests.exceptions.ConnectionError:
                health.status = ConnectionStatus.DISCONNECTED
                health.error_message = "Connection refused"
                health.consecutive_failures += 1
                health.response_time = None
            
            except Exception as e:
                health.status = ConnectionStatus.ERROR
                health.error_message = str(e)
                health.consecutive_failures += 1
                health.response_time = None
            
            # Log connection event
            self._log_connection_event(
                service_name=service_name,
                event_type=health.status.value,
                details=health.error_message or "Health check completed"
            )
            
            # Update session state
            try:
                if hasattr(st.session_state, 'connection_status'):
                    st.session_state.connection_status[service_name] = {
                        'status': health.status.value,
                        'last_check': health.last_check.isoformat(),
                        'response_time': health.response_time,
                        'error_message': health.error_message,
                        'consecutive_failures': health.consecutive_failures
                    }
            except (AttributeError, TypeError):
                # Session state not available (e.g., in tests)
                pass
            
            return health
            
        except Exception as e:
            logger.error(f"Error checking health for {service_name}: {e}")
            
            # Return error health status
            error_health = ServiceHealth(
                service_name=service_name,
                service_type=ServiceType.API,
                status=ConnectionStatus.ERROR,
                last_check=datetime.now(),
                response_time=None,
                error_message=str(e),
                consecutive_failures=999,
                uptime_percentage=0.0
            )
            
            return error_health
    
    def check_all_services(self) -> Dict[str, ServiceHealth]:
        """
        Check health of all registered services
        
        Returns:
            Dictionary mapping service names to their health status
        """
        try:
            health_results = {}
            
            for service_name in self.services.keys():
                health_results[service_name] = self.check_service_health(service_name)
            
            # Update last health check time
            try:
                if hasattr(st.session_state, 'last_health_check'):
                    st.session_state.last_health_check = datetime.now()
            except (AttributeError, TypeError):
                # Session state not available (e.g., in tests)
                pass
            
            return health_results
            
        except Exception as e:
            logger.error(f"Error checking all services: {e}")
            return {}
    
    def _log_connection_event(self, service_name: str, event_type: str, details: str):
        """Log a connection event"""
        try:
            event = ConnectionEvent(
                timestamp=datetime.now(),
                service_name=service_name,
                event_type=event_type,
                details=details
            )
            
            self.connection_events.append(event)
            
            # Keep only last 100 events
            if len(self.connection_events) > 100:
                self.connection_events = self.connection_events[-100:]
                
        except Exception as e:
            logger.error(f"Error logging connection event: {e}")
    
    def get_overall_status(self) -> ConnectionStatus:
        """
        Get overall connection status across all services
        
        Returns:
            Overall connection status
        """
        try:
            if not self.services:
                return ConnectionStatus.UNKNOWN
            
            statuses = []
            for service_config in self.services.values():
                statuses.append(service_config['health'].status)
            
            # Determine overall status
            if all(status == ConnectionStatus.CONNECTED for status in statuses):
                return ConnectionStatus.CONNECTED
            elif any(status == ConnectionStatus.CONNECTED for status in statuses):
                return ConnectionStatus.ERROR  # Partial connectivity
            elif all(status == ConnectionStatus.DISCONNECTED for status in statuses):
                return ConnectionStatus.DISCONNECTED
            else:
                return ConnectionStatus.ERROR
                
        except Exception as e:
            logger.error(f"Error getting overall status: {e}")
            return ConnectionStatus.ERROR
    
    def render_connection_status(self, detailed: bool = False) -> None:
        """
        Render connection status in Streamlit
        
        Args:
            detailed: Whether to show detailed status for all services
        """
        try:
            st.subheader("🔗 Connection Status")
            
            # Overall status
            overall_status = self.get_overall_status()
            
            col1, col2, col3 = st.columns([2, 2, 1])
            
            with col1:
                if overall_status == ConnectionStatus.CONNECTED:
                    st.success("🟢 All Systems Connected")
                elif overall_status == ConnectionStatus.DISCONNECTED:
                    st.error("🔴 All Systems Disconnected")
                elif overall_status == ConnectionStatus.ERROR:
                    st.warning("🟡 Partial Connectivity")
                else:
                    st.info("🔵 Status Unknown")
            
            with col2:
                last_check = st.session_state.get('last_health_check')
                if last_check:
                    if isinstance(last_check, str):
                        last_check = datetime.fromisoformat(last_check)
                    time_ago = datetime.now() - last_check
                    st.caption(f"Last check: {time_ago.seconds}s ago")
                else:
                    st.caption("Never checked")
            
            with col3:
                if st.button("🔄 Refresh", help="Check connection status"):
                    self.check_all_services()
                    st.rerun()
            
            # Detailed status if requested
            if detailed and self.services:
                st.markdown("---")
                st.subheader("📊 Service Details")
                
                for service_name, service_config in self.services.items():
                    health = service_config['health']
                    
                    with st.expander(f"{service_name} ({service_config['type'].value})"):
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            # Status indicator
                            if health.status == ConnectionStatus.CONNECTED:
                                st.success("✅ Connected")
                            elif health.status == ConnectionStatus.DISCONNECTED:
                                st.error("❌ Disconnected")
                            elif health.status == ConnectionStatus.ERROR:
                                st.warning("⚠️ Error")
                            else:
                                st.info("❓ Unknown")
                            
                            # Response time
                            if health.response_time:
                                st.metric("Response Time", f"{health.response_time*1000:.0f}ms")
                        
                        with col2:
                            # Last check
                            st.write(f"**Last Check:** {health.last_check.strftime('%H:%M:%S')}")
                            
                            # Consecutive failures
                            if health.consecutive_failures > 0:
                                st.write(f"**Failures:** {health.consecutive_failures}")
                            
                            # Error message
                            if health.error_message:
                                st.error(f"**Error:** {health.error_message}")
        
        except Exception as e:
            logger.error(f"Error rendering connection status: {e}")
            st.error("Error displaying connection status")
    
    def render_connection_indicator(self) -> None:
        """Render a compact connection indicator"""
        try:
            overall_status = self.get_overall_status()
            
            # Create indicator based on status
            if overall_status == ConnectionStatus.CONNECTED:
                st.success("🟢 Online")
            elif overall_status == ConnectionStatus.DISCONNECTED:
                st.error("🔴 Offline")
            elif overall_status == ConnectionStatus.ERROR:
                st.warning("🟡 Issues")
            else:
                st.info("🔵 Checking...")
        
        except Exception as e:
            logger.error(f"Error rendering connection indicator: {e}")
            st.warning("🟡 Status Unknown")
    
    def enable_offline_mode(self) -> None:
        """Enable offline mode with cached data"""
        try:
            if hasattr(st.session_state, 'offline_mode'):
                st.session_state.offline_mode = True
            
            # Show offline notification
            st.warning("📴 Offline Mode Enabled - Using cached data where available")
            
            logger.info("Offline mode enabled")
            
        except Exception as e:
            logger.error(f"Error enabling offline mode: {e}")
    
    def disable_offline_mode(self) -> None:
        """Disable offline mode"""
        try:
            if hasattr(st.session_state, 'offline_mode'):
                st.session_state.offline_mode = False
            
            # Show online notification
            st.success("🌐 Online Mode Restored")
            
            logger.info("Offline mode disabled")
            
        except Exception as e:
            logger.error(f"Error disabling offline mode: {e}")
    
    def is_offline_mode(self) -> bool:
        """Check if currently in offline mode"""
        return st.session_state.get('offline_mode', False)
    
    def render_offline_banner(self) -> None:
        """Render offline mode banner"""
        try:
            if self.is_offline_mode():
                st.warning("📴 **Offline Mode** - Some features may be limited. Data shown may be cached.")
                
                col1, col2 = st.columns([3, 1])
                
                with col2:
                    if st.button("🔄 Try Reconnect"):
                        # Try to reconnect
                        health_results = self.check_all_services()
                        
                        # Check if any service is now connected
                        if any(health.status == ConnectionStatus.CONNECTED for health in health_results.values()):
                            self.disable_offline_mode()
                            st.rerun()
                        else:
                            st.error("Still unable to connect to services")
        
        except Exception as e:
            logger.error(f"Error rendering offline banner: {e}")
    
    def get_connection_history(self, hours: int = 24) -> List[ConnectionEvent]:
        """
        Get connection history for the specified time period
        
        Args:
            hours: Number of hours to look back
            
        Returns:
            List of connection events
        """
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            return [event for event in self.connection_events 
                   if event.timestamp >= cutoff_time]
        
        except Exception as e:
            logger.error(f"Error getting connection history: {e}")
            return []
    
    def render_connection_history(self, hours: int = 24) -> None:
        """
        Render connection history
        
        Args:
            hours: Number of hours to show
        """
        try:
            st.subheader(f"📈 Connection History ({hours}h)")
            
            history = self.get_connection_history(hours)
            
            if not history:
                st.info("No connection events recorded")
                return
            
            # Group events by service
            service_events = {}
            for event in history:
                if event.service_name not in service_events:
                    service_events[event.service_name] = []
                service_events[event.service_name].append(event)
            
            # Display events for each service
            for service_name, events in service_events.items():
                with st.expander(f"{service_name} ({len(events)} events)"):
                    for event in reversed(events[-10:]):  # Show last 10 events
                        col1, col2, col3 = st.columns([2, 2, 4])
                        
                        with col1:
                            st.write(event.timestamp.strftime("%H:%M:%S"))
                        
                        with col2:
                            if event.event_type == "connected":
                                st.success("Connected")
                            elif event.event_type == "disconnected":
                                st.error("Disconnected")
                            else:
                                st.warning("Error")
                        
                        with col3:
                            st.write(event.details)
        
        except Exception as e:
            logger.error(f"Error rendering connection history: {e}")
            st.error("Error displaying connection history")
    
    def auto_check_connections(self) -> None:
        """Automatically check connections and handle failures"""
        try:
            health_results = self.check_all_services()
            
            # Check for failures
            failed_services = [name for name, health in health_results.items() 
                             if health.status != ConnectionStatus.CONNECTED]
            
            if failed_services:
                # Check if we should enable offline mode
                all_failed = len(failed_services) == len(self.services)
                
                if all_failed and not self.is_offline_mode():
                    # All services failed - enable offline mode
                    self.enable_offline_mode()
                
                # Show alerts for failed services
                for service_name in failed_services:
                    health = health_results[service_name]
                    
                    # Only show alert if consecutive failures > 2
                    if health.consecutive_failures > 2:
                        alert_key = f"{service_name}_failure"
                        
                        if alert_key not in st.session_state.connection_alerts:
                            st.error(f"⚠️ Service '{service_name}' is experiencing issues: {health.error_message}")
                            st.session_state.connection_alerts.append(alert_key)
            
            else:
                # All services are healthy
                if self.is_offline_mode():
                    self.disable_offline_mode()
                
                # Clear alerts
                st.session_state.connection_alerts = []
        
        except Exception as e:
            logger.error(f"Error in auto connection check: {e}")

# Utility functions

def setup_default_monitoring(api_base_url: str) -> ConnectionMonitor:
    """
    Set up default connection monitoring for ARGO dashboard
    
    Args:
        api_base_url: Base URL for the API
        
    Returns:
        Configured ConnectionMonitor instance
    """
    try:
        monitor = ConnectionMonitor()
        
        # Register main API service
        monitor.register_service(
            service_name="ARGO API",
            service_type=ServiceType.API,
            health_check_url=f"{api_base_url}/health",
            timeout=10
        )
        
        # Register database service (if health endpoint exists)
        monitor.register_service(
            service_name="Database",
            service_type=ServiceType.DATABASE,
            health_check_url=f"{api_base_url}/health/database",
            timeout=15
        )
        
        # Register ChromaDB service (if health endpoint exists)
        monitor.register_service(
            service_name="ChromaDB",
            service_type=ServiceType.CHROMADB,
            health_check_url=f"{api_base_url}/health/chromadb",
            timeout=10
        )
        
        return monitor
        
    except Exception as e:
        logger.error(f"Error setting up default monitoring: {e}")
        return ConnectionMonitor()

def get_connection_monitor() -> ConnectionMonitor:
    """Get or create connection monitor instance"""
    try:
        if hasattr(st.session_state, '__contains__') and 'connection_monitor' not in st.session_state:
            st.session_state.connection_monitor = ConnectionMonitor()
        
        if hasattr(st.session_state, 'connection_monitor'):
            return st.session_state.connection_monitor
        else:
            return ConnectionMonitor()
    except (AttributeError, TypeError):
        # Session state not available (e.g., in tests)
        return ConnectionMonitor()