"""
User Feedback System for ARGO Float Dashboard

This component provides user feedback mechanisms including notifications,
progress indicators, status updates, and interactive feedback collection.
"""

import streamlit as st
import time
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

class NotificationType(Enum):
    """Types of notifications"""
    SUCCESS = "success"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"

class FeedbackType(Enum):
    """Types of user feedback"""
    RATING = "rating"
    TEXT = "text"
    CHOICE = "choice"
    BOOLEAN = "boolean"

@dataclass
class Notification:
    """Structure for notifications"""
    message: str
    type: NotificationType
    timestamp: datetime
    duration: Optional[float] = None
    dismissible: bool = True
    action_label: Optional[str] = None
    action_callback: Optional[Callable] = None

@dataclass
class UserFeedback:
    """Structure for user feedback"""
    feedback_id: str
    type: FeedbackType
    question: str
    response: Any
    timestamp: datetime
    context: Dict[str, Any]

class UserFeedbackSystem:
    """Comprehensive user feedback and notification system"""
    
    def __init__(self):
        """Initialize the feedback system"""
        self.notifications = []
        self.feedback_history = []
        
        # Initialize session state
        try:
            if hasattr(st.session_state, '__contains__') and 'feedback_system_initialized' not in st.session_state:
                st.session_state.feedback_system_initialized = True
                st.session_state.notifications = []
                st.session_state.feedback_responses = {}
                st.session_state.progress_operations = {}
        except (AttributeError, TypeError):
            # Session state not available (e.g., in tests)
            pass
    
    def show_notification(self, 
                         message: str, 
                         type: NotificationType = NotificationType.INFO,
                         duration: Optional[float] = None,
                         dismissible: bool = True,
                         action_label: Optional[str] = None,
                         action_callback: Optional[Callable] = None) -> None:
        """
        Show a notification to the user
        
        Args:
            message: Notification message
            type: Type of notification
            duration: Auto-dismiss duration in seconds
            dismissible: Whether user can dismiss
            action_label: Label for action button
            action_callback: Callback for action button
        """
        try:
            notification = Notification(
                message=message,
                type=type,
                timestamp=datetime.now(),
                duration=duration,
                dismissible=dismissible,
                action_label=action_label,
                action_callback=action_callback
            )
            
            # Add to session state notifications
            try:
                if hasattr(st.session_state, '__contains__') and 'notifications' not in st.session_state:
                    st.session_state.notifications = []
                
                if hasattr(st.session_state, 'notifications'):
                    st.session_state.notifications.append(notification)
            except (AttributeError, TypeError):
                # Session state not available (e.g., in tests)
                pass
            
            # Display immediately
            self._display_notification(notification)
            
        except Exception as e:
            logger.error(f"Error showing notification: {e}")
            # Fallback to simple Streamlit message
            if type == NotificationType.ERROR:
                st.error(message)
            elif type == NotificationType.WARNING:
                st.warning(message)
            elif type == NotificationType.SUCCESS:
                st.success(message)
            else:
                st.info(message)
    
    def _display_notification(self, notification: Notification) -> None:
        """Display a notification using Streamlit"""
        
        # Create notification container
        container = st.container()
        
        with container:
            # Choose appropriate Streamlit method
            if notification.type == NotificationType.SUCCESS:
                st.success(f"✅ {notification.message}")
            elif notification.type == NotificationType.WARNING:
                st.warning(f"⚠️ {notification.message}")
            elif notification.type == NotificationType.ERROR:
                st.error(f"❌ {notification.message}")
            else:
                st.info(f"ℹ️ {notification.message}")
            
            # Add action button if provided
            if notification.action_label and notification.action_callback:
                if st.button(notification.action_label, key=f"action_{id(notification)}"):
                    try:
                        notification.action_callback()
                    except Exception as e:
                        logger.error(f"Error executing notification action: {e}")
                        st.error("Action failed. Please try again.")
    
    def show_progress_operation(self, 
                              operation_id: str,
                              title: str,
                              steps: List[str],
                              operation_func: Callable,
                              *args, **kwargs) -> Any:
        """
        Execute an operation with progress indication
        
        Args:
            operation_id: Unique identifier for the operation
            title: Title for the progress display
            steps: List of step descriptions
            operation_func: Function to execute
            *args, **kwargs: Arguments for the operation function
            
        Returns:
            Result of the operation function
        """
        try:
            # Create progress container
            progress_container = st.container()
            
            with progress_container:
                st.subheader(f"⏳ {title}")
                
                # Create progress bar and status
                progress_bar = st.progress(0)
                status_text = st.empty()
                step_details = st.empty()
                
                # Store progress info in session state
                st.session_state.progress_operations[operation_id] = {
                    'progress_bar': progress_bar,
                    'status_text': status_text,
                    'step_details': step_details,
                    'total_steps': len(steps),
                    'current_step': 0
                }
                
                # Create progress callback
                def update_progress(step_index: int, message: str = ""):
                    try:
                        progress_info = st.session_state.progress_operations.get(operation_id)
                        if progress_info:
                            # Update progress bar
                            progress = (step_index + 1) / progress_info['total_steps']
                            progress_info['progress_bar'].progress(progress)
                            
                            # Update status
                            if step_index < len(steps):
                                step_message = steps[step_index]
                                progress_info['status_text'].info(f"Step {step_index + 1}/{len(steps)}: {step_message}")
                            
                            # Update details if provided
                            if message:
                                progress_info['step_details'].text(message)
                            
                            progress_info['current_step'] = step_index
                            
                    except Exception as e:
                        logger.error(f"Error updating progress: {e}")
                
                # Execute operation with progress callback
                try:
                    result = operation_func(update_progress, *args, **kwargs)
                    
                    # Show completion
                    progress_bar.progress(1.0)
                    status_text.success("✅ Operation completed successfully!")
                    
                    # Clean up after a short delay
                    time.sleep(1)
                    progress_container.empty()
                    
                    return result
                    
                except Exception as e:
                    # Show error
                    status_text.error(f"❌ Operation failed: {str(e)}")
                    raise e
                
                finally:
                    # Clean up progress info
                    if operation_id in st.session_state.progress_operations:
                        del st.session_state.progress_operations[operation_id]
        
        except Exception as e:
            logger.error(f"Error in progress operation: {e}")
            # Fallback to simple execution
            return operation_func(lambda x, msg="": None, *args, **kwargs)
    
    def collect_user_feedback(self, 
                            feedback_id: str,
                            question: str,
                            feedback_type: FeedbackType,
                            options: Optional[List[str]] = None,
                            context: Optional[Dict[str, Any]] = None) -> Optional[Any]:
        """
        Collect feedback from the user
        
        Args:
            feedback_id: Unique identifier for the feedback
            question: Question to ask the user
            feedback_type: Type of feedback to collect
            options: Options for choice-based feedback
            context: Additional context information
            
        Returns:
            User's response or None if not provided
        """
        try:
            # Check if feedback already collected
            try:
                if hasattr(st.session_state, 'feedback_responses') and feedback_id in st.session_state.feedback_responses:
                    return st.session_state.feedback_responses[feedback_id]
            except (AttributeError, TypeError):
                # Session state not available (e.g., in tests)
                pass
            
            st.subheader("💬 Your Feedback")
            st.write(question)
            
            response = None
            
            if feedback_type == FeedbackType.RATING:
                response = st.slider(
                    "Rating (1-5)",
                    min_value=1,
                    max_value=5,
                    value=3,
                    key=f"rating_{feedback_id}"
                )
            
            elif feedback_type == FeedbackType.TEXT:
                response = st.text_area(
                    "Your response:",
                    key=f"text_{feedback_id}",
                    height=100
                )
            
            elif feedback_type == FeedbackType.CHOICE:
                if options:
                    response = st.selectbox(
                        "Select an option:",
                        options,
                        key=f"choice_{feedback_id}"
                    )
                else:
                    st.error("No options provided for choice feedback")
                    return None
            
            elif feedback_type == FeedbackType.BOOLEAN:
                response = st.checkbox(
                    "Yes/No",
                    key=f"boolean_{feedback_id}"
                )
            
            # Submit button
            if st.button("Submit Feedback", key=f"submit_{feedback_id}"):
                if response is not None and response != "":
                    # Store feedback
                    feedback = UserFeedback(
                        feedback_id=feedback_id,
                        type=feedback_type,
                        question=question,
                        response=response,
                        timestamp=datetime.now(),
                        context=context or {}
                    )
                    
                    self.feedback_history.append(feedback)
                    
                    try:
                        if hasattr(st.session_state, 'feedback_responses'):
                            st.session_state.feedback_responses[feedback_id] = response
                    except (AttributeError, TypeError):
                        # Session state not available (e.g., in tests)
                        pass
                    
                    self.show_notification(
                        "Thank you for your feedback!",
                        NotificationType.SUCCESS
                    )
                    
                    return response
                else:
                    self.show_notification(
                        "Please provide a response before submitting.",
                        NotificationType.WARNING
                    )
            
            return None
            
        except Exception as e:
            logger.error(f"Error collecting feedback: {e}")
            st.error("Error collecting feedback. Please try again.")
            return None
    
    def show_status_indicator(self, 
                            status: str,
                            details: Optional[str] = None,
                            color: str = "blue") -> None:
        """
        Show a status indicator
        
        Args:
            status: Status message
            details: Additional details
            color: Color for the indicator
        """
        try:
            # Create status indicator with color
            color_map = {
                "green": "🟢",
                "yellow": "🟡", 
                "red": "🔴",
                "blue": "🔵",
                "orange": "🟠"
            }
            
            indicator = color_map.get(color, "🔵")
            
            col1, col2 = st.columns([1, 4])
            
            with col1:
                st.markdown(f"### {indicator}")
            
            with col2:
                st.markdown(f"**{status}**")
                if details:
                    st.caption(details)
        
        except Exception as e:
            logger.error(f"Error showing status indicator: {e}")
            st.info(f"{status} - {details}" if details else status)
    
    def create_confirmation_dialog(self, 
                                 message: str,
                                 confirm_label: str = "Confirm",
                                 cancel_label: str = "Cancel") -> Optional[bool]:
        """
        Create a confirmation dialog
        
        Args:
            message: Confirmation message
            confirm_label: Label for confirm button
            cancel_label: Label for cancel button
            
        Returns:
            True if confirmed, False if cancelled, None if no action
        """
        try:
            st.warning(f"⚠️ {message}")
            
            col1, col2, col3 = st.columns([1, 1, 2])
            
            with col1:
                if st.button(confirm_label, type="primary"):
                    return True
            
            with col2:
                if st.button(cancel_label):
                    return False
            
            return None
            
        except Exception as e:
            logger.error(f"Error creating confirmation dialog: {e}")
            return None
    
    def show_help_tooltip(self, 
                         content: str,
                         title: str = "Help") -> None:
        """
        Show a help tooltip
        
        Args:
            content: Help content
            title: Tooltip title
        """
        try:
            with st.expander(f"❓ {title}"):
                st.markdown(content)
        
        except Exception as e:
            logger.error(f"Error showing help tooltip: {e}")
            st.info(content)
    
    def render_notification_center(self) -> None:
        """Render notification center with all notifications"""
        
        try:
            notifications = st.session_state.get('notifications', [])
            
            if not notifications:
                return
            
            st.subheader("🔔 Notifications")
            
            # Show recent notifications
            recent_notifications = [n for n in notifications 
                                  if (datetime.now() - n.timestamp).total_seconds() < 300]  # Last 5 minutes
            
            if recent_notifications:
                for i, notification in enumerate(reversed(recent_notifications)):
                    with st.container():
                        # Time ago
                        time_ago = datetime.now() - notification.timestamp
                        time_str = f"{int(time_ago.total_seconds())}s ago" if time_ago.total_seconds() < 60 else f"{int(time_ago.total_seconds()/60)}m ago"
                        
                        # Display notification with timestamp
                        col1, col2 = st.columns([4, 1])
                        
                        with col1:
                            self._display_notification(notification)
                        
                        with col2:
                            st.caption(time_str)
                            if notification.dismissible:
                                if st.button("✕", key=f"dismiss_{i}", help="Dismiss"):
                                    notifications.remove(notification)
                                    st.rerun()
            
            # Clear all button
            if len(notifications) > 0:
                if st.button("🗑️ Clear All Notifications"):
                    st.session_state.notifications = []
                    st.rerun()
        
        except Exception as e:
            logger.error(f"Error rendering notification center: {e}")
    
    def show_loading_spinner(self, message: str = "Loading...") -> None:
        """
        Show a loading spinner with message
        
        Args:
            message: Loading message
        """
        try:
            with st.spinner(message):
                # This will show the spinner until the context exits
                pass
        except Exception as e:
            logger.error(f"Error showing loading spinner: {e}")
            st.info(message)
    
    def create_progress_tracker(self, 
                              tasks: List[str],
                              completed_tasks: List[bool]) -> None:
        """
        Create a visual progress tracker
        
        Args:
            tasks: List of task descriptions
            completed_tasks: List of completion status for each task
        """
        try:
            st.subheader("📋 Progress Tracker")
            
            for i, (task, completed) in enumerate(zip(tasks, completed_tasks)):
                col1, col2 = st.columns([1, 10])
                
                with col1:
                    if completed:
                        st.markdown("✅")
                    else:
                        st.markdown("⏳")
                
                with col2:
                    if completed:
                        st.markdown(f"~~{task}~~")  # Strikethrough for completed
                    else:
                        st.markdown(task)
            
            # Overall progress
            completed_count = sum(completed_tasks)
            total_count = len(tasks)
            progress_percentage = completed_count / total_count if total_count > 0 else 0
            
            st.progress(progress_percentage)
            st.caption(f"Progress: {completed_count}/{total_count} tasks completed ({progress_percentage*100:.1f}%)")
        
        except Exception as e:
            logger.error(f"Error creating progress tracker: {e}")
    
    def render_feedback_summary(self) -> None:
        """Render summary of collected feedback"""
        
        try:
            if not self.feedback_history:
                st.info("No feedback collected yet.")
                return
            
            st.subheader("📊 Feedback Summary")
            
            # Feedback statistics
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Total Feedback", len(self.feedback_history))
            
            with col2:
                recent_feedback = [f for f in self.feedback_history 
                                 if (datetime.now() - f.timestamp).total_seconds() < 3600]  # Last hour
                st.metric("Recent Feedback", len(recent_feedback))
            
            with col3:
                rating_feedback = [f for f in self.feedback_history if f.type == FeedbackType.RATING]
                if rating_feedback:
                    avg_rating = sum(f.response for f in rating_feedback) / len(rating_feedback)
                    st.metric("Avg Rating", f"{avg_rating:.1f}/5")
                else:
                    st.metric("Avg Rating", "N/A")
            
            # Recent feedback details
            if st.checkbox("Show Feedback Details"):
                for feedback in reversed(self.feedback_history[-5:]):  # Show last 5
                    with st.expander(f"{feedback.type.value.title()}: {feedback.question[:50]}..."):
                        st.write(f"**Question:** {feedback.question}")
                        st.write(f"**Response:** {feedback.response}")
                        st.write(f"**Time:** {feedback.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
                        if feedback.context:
                            st.write(f"**Context:** {feedback.context}")
        
        except Exception as e:
            logger.error(f"Error rendering feedback summary: {e}")

# Utility functions for common feedback patterns

def show_success_message(message: str, duration: float = 3.0):
    """Show a success message with auto-dismiss"""
    feedback_system = get_feedback_system()
    feedback_system.show_notification(message, NotificationType.SUCCESS, duration)

def show_error_message(message: str, action_label: str = None, action_callback: Callable = None):
    """Show an error message with optional action"""
    feedback_system = get_feedback_system()
    feedback_system.show_notification(
        message, 
        NotificationType.ERROR, 
        action_label=action_label,
        action_callback=action_callback
    )

def show_warning_message(message: str):
    """Show a warning message"""
    feedback_system = get_feedback_system()
    feedback_system.show_notification(message, NotificationType.WARNING)

def show_info_message(message: str):
    """Show an info message"""
    feedback_system = get_feedback_system()
    feedback_system.show_notification(message, NotificationType.INFO)

def get_feedback_system() -> UserFeedbackSystem:
    """Get or create feedback system instance"""
    try:
        if hasattr(st.session_state, '__contains__') and 'user_feedback_system' not in st.session_state:
            st.session_state.user_feedback_system = UserFeedbackSystem()
        
        if hasattr(st.session_state, 'user_feedback_system'):
            return st.session_state.user_feedback_system
        else:
            return UserFeedbackSystem()
    except (AttributeError, TypeError):
        # Session state not available (e.g., in tests)
        return UserFeedbackSystem()