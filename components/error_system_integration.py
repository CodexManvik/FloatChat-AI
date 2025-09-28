"""
Error System Integration for ARGO Float Dashboard

This module integrates all error handling components and provides
a unified interface for error management across the dashboard.
"""

import streamlit as st
import logging
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime
import pandas as pd

from .error_handler import ErrorHandler, ErrorCategory, ErrorSeverity, safe_api_call, safe_data_operation
from .user_feedback import UserFeedbackSystem, NotificationType, FeedbackType
from .connection_monitor import ConnectionMonitor, setup_default_monitoring

logger = logging.getLogger(__name__)

class IntegratedErrorSystem:
    """Integrated error handling system for the ARGO Float Dashboard"""
    
    def __init__(self, api_base_url: str = "http://localhost:8000"):
        """
        Initialize the integrated error system
        
        Args:
            api_base_url: Base URL for the API
        """
        self.api_base_url = api_base_url
        
        # Initialize components
        self.error_handler = ErrorHandler()
        self.feedback_system = UserFeedbackSystem()
        self.connection_monitor = setup_default_monitoring(api_base_url)
        
        # Initialize session state
        self._initialize_session_state()
    
    def _initialize_session_state(self):
        """Initialize session state for error system"""
        try:
            if hasattr(st.session_state, '__contains__'):
                if 'integrated_error_system' not in st.session_state:
                    st.session_state.integrated_error_system = True
                    st.session_state.error_system_active = True
                    st.session_state.auto_monitoring = True
        except (AttributeError, TypeError):
            # Session state not available (e.g., in tests)
            pass
    
    def handle_dashboard_error(self, 
                              error: Exception,
                              context: str = "",
                              component: str = "dashboard",
                              show_feedback: bool = True,
                              fallback_data: Any = None) -> Any:
        """
        Handle errors that occur in dashboard components
        
        Args:
            error: The exception that occurred
            context: Context where the error occurred
            component: Dashboard component name
            show_feedback: Whether to show user feedback
            fallback_data: Fallback data to return
            
        Returns:
            Fallback data or None
        """
        try:
            # Determine error category based on component
            category = self._get_error_category(component, error)
            
            # Handle the error
            result = self.error_handler.handle_error(
                error=error,
                category=category,
                context=f"{component}: {context}",
                show_to_user=show_feedback,
                fallback_action=lambda: fallback_data if fallback_data is not None else None
            )
            
            # Show user feedback if requested
            if show_feedback:
                self._show_error_feedback(error, category, component)
            
            return result
            
        except Exception as e:
            logger.critical(f"Error in error handling system: {e}")
            if show_feedback:
                st.error("A critical error occurred. Please refresh the page.")
            return fallback_data
    
    def _get_error_category(self, component: str, error: Exception) -> ErrorCategory:
        """Determine error category based on component and error type"""
        
        # Component-based categorization
        if component in ['api_client', 'data_fetcher']:
            return ErrorCategory.API_CONNECTION
        elif component in ['map_visualization', 'profile_visualizer', 'statistics_manager']:
            return ErrorCategory.VISUALIZATION
        elif component in ['data_manager', 'data_transformer']:
            return ErrorCategory.DATA_PROCESSING
        elif component in ['chat_interface']:
            return ErrorCategory.USER_INPUT
        
        # Error type-based categorization
        if isinstance(error, (ConnectionError, TimeoutError)):
            return ErrorCategory.NETWORK
        elif isinstance(error, (ValueError, TypeError)):
            return ErrorCategory.DATA_PROCESSING
        else:
            return ErrorCategory.SYSTEM
    
    def _show_error_feedback(self, error: Exception, category: ErrorCategory, component: str):
        """Show appropriate user feedback for the error"""
        try:
            error_message = f"Error in {component}: {str(error)}"
            
            if category == ErrorCategory.API_CONNECTION:
                self.feedback_system.show_notification(
                    "Connection issue detected. Switching to offline mode if needed.",
                    NotificationType.WARNING
                )
            elif category == ErrorCategory.DATA_PROCESSING:
                self.feedback_system.show_notification(
                    "Data processing error. Please check your inputs and try again.",
                    NotificationType.ERROR
                )
            elif category == ErrorCategory.VISUALIZATION:
                self.feedback_system.show_notification(
                    "Visualization error. Trying alternative display method.",
                    NotificationType.WARNING
                )
            else:
                self.feedback_system.show_notification(
                    "An unexpected error occurred. Please try again.",
                    NotificationType.ERROR
                )
                
        except Exception as e:
            logger.error(f"Error showing feedback: {e}")
    
    def monitor_system_health(self, api_client=None) -> Dict[str, Any]:
        """
        Monitor overall system health
        
        Args:
            api_client: API client instance for health checks
            
        Returns:
            System health status
        """
        try:
            health_status = {
                'overall_status': 'healthy',
                'components': {},
                'recommendations': []
            }
            
            # Check API connection
            if api_client:
                connection_status = self.error_handler.monitor_connection_status(api_client)
                health_status['components']['api'] = connection_status
                
                if connection_status['api'] != 'connected':
                    health_status['overall_status'] = 'degraded'
                    health_status['recommendations'].append("Check API connection")
            
            # Check connection monitor services
            service_health = self.connection_monitor.check_all_services()
            health_status['components']['services'] = service_health
            
            # Check for recent errors
            recent_errors = [e for e in self.error_handler.error_history 
                           if (datetime.now() - e.timestamp).total_seconds() < 300]  # Last 5 minutes
            
            if len(recent_errors) > 5:
                health_status['overall_status'] = 'degraded'
                health_status['recommendations'].append("High error rate detected")
            
            health_status['components']['recent_errors'] = len(recent_errors)
            
            return health_status
            
        except Exception as e:
            logger.error(f"Error monitoring system health: {e}")
            return {
                'overall_status': 'error',
                'components': {},
                'recommendations': ['System health monitoring failed']
            }
    
    def render_system_status(self, api_client=None, detailed: bool = False):
        """
        Render system status in Streamlit
        
        Args:
            api_client: API client for health checks
            detailed: Whether to show detailed status
        """
        try:
            st.subheader("🔧 System Status")
            
            # Get system health
            health = self.monitor_system_health(api_client)
            
            # Overall status
            col1, col2, col3 = st.columns([2, 2, 2])
            
            with col1:
                if health['overall_status'] == 'healthy':
                    st.success("✅ System Healthy")
                elif health['overall_status'] == 'degraded':
                    st.warning("⚠️ System Degraded")
                else:
                    st.error("❌ System Error")
            
            with col2:
                recent_errors = health['components'].get('recent_errors', 0)
                st.metric("Recent Errors", recent_errors)
            
            with col3:
                if st.button("🔄 Refresh Status"):
                    st.rerun()
            
            # Connection status
            self.connection_monitor.render_connection_indicator()
            
            # Recommendations
            if health['recommendations']:
                st.subheader("💡 Recommendations")
                for rec in health['recommendations']:
                    st.info(rec)
            
            # Detailed status
            if detailed:
                st.markdown("---")
                
                # Connection details
                self.connection_monitor.render_connection_status(detailed=True)
                
                # Error summary
                self.error_handler.render_error_summary()
                
                # Feedback summary
                self.feedback_system.render_feedback_summary()
        
        except Exception as e:
            logger.error(f"Error rendering system status: {e}")
            st.error("Error displaying system status")
    
    def safe_execute_with_feedback(self, 
                                  operation: Callable,
                                  operation_name: str,
                                  component: str = "dashboard",
                                  show_progress: bool = False,
                                  fallback_result: Any = None,
                                  *args, **kwargs) -> Any:
        """
        Safely execute an operation with comprehensive error handling and user feedback
        
        Args:
            operation: Function to execute
            operation_name: Name of the operation for user display
            component: Component name for error categorization
            show_progress: Whether to show progress indicator
            fallback_result: Result to return on error
            *args, **kwargs: Arguments for the operation
            
        Returns:
            Operation result or fallback result
        """
        try:
            if show_progress:
                with self.feedback_system.create_loading_context(f"Executing {operation_name}..."):
                    return operation(*args, **kwargs)
            else:
                return operation(*args, **kwargs)
                
        except Exception as e:
            return self.handle_dashboard_error(
                error=e,
                context=operation_name,
                component=component,
                show_feedback=True,
                fallback_data=fallback_result
            )
    
    def create_error_boundary(self, component_name: str):
        """
        Create an error boundary context manager for dashboard components
        
        Args:
            component_name: Name of the component
            
        Returns:
            Context manager for error handling
        """
        return ErrorBoundary(self, component_name)
    
    def collect_user_error_feedback(self, error_context: str) -> Optional[str]:
        """
        Collect feedback from user about an error
        
        Args:
            error_context: Context of the error
            
        Returns:
            User feedback or None
        """
        try:
            feedback_id = f"error_feedback_{hash(error_context)}"
            
            return self.feedback_system.collect_user_feedback(
                feedback_id=feedback_id,
                question=f"We encountered an issue with {error_context}. Can you help us understand what happened?",
                feedback_type=FeedbackType.TEXT,
                context={'error_context': error_context, 'timestamp': datetime.now().isoformat()}
            )
            
        except Exception as e:
            logger.error(f"Error collecting user feedback: {e}")
            return None
    
    def enable_auto_monitoring(self, api_client=None):
        """Enable automatic system monitoring"""
        try:
            if hasattr(st.session_state, 'auto_monitoring'):
                st.session_state.auto_monitoring = True
            
            # Perform auto checks
            if api_client:
                self.connection_monitor.auto_check_connections()
            
        except Exception as e:
            logger.error(f"Error enabling auto monitoring: {e}")
    
    def disable_auto_monitoring(self):
        """Disable automatic system monitoring"""
        try:
            if hasattr(st.session_state, 'auto_monitoring'):
                st.session_state.auto_monitoring = False
                
        except Exception as e:
            logger.error(f"Error disabling auto monitoring: {e}")

class ErrorBoundary:
    """Context manager for error boundaries in dashboard components"""
    
    def __init__(self, error_system: IntegratedErrorSystem, component_name: str):
        self.error_system = error_system
        self.component_name = component_name
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            # Handle the error
            self.error_system.handle_dashboard_error(
                error=exc_val,
                context="Component execution",
                component=self.component_name,
                show_feedback=True
            )
            
            # Suppress the exception (return True)
            return True
        
        return False

# Utility functions for easy integration

def get_integrated_error_system(api_base_url: str = "http://localhost:8000") -> IntegratedErrorSystem:
    """Get or create integrated error system instance"""
    try:
        if hasattr(st.session_state, '__contains__') and 'integrated_error_system_instance' not in st.session_state:
            st.session_state.integrated_error_system_instance = IntegratedErrorSystem(api_base_url)
        
        if hasattr(st.session_state, 'integrated_error_system_instance'):
            return st.session_state.integrated_error_system_instance
        else:
            return IntegratedErrorSystem(api_base_url)
    except (AttributeError, TypeError):
        # Session state not available (e.g., in tests)
        return IntegratedErrorSystem(api_base_url)

def safe_dashboard_operation(operation: Callable, 
                           operation_name: str,
                           component: str = "dashboard",
                           fallback_result: Any = None,
                           *args, **kwargs) -> Any:
    """
    Safely execute a dashboard operation with integrated error handling
    
    Args:
        operation: Function to execute
        operation_name: Name for user display
        component: Component name
        fallback_result: Fallback result on error
        *args, **kwargs: Operation arguments
        
    Returns:
        Operation result or fallback
    """
    error_system = get_integrated_error_system()
    return error_system.safe_execute_with_feedback(
        operation=operation,
        operation_name=operation_name,
        component=component,
        fallback_result=fallback_result,
        *args, **kwargs
    )

def dashboard_error_boundary(component_name: str):
    """
    Create error boundary decorator for dashboard components
    
    Args:
        component_name: Name of the component
        
    Returns:
        Decorator function
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            error_system = get_integrated_error_system()
            with error_system.create_error_boundary(component_name):
                return func(*args, **kwargs)
        return wrapper
    return decorator