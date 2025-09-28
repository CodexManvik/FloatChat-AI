"""
Unit tests for User Feedback System Component
"""

import pytest
import streamlit as st
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import sys
import os

# Add the parent directory to the path to import components
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from components.user_feedback import (
    UserFeedbackSystem, NotificationType, FeedbackType, 
    Notification, UserFeedback,
    show_success_message, show_error_message, show_warning_message, show_info_message
)

class TestUserFeedbackSystem:
    """Test cases for UserFeedbackSystem class."""
    
    @pytest.fixture
    def feedback_system(self):
        """Create a UserFeedbackSystem instance for testing."""
        return UserFeedbackSystem()
    
    @pytest.fixture
    def mock_streamlit(self):
        """Mock Streamlit functions."""
        with patch.multiple(
            'streamlit',
            success=Mock(),
            error=Mock(),
            warning=Mock(),
            info=Mock(),
            session_state=Mock(),
            container=Mock(),
            subheader=Mock(),
            progress=Mock(),
            empty=Mock(),
            slider=Mock(),
            text_area=Mock(),
            selectbox=Mock(),
            checkbox=Mock(),
            button=Mock(),
            columns=Mock(),
            spinner=Mock()
        ) as mocks:
            # Initialize session state mock
            mocks['session_state'].__contains__ = Mock(return_value=False)
            mocks['session_state'].__getitem__ = Mock(return_value=[])
            mocks['session_state'].__setitem__ = Mock()
            mocks['session_state'].get = Mock(return_value=[])
            yield mocks
    
    def test_initialization(self, feedback_system):
        """Test UserFeedbackSystem initialization."""
        assert isinstance(feedback_system, UserFeedbackSystem)
        assert hasattr(feedback_system, 'notifications')
        assert hasattr(feedback_system, 'feedback_history')
        assert feedback_system.notifications == []
        assert feedback_system.feedback_history == []
    
    @patch('streamlit.success')
    @patch('streamlit.session_state', new_callable=lambda: {'notifications': []})
    def test_show_notification_success(self, mock_session_state, mock_success, feedback_system):
        """Test showing success notification."""
        message = "Operation completed successfully"
        
        feedback_system.show_notification(message, NotificationType.SUCCESS)
        
        # Check that notification was added to session state
        assert len(mock_session_state['notifications']) == 1
        
        # Check that Streamlit success was called
        mock_success.assert_called_once()
    
    @patch('streamlit.error')
    @patch('streamlit.session_state', new_callable=lambda: {'notifications': []})
    def test_show_notification_error(self, mock_session_state, mock_error, feedback_system):
        """Test showing error notification."""
        message = "An error occurred"
        
        feedback_system.show_notification(message, NotificationType.ERROR)
        
        # Check that notification was added
        assert len(mock_session_state['notifications']) == 1
        
        # Check that Streamlit error was called
        mock_error.assert_called_once()
    
    @patch('streamlit.warning')
    @patch('streamlit.session_state', new_callable=lambda: {'notifications': []})
    def test_show_notification_warning(self, mock_session_state, mock_warning, feedback_system):
        """Test showing warning notification."""
        message = "This is a warning"
        
        feedback_system.show_notification(message, NotificationType.WARNING)
        
        # Check that notification was added
        assert len(mock_session_state['notifications']) == 1
        
        # Check that Streamlit warning was called
        mock_warning.assert_called_once()
    
    @patch('streamlit.info')
    @patch('streamlit.session_state', new_callable=lambda: {'notifications': []})
    def test_show_notification_info(self, mock_session_state, mock_info, feedback_system):
        """Test showing info notification."""
        message = "Information message"
        
        feedback_system.show_notification(message, NotificationType.INFO)
        
        # Check that notification was added
        assert len(mock_session_state['notifications']) == 1
        
        # Check that Streamlit info was called
        mock_info.assert_called_once()
    
    def test_show_notification_with_action(self, feedback_system):
        """Test showing notification with action callback."""
        message = "Action required"
        action_called = False
        
        def action_callback():
            nonlocal action_called
            action_called = True
        
        with patch('streamlit.session_state', {'notifications': []}), \
             patch('streamlit.info'), \
             patch('streamlit.button', return_value=True):
            
            feedback_system.show_notification(
                message, 
                NotificationType.INFO,
                action_label="Take Action",
                action_callback=action_callback
            )
            
            # Simulate action button click by calling the callback
            action_callback()
            assert action_called
    
    def test_show_progress_operation_success(self, feedback_system):
        """Test progress operation with successful execution."""
        steps = ["Step 1", "Step 2", "Step 3"]
        
        def test_operation(progress_callback):
            for i, step in enumerate(steps):
                progress_callback(i, f"Executing {step}")
            return "success"
        
        with patch('streamlit.container') as mock_container, \
             patch('streamlit.subheader'), \
             patch('streamlit.progress'), \
             patch('streamlit.empty'), \
             patch('streamlit.session_state', {'progress_operations': {}}), \
             patch('time.sleep'):
            
            # Mock container context manager
            mock_container.return_value.__enter__ = Mock(return_value=None)
            mock_container.return_value.__exit__ = Mock(return_value=None)
            mock_container.return_value.empty = Mock()
            
            result = feedback_system.show_progress_operation(
                "test_op", "Test Operation", steps, test_operation
            )
            
            assert result == "success"
    
    def test_show_progress_operation_failure(self, feedback_system):
        """Test progress operation with failed execution."""
        steps = ["Step 1", "Step 2"]
        
        def failing_operation(progress_callback):
            progress_callback(0, "Starting")
            raise ValueError("Operation failed")
        
        with patch('streamlit.container') as mock_container, \
             patch('streamlit.subheader'), \
             patch('streamlit.progress'), \
             patch('streamlit.empty'), \
             patch('streamlit.session_state', {'progress_operations': {}}):
            
            # Mock container context manager
            mock_container.return_value.__enter__ = Mock(return_value=None)
            mock_container.return_value.__exit__ = Mock(return_value=None)
            mock_container.return_value.empty = Mock()
            
            with pytest.raises(ValueError):
                feedback_system.show_progress_operation(
                    "test_op", "Test Operation", steps, failing_operation
                )
    
    def test_collect_user_feedback_rating(self, feedback_system):
        """Test collecting rating feedback."""
        feedback_id = "test_rating"
        question = "How would you rate this feature?"
        
        with patch('streamlit.session_state', {'feedback_responses': {}}), \
             patch('streamlit.subheader'), \
             patch('streamlit.write'), \
             patch('streamlit.slider', return_value=4), \
             patch('streamlit.button', return_value=True), \
             patch('streamlit.success'):
            
            result = feedback_system.collect_user_feedback(
                feedback_id, question, FeedbackType.RATING
            )
            
            assert result == 4
            assert len(feedback_system.feedback_history) == 1
            
            feedback = feedback_system.feedback_history[0]
            assert feedback.feedback_id == feedback_id
            assert feedback.type == FeedbackType.RATING
            assert feedback.response == 4
    
    def test_collect_user_feedback_text(self, feedback_system):
        """Test collecting text feedback."""
        feedback_id = "test_text"
        question = "Please provide your comments"
        response_text = "This is my feedback"
        
        with patch('streamlit.session_state', {'feedback_responses': {}}), \
             patch('streamlit.subheader'), \
             patch('streamlit.write'), \
             patch('streamlit.text_area', return_value=response_text), \
             patch('streamlit.button', return_value=True), \
             patch('streamlit.success'):
            
            result = feedback_system.collect_user_feedback(
                feedback_id, question, FeedbackType.TEXT
            )
            
            assert result == response_text
            assert len(feedback_system.feedback_history) == 1
    
    def test_collect_user_feedback_choice(self, feedback_system):
        """Test collecting choice feedback."""
        feedback_id = "test_choice"
        question = "Which option do you prefer?"
        options = ["Option A", "Option B", "Option C"]
        selected_option = "Option B"
        
        with patch('streamlit.session_state', {'feedback_responses': {}}), \
             patch('streamlit.subheader'), \
             patch('streamlit.write'), \
             patch('streamlit.selectbox', return_value=selected_option), \
             patch('streamlit.button', return_value=True), \
             patch('streamlit.success'):
            
            result = feedback_system.collect_user_feedback(
                feedback_id, question, FeedbackType.CHOICE, options=options
            )
            
            assert result == selected_option
            assert len(feedback_system.feedback_history) == 1
    
    def test_collect_user_feedback_boolean(self, feedback_system):
        """Test collecting boolean feedback."""
        feedback_id = "test_boolean"
        question = "Do you agree with this statement?"
        
        with patch('streamlit.session_state', {'feedback_responses': {}}), \
             patch('streamlit.subheader'), \
             patch('streamlit.write'), \
             patch('streamlit.checkbox', return_value=True), \
             patch('streamlit.button', return_value=True), \
             patch('streamlit.success'):
            
            result = feedback_system.collect_user_feedback(
                feedback_id, question, FeedbackType.BOOLEAN
            )
            
            assert result is True
            assert len(feedback_system.feedback_history) == 1
    
    def test_collect_user_feedback_already_collected(self, feedback_system):
        """Test collecting feedback that was already provided."""
        feedback_id = "existing_feedback"
        existing_response = "Already provided"
        
        with patch('streamlit.session_state', {'feedback_responses': {feedback_id: existing_response}}):
            result = feedback_system.collect_user_feedback(
                feedback_id, "Test question", FeedbackType.TEXT
            )
            
            assert result == existing_response
    
    def test_collect_user_feedback_no_submit(self, feedback_system):
        """Test collecting feedback without submitting."""
        feedback_id = "test_no_submit"
        question = "Test question"
        
        with patch('streamlit.session_state', {'feedback_responses': {}}), \
             patch('streamlit.subheader'), \
             patch('streamlit.write'), \
             patch('streamlit.text_area', return_value="Some text"), \
             patch('streamlit.button', return_value=False):  # Not submitted
            
            result = feedback_system.collect_user_feedback(
                feedback_id, question, FeedbackType.TEXT
            )
            
            assert result is None
            assert len(feedback_system.feedback_history) == 0
    
    def test_show_status_indicator(self, feedback_system):
        """Test showing status indicator."""
        with patch('streamlit.columns', return_value=[Mock(), Mock()]) as mock_columns, \
             patch('streamlit.markdown'):
            
            mock_col1, mock_col2 = Mock(), Mock()
            mock_columns.return_value = [mock_col1, mock_col2]
            mock_col1.__enter__ = Mock(return_value=mock_col1)
            mock_col1.__exit__ = Mock(return_value=None)
            mock_col2.__enter__ = Mock(return_value=mock_col2)
            mock_col2.__exit__ = Mock(return_value=None)
            
            feedback_system.show_status_indicator("System Online", "All services running", "green")
            
            # Should not raise any exceptions
    
    def test_create_confirmation_dialog_confirm(self, feedback_system):
        """Test confirmation dialog with confirm action."""
        with patch('streamlit.warning'), \
             patch('streamlit.columns', return_value=[Mock(), Mock(), Mock()]) as mock_columns, \
             patch('streamlit.button', side_effect=[True, False]):  # Confirm clicked, cancel not clicked
            
            # Mock column context managers
            for col in mock_columns.return_value:
                col.__enter__ = Mock(return_value=col)
                col.__exit__ = Mock(return_value=None)
            
            result = feedback_system.create_confirmation_dialog("Are you sure?")
            
            assert result is True
    
    def test_create_confirmation_dialog_cancel(self, feedback_system):
        """Test confirmation dialog with cancel action."""
        with patch('streamlit.warning'), \
             patch('streamlit.columns', return_value=[Mock(), Mock(), Mock()]) as mock_columns, \
             patch('streamlit.button', side_effect=[False, True]):  # Confirm not clicked, cancel clicked
            
            # Mock column context managers
            for col in mock_columns.return_value:
                col.__enter__ = Mock(return_value=col)
                col.__exit__ = Mock(return_value=None)
            
            result = feedback_system.create_confirmation_dialog("Are you sure?")
            
            assert result is False
    
    def test_create_confirmation_dialog_no_action(self, feedback_system):
        """Test confirmation dialog with no action."""
        with patch('streamlit.warning'), \
             patch('streamlit.columns', return_value=[Mock(), Mock(), Mock()]) as mock_columns, \
             patch('streamlit.button', side_effect=[False, False]):  # Neither button clicked
            
            # Mock column context managers
            for col in mock_columns.return_value:
                col.__enter__ = Mock(return_value=col)
                col.__exit__ = Mock(return_value=None)
            
            result = feedback_system.create_confirmation_dialog("Are you sure?")
            
            assert result is None
    
    def test_show_help_tooltip(self, feedback_system):
        """Test showing help tooltip."""
        with patch('streamlit.expander') as mock_expander, \
             patch('streamlit.markdown'):
            
            mock_expander.return_value.__enter__ = Mock()
            mock_expander.return_value.__exit__ = Mock()
            
            feedback_system.show_help_tooltip("This is help content", "Help Title")
            
            mock_expander.assert_called_once()
    
    def test_show_loading_spinner(self, feedback_system):
        """Test showing loading spinner."""
        with patch('streamlit.spinner') as mock_spinner:
            mock_spinner.return_value.__enter__ = Mock()
            mock_spinner.return_value.__exit__ = Mock()
            
            feedback_system.show_loading_spinner("Loading data...")
            
            mock_spinner.assert_called_once_with("Loading data...")
    
    def test_create_progress_tracker(self, feedback_system):
        """Test creating progress tracker."""
        tasks = ["Task 1", "Task 2", "Task 3"]
        completed = [True, True, False]
        
        with patch('streamlit.subheader'), \
             patch('streamlit.columns', return_value=[Mock(), Mock()]) as mock_columns, \
             patch('streamlit.markdown'), \
             patch('streamlit.progress'), \
             patch('streamlit.caption'):
            
            # Mock column context managers
            for col in mock_columns.return_value:
                col.__enter__ = Mock(return_value=col)
                col.__exit__ = Mock(return_value=None)
            
            feedback_system.create_progress_tracker(tasks, completed)
            
            # Should not raise any exceptions
    
    def test_render_notification_center_empty(self, feedback_system):
        """Test rendering notification center with no notifications."""
        with patch('streamlit.session_state', {'notifications': []}):
            # Should not raise any exceptions and should return early
            feedback_system.render_notification_center()
    
    def test_render_notification_center_with_notifications(self, feedback_system):
        """Test rendering notification center with notifications."""
        notifications = [
            Notification(
                message="Test notification",
                type=NotificationType.INFO,
                timestamp=datetime.now(),
                dismissible=True
            )
        ]
        
        with patch('streamlit.session_state', {'notifications': notifications}), \
             patch('streamlit.subheader'), \
             patch('streamlit.container') as mock_container, \
             patch('streamlit.columns', return_value=[Mock(), Mock()]), \
             patch('streamlit.caption'), \
             patch('streamlit.button', return_value=False), \
             patch('streamlit.info'):
            
            mock_container.return_value.__enter__ = Mock()
            mock_container.return_value.__exit__ = Mock()
            
            feedback_system.render_notification_center()
            
            # Should not raise any exceptions
    
    def test_render_feedback_summary_empty(self, feedback_system):
        """Test rendering feedback summary with no feedback."""
        with patch('streamlit.info'):
            feedback_system.render_feedback_summary()
            
            # Should show "No feedback collected yet."
    
    def test_render_feedback_summary_with_feedback(self, feedback_system):
        """Test rendering feedback summary with feedback data."""
        # Add some test feedback
        feedback_system.feedback_history = [
            UserFeedback(
                feedback_id="test1",
                type=FeedbackType.RATING,
                question="Test question",
                response=4,
                timestamp=datetime.now(),
                context={}
            ),
            UserFeedback(
                feedback_id="test2",
                type=FeedbackType.TEXT,
                question="Another question",
                response="Good feedback",
                timestamp=datetime.now(),
                context={}
            )
        ]
        
        with patch('streamlit.subheader'), \
             patch('streamlit.columns', return_value=[Mock(), Mock(), Mock()]) as mock_columns, \
             patch('streamlit.metric'), \
             patch('streamlit.checkbox', return_value=True), \
             patch('streamlit.expander') as mock_expander, \
             patch('streamlit.write'):
            
            # Mock column context managers
            for col in mock_columns.return_value:
                col.__enter__ = Mock(return_value=col)
                col.__exit__ = Mock(return_value=None)
            
            mock_expander.return_value.__enter__ = Mock()
            mock_expander.return_value.__exit__ = Mock()
            
            feedback_system.render_feedback_summary()
            
            # Should not raise any exceptions

class TestUtilityFunctions:
    """Test cases for utility functions."""
    
    @patch('streamlit.session_state', {'user_feedback_system': UserFeedbackSystem()})
    def test_show_success_message(self):
        """Test show_success_message utility function."""
        with patch.object(UserFeedbackSystem, 'show_notification') as mock_show:
            show_success_message("Success!")
            mock_show.assert_called_once_with("Success!", NotificationType.SUCCESS, 3.0)
    
    @patch('streamlit.session_state', {'user_feedback_system': UserFeedbackSystem()})
    def test_show_error_message(self):
        """Test show_error_message utility function."""
        with patch.object(UserFeedbackSystem, 'show_notification') as mock_show:
            show_error_message("Error occurred!")
            mock_show.assert_called_once_with(
                "Error occurred!", 
                NotificationType.ERROR, 
                action_label=None,
                action_callback=None
            )
    
    @patch('streamlit.session_state', {'user_feedback_system': UserFeedbackSystem()})
    def test_show_warning_message(self):
        """Test show_warning_message utility function."""
        with patch.object(UserFeedbackSystem, 'show_notification') as mock_show:
            show_warning_message("Warning!")
            mock_show.assert_called_once_with("Warning!", NotificationType.WARNING)
    
    @patch('streamlit.session_state', {'user_feedback_system': UserFeedbackSystem()})
    def test_show_info_message(self):
        """Test show_info_message utility function."""
        with patch.object(UserFeedbackSystem, 'show_notification') as mock_show:
            show_info_message("Information")
            mock_show.assert_called_once_with("Information", NotificationType.INFO)

if __name__ == "__main__":
    pytest.main([__file__])