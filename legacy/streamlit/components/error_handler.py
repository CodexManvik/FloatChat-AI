"""
Error Handler Component for ARGO Float Dashboard

This component provides comprehensive error handling, user feedback systems,
and connection monitoring for the Streamlit dashboard.
"""

import streamlit as st
import pandas as pd
import logging
import traceback
from typing import Dict, Any, Optional, Callable, List, Union
from datetime import datetime, timedelta
import time
import json
from enum import Enum
from dataclasses import dataclass
import requests
from functools import wraps

logger = logging.getLogger(__name__)

class ErrorSeverity(Enum):
    """Error severity levels for user feedback"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class ErrorCategory(Enum):
    """Categories of errors for better handling"""
    API_CONNECTION = "api_connection"
    DATA_PROCESSING = "data_processing"
    VISUALIZATION = "visualization"
    USER_INPUT = "user_input"
    SYSTEM = "system"
    NETWORK = "network"

@dataclass
class ErrorInfo:
    """Structure for error information"""
    category: ErrorCategory
    severity: ErrorSeverity
    message: str
    technical_details: str
    suggested_actions: List[str]
    timestamp: datetime
    user_friendly: bool = True

class ErrorHandler:
    """Comprehensive error handling and user feedback system"""
    
    def __init__(self):
        """Initialize the error handler"""
        self.error_history = []
        self.connection_status = {
            'api': 'unknown',
            'last_check': None,
            'consecutive_failures': 0
        }
        self.cached_data = {}
        self.cache_timestamps = {}
        
        # Initialize session state for error tracking
        try:
            if hasattr(st.session_state, '__contains__') and 'error_handler_initialized' not in st.session_state:
                st.session_state.error_handler_initialized = True
                st.session_state.error_count = 0
                st.session_state.last_error_time = None
                st.session_state.connection_alerts_shown = set()
        except (AttributeError, TypeError):
            # Session state not available (e.g., in tests)
            pass
    
    def handle_error(self, 
                    error: Exception, 
                    category: ErrorCategory,
                    context: str = "",
                    show_to_user: bool = True,
                    fallback_action: Optional[Callable] = None) -> Optional[Any]:
        """
        Comprehensive error handling with user feedback
        
        Args:
            error: The exception that occurred
            category: Category of the error
            context: Additional context about where the error occurred
            show_to_user: Whether to show error message to user
            fallback_action: Optional fallback function to execute
            
        Returns:
            Result of fallback action if provided, None otherwise
        """
        try:
            # Determine error severity
            severity = self._determine_severity(error, category)
            
            # Create error info
            error_info = ErrorInfo(
                category=category,
                severity=severity,
                message=self._create_user_message(error, category, context),
                technical_details=str(error),
                suggested_actions=self._get_suggested_actions(error, category),
                timestamp=datetime.now()
            )
            
            # Log error
            self._log_error(error_info, context)
            
            # Store in error history
            self.error_history.append(error_info)
            
            # Update session state safely
            if hasattr(st.session_state, 'error_count'):
                st.session_state.error_count += 1
            if hasattr(st.session_state, 'last_error_time'):
                st.session_state.last_error_time = datetime.now()
            
            # Show to user if requested
            if show_to_user:
                self._display_error_to_user(error_info)
            
            # Execute fallback action if provided
            if fallback_action:
                try:
                    return fallback_action()
                except Exception as fallback_error:
                    logger.error(f"Fallback action failed: {fallback_error}")
            
            return None
            
        except Exception as handler_error:
            # Error in error handler - log but don't recurse
            logger.critical(f"Error handler failed: {handler_error}")
            if show_to_user:
                st.error("An unexpected error occurred. Please refresh the page.")
            return None
    
    def _determine_severity(self, error: Exception, category: ErrorCategory) -> ErrorSeverity:
        """Determine the severity of an error"""
        
        # Critical errors
        if isinstance(error, (SystemError, MemoryError)):
            return ErrorSeverity.CRITICAL
        
        # Category-based severity
        if category == ErrorCategory.API_CONNECTION:
            if "timeout" in str(error).lower():
                return ErrorSeverity.WARNING
            return ErrorSeverity.ERROR
        
        elif category == ErrorCategory.DATA_PROCESSING:
            if isinstance(error, (ValueError, TypeError)):
                return ErrorSeverity.WARNING
            return ErrorSeverity.ERROR
        
        elif category == ErrorCategory.VISUALIZATION:
            return ErrorSeverity.WARNING
        
        elif category == ErrorCategory.USER_INPUT:
            return ErrorSeverity.INFO
        
        elif category == ErrorCategory.NETWORK:
            return ErrorSeverity.WARNING
        
        else:
            return ErrorSeverity.ERROR
    
    def _create_user_message(self, error: Exception, category: ErrorCategory, context: str) -> str:
        """Create user-friendly error message"""
        
        base_messages = {
            ErrorCategory.API_CONNECTION: "Unable to connect to the data server",
            ErrorCategory.DATA_PROCESSING: "Error processing oceanographic data",
            ErrorCategory.VISUALIZATION: "Error creating visualization",
            ErrorCategory.USER_INPUT: "Invalid input provided",
            ErrorCategory.NETWORK: "Network connectivity issue",
            ErrorCategory.SYSTEM: "System error occurred"
        }
        
        base_message = base_messages.get(category, "An error occurred")
        
        # Add context if provided
        if context:
            base_message += f" while {context}"
        
        # Add specific error details for certain types
        error_str = str(error).lower()
        if "timeout" in error_str:
            base_message += ". The operation timed out."
        elif "connection refused" in error_str:
            base_message += ". The server is not responding."
        elif "not found" in error_str:
            base_message += ". The requested resource was not found."
        elif "unauthorized" in error_str:
            base_message += ". Authentication failed."
        
        return base_message
    
    def _get_suggested_actions(self, error: Exception, category: ErrorCategory) -> List[str]:
        """Get suggested actions for the user"""
        
        actions = []
        error_str = str(error).lower()
        
        if category == ErrorCategory.API_CONNECTION:
            actions.extend([
                "Check your internet connection",
                "Verify the backend server is running",
                "Try refreshing the page",
                "Contact system administrator if problem persists"
            ])
            
            if "timeout" in error_str:
                actions.insert(0, "Wait a moment and try again")
        
        elif category == ErrorCategory.DATA_PROCESSING:
            actions.extend([
                "Check if the data format is correct",
                "Try with a smaller dataset",
                "Verify filter settings are valid",
                "Report this issue if it continues"
            ])
        
        elif category == ErrorCategory.VISUALIZATION:
            actions.extend([
                "Try refreshing the visualization",
                "Check if data is available",
                "Try with different parameters",
                "Use alternative visualization options"
            ])
        
        elif category == ErrorCategory.USER_INPUT:
            actions.extend([
                "Check input format and values",
                "Ensure all required fields are filled",
                "Verify numeric inputs are within valid ranges"
            ])
        
        elif category == ErrorCategory.NETWORK:
            actions.extend([
                "Check internet connectivity",
                "Try again in a few moments",
                "Contact IT support if problem persists"
            ])
        
        else:
            actions.extend([
                "Try refreshing the page",
                "Clear browser cache if problem persists",
                "Contact support for assistance"
            ])
        
        return actions
    
    def _log_error(self, error_info: ErrorInfo, context: str):
        """Log error with appropriate level"""
        
        log_message = f"{error_info.category.value}: {error_info.message}"
        if context:
            log_message += f" (Context: {context})"
        log_message += f" - {error_info.technical_details}"
        
        if error_info.severity == ErrorSeverity.CRITICAL:
            logger.critical(log_message)
        elif error_info.severity == ErrorSeverity.ERROR:
            logger.error(log_message)
        elif error_info.severity == ErrorSeverity.WARNING:
            logger.warning(log_message)
        else:
            logger.info(log_message)
    
    def _display_error_to_user(self, error_info: ErrorInfo):
        """Display error message to user in Streamlit"""
        
        # Choose appropriate Streamlit display method
        if error_info.severity == ErrorSeverity.CRITICAL:
            st.error(f"🚨 Critical Error: {error_info.message}")
        elif error_info.severity == ErrorSeverity.ERROR:
            st.error(f"❌ Error: {error_info.message}")
        elif error_info.severity == ErrorSeverity.WARNING:
            st.warning(f"⚠️ Warning: {error_info.message}")
        else:
            st.info(f"ℹ️ {error_info.message}")
        
        # Show suggested actions in an expander
        if error_info.suggested_actions:
            with st.expander("💡 Suggested Actions"):
                for i, action in enumerate(error_info.suggested_actions, 1):
                    st.write(f"{i}. {action}")
    
    def monitor_connection_status(self, api_client) -> Dict[str, Any]:
        """
        Monitor API connection status
        
        Args:
            api_client: The API client to monitor
            
        Returns:
            Dictionary with connection status information
        """
        try:
            # Check if we need to test connection
            now = datetime.now()
            last_check = self.connection_status.get('last_check')
            
            # Test connection every 30 seconds or if never tested
            if not last_check or (now - last_check).seconds > 30:
                
                # Test connection
                try:
                    health_response = api_client.health_check()
                    
                    if health_response and health_response.get('status') == 'healthy':
                        self.connection_status.update({
                            'api': 'connected',
                            'last_check': now,
                            'consecutive_failures': 0
                        })
                    else:
                        self._handle_connection_failure()
                        
                except Exception as e:
                    self._handle_connection_failure()
                    logger.warning(f"Connection check failed: {e}")
            
            return self.connection_status
            
        except Exception as e:
            logger.error(f"Error monitoring connection: {e}")
            return {'api': 'error', 'last_check': now, 'consecutive_failures': 999}
    
    def _handle_connection_failure(self):
        """Handle connection failure"""
        now = datetime.now()
        self.connection_status.update({
            'api': 'disconnected',
            'last_check': now,
            'consecutive_failures': self.connection_status.get('consecutive_failures', 0) + 1
        })
    
    def render_connection_status(self, api_client) -> None:
        """Render connection status indicator in Streamlit"""
        
        status_info = self.monitor_connection_status(api_client)
        
        # Create status indicator
        col1, col2 = st.columns([3, 1])
        
        with col1:
            if status_info['api'] == 'connected':
                st.success("🟢 Backend Connected")
            elif status_info['api'] == 'disconnected':
                consecutive_failures = status_info.get('consecutive_failures', 0)
                if consecutive_failures > 5:
                    st.error("🔴 Backend Disconnected (Multiple Failures)")
                else:
                    st.warning("🟡 Backend Connection Issues")
            else:
                st.info("🔵 Checking Connection...")
        
        with col2:
            if st.button("🔄 Test", help="Test connection"):
                self.connection_status['last_check'] = None  # Force recheck
                st.rerun()
    
    def create_loading_context(self, message: str = "Loading...", show_progress: bool = False):
        """
        Create a loading context manager for long operations
        
        Args:
            message: Loading message to display
            show_progress: Whether to show progress bar
            
        Returns:
            Context manager for loading operations
        """
        return LoadingContext(message, show_progress)
    
    def cache_data(self, key: str, data: Any, ttl_minutes: int = 60):
        """
        Cache data for offline access
        
        Args:
            key: Cache key
            data: Data to cache
            ttl_minutes: Time to live in minutes
        """
        try:
            self.cached_data[key] = data
            self.cache_timestamps[key] = datetime.now()
            
            # Clean old cache entries
            self._clean_cache(ttl_minutes)
            
        except Exception as e:
            logger.warning(f"Failed to cache data: {e}")
    
    def get_cached_data(self, key: str, ttl_minutes: int = 60) -> Optional[Any]:
        """
        Retrieve cached data
        
        Args:
            key: Cache key
            ttl_minutes: Time to live in minutes
            
        Returns:
            Cached data if available and not expired, None otherwise
        """
        try:
            if key not in self.cached_data:
                return None
            
            # Check if cache is expired
            cache_time = self.cache_timestamps.get(key)
            if cache_time and (datetime.now() - cache_time).total_seconds() > ttl_minutes * 60:
                # Remove expired cache
                del self.cached_data[key]
                del self.cache_timestamps[key]
                return None
            
            return self.cached_data[key]
            
        except Exception as e:
            logger.warning(f"Failed to retrieve cached data: {e}")
            return None
    
    def _clean_cache(self, ttl_minutes: int):
        """Clean expired cache entries"""
        try:
            now = datetime.now()
            expired_keys = []
            
            for key, timestamp in self.cache_timestamps.items():
                if (now - timestamp).total_seconds() > ttl_minutes * 60:
                    expired_keys.append(key)
            
            for key in expired_keys:
                if key in self.cached_data:
                    del self.cached_data[key]
                if key in self.cache_timestamps:
                    del self.cache_timestamps[key]
                    
        except Exception as e:
            logger.warning(f"Failed to clean cache: {e}")
    
    def render_error_summary(self):
        """Render error summary for debugging"""
        
        if not self.error_history:
            st.success("✅ No errors recorded in this session")
            return
        
        st.subheader("🐛 Error Summary")
        
        # Error statistics
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Errors", len(self.error_history))
        
        with col2:
            recent_errors = [e for e in self.error_history 
                           if (datetime.now() - e.timestamp).total_seconds() < 300]  # Last 5 minutes
            st.metric("Recent Errors", len(recent_errors))
        
        with col3:
            critical_errors = [e for e in self.error_history 
                             if e.severity == ErrorSeverity.CRITICAL]
            st.metric("Critical Errors", len(critical_errors))
        
        # Recent errors list
        if st.checkbox("Show Error Details"):
            for error in reversed(self.error_history[-10:]):  # Show last 10 errors
                with st.expander(f"{error.severity.value.title()}: {error.message[:50]}..."):
                    st.write(f"**Time:** {error.timestamp.strftime('%H:%M:%S')}")
                    st.write(f"**Category:** {error.category.value}")
                    st.write(f"**Message:** {error.message}")
                    st.write(f"**Technical Details:** {error.technical_details}")
                    
                    if error.suggested_actions:
                        st.write("**Suggested Actions:**")
                        for action in error.suggested_actions:
                            st.write(f"• {action}")

class LoadingContext:
    """Context manager for loading operations with progress indication"""
    
    def __init__(self, message: str = "Loading...", show_progress: bool = False):
        self.message = message
        self.show_progress = show_progress
        self.progress_bar = None
        self.status_text = None
        self.container = None
    
    def __enter__(self):
        """Enter loading context"""
        self.container = st.container()
        
        with self.container:
            self.status_text = st.empty()
            self.status_text.info(f"⏳ {self.message}")
            
            if self.show_progress:
                self.progress_bar = st.progress(0)
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit loading context"""
        if self.container:
            self.container.empty()
    
    def update_progress(self, progress: float, message: str = None):
        """Update progress bar and message"""
        if self.progress_bar:
            self.progress_bar.progress(min(max(progress, 0.0), 1.0))
        
        if message and self.status_text:
            self.status_text.info(f"⏳ {message}")
    
    def update_message(self, message: str):
        """Update status message"""
        if self.status_text:
            self.status_text.info(f"⏳ {message}")

def error_handler_decorator(category: ErrorCategory, 
                          context: str = "",
                          show_to_user: bool = True,
                          fallback_value: Any = None):
    """
    Decorator for automatic error handling
    
    Args:
        category: Error category
        context: Context description
        show_to_user: Whether to show error to user
        fallback_value: Value to return on error
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Get error handler from session state or create new one
                try:
                    if hasattr(st.session_state, 'error_handler') and st.session_state.error_handler:
                        error_handler = st.session_state.error_handler
                    else:
                        error_handler = ErrorHandler()
                except:
                    error_handler = ErrorHandler()
                
                # Handle the error
                result = error_handler.handle_error(
                    error=e,
                    category=category,
                    context=context or func.__name__,
                    show_to_user=show_to_user,
                    fallback_action=lambda: fallback_value
                )
                
                return result if result is not None else fallback_value
        
        return wrapper
    return decorator

# Utility functions for common error handling patterns

def safe_api_call(api_func: Callable, *args, **kwargs) -> Optional[Any]:
    """
    Safely execute an API call with error handling
    
    Args:
        api_func: API function to call
        *args, **kwargs: Arguments for the API function
        
    Returns:
        API response or None if error occurred
    """
    try:
        return api_func(*args, **kwargs)
    except requests.exceptions.Timeout:
        st.warning("⏱️ Request timed out. Please try again.")
        return None
    except requests.exceptions.ConnectionError:
        st.error("🔌 Connection error. Please check your internet connection.")
        return None
    except requests.exceptions.HTTPError as e:
        st.error(f"🌐 HTTP error: {e}")
        return None
    except Exception as e:
        st.error(f"❌ Unexpected error: {str(e)}")
        return None

def safe_data_operation(operation: Callable, data: Any, operation_name: str = "data operation") -> Optional[Any]:
    """
    Safely execute a data operation with error handling
    
    Args:
        operation: Operation function to execute
        data: Data to operate on
        operation_name: Name of the operation for error messages
        
    Returns:
        Operation result or None if error occurred
    """
    try:
        if data is None or (hasattr(data, 'empty') and data.empty):
            st.warning(f"⚠️ No data available for {operation_name}")
            return None
        
        return operation(data)
        
    except ValueError as e:
        st.error(f"📊 Data format error in {operation_name}: {str(e)}")
        return None
    except TypeError as e:
        st.error(f"🔧 Type error in {operation_name}: {str(e)}")
        return None
    except Exception as e:
        st.error(f"❌ Error in {operation_name}: {str(e)}")
        return None