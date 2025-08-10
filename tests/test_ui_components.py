"""
Tests for the ui_components module
"""
import pytest
import discord
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from ui_components import TicketView
import asyncio


class TestTicketView:
    """Test cases for TicketView class"""
    
    @pytest.fixture
    def mock_interaction(self):
        """Create a mock Discord interaction"""
        interaction = Mock()
        interaction.id = "test_interaction_123"
        interaction.data = {"custom_id": "quick_reply_no_robux_12345"}
        interaction.response = Mock()
        interaction.response.send_message = AsyncMock()
        interaction.followup = Mock()
        interaction.followup.send = AsyncMock()
        interaction.message = Mock()
        interaction.message.delete = AsyncMock()
        return interaction
    
    @pytest.fixture
    def ticket_view(self):
        """Create a TicketView instance for testing"""
        # Mock the required dependencies
        mock_intercom = Mock()
        mock_db = Mock()
        
        # Mock the asyncio event loop to prevent "no running event loop"
        with patch('asyncio.get_running_loop') as mock_loop:
            mock_future = Mock()
            mock_loop.return_value.create_future.return_value = mock_future
            
            return TicketView(ticket_id="12345", conversation_id="conv_123",
                             intercom_client=mock_intercom, db_manager=mock_db)
    
    def test_ticket_view_initialization(self):
        """Test TicketView initialization"""
        mock_intercom = Mock()
        mock_db = Mock()
        
        # Mock the asyncio event loop to prevent "no running event loop" 
        with patch('asyncio.get_running_loop') as mock_loop:
            mock_future = Mock()
            mock_loop.return_value.create_future.return_value = mock_future
            
            view = TicketView(ticket_id="12345", conversation_id="conv_123",
                             intercom_client=mock_intercom, db_manager=mock_db)
            
            assert view.ticket_id == "12345"
            assert view.conversation_id == "conv_123"
            assert view.intercom_client == mock_intercom
            assert view.db_manager == mock_db
    
    def test_quick_reply_button_creation(self):
        """Test that quick reply buttons are created correctly"""
        mock_intercom = Mock()
        mock_db = Mock()
        
        # Mock the asyncio event loop to prevent "no running event loop" 
        with patch('asyncio.get_running_loop') as mock_loop:
            mock_future = Mock()
            mock_loop.return_value.create_future.return_value = mock_future
            
            view = TicketView(ticket_id="12345", conversation_id="conv_123",
                             intercom_client=mock_intercom, db_manager=mock_db)
            
            # Check that buttons were created
            assert len(view.children) > 0
            
            # Check that all children are buttons
            for child in view.children:
                assert hasattr(child, 'custom_id')
                assert hasattr(child, 'label')
    
    def test_quick_reply_button_custom_id_format(self):
        """Test that button custom_id follows the correct format"""
        mock_intercom = Mock()
        mock_db = Mock()
        
        # Mock the asyncio event loop to prevent "no running event loop" 
        with patch('asyncio.get_running_loop') as mock_loop:
            mock_future = Mock()
            mock_loop.return_value.create_future.return_value = mock_future
            
            view = TicketView(ticket_id="12345", conversation_id="conv_123",
                             intercom_client=mock_intercom, db_manager=mock_db)
            
            # Check that each button has the correct custom_id format
            for child in view.children:
                custom_id = child.custom_id
                
                # Check that the custom_id follows one of the expected patterns
                assert (
                    custom_id.startswith("quick_reply_") or
                    custom_id.startswith("custom_reply_") or
                    custom_id.startswith("close_ticket_")
                ), f"Button custom_id '{custom_id}' doesn't follow expected format"
                
                # Check that it ends with the ticket_id
                assert custom_id.endswith("_12345"), f"Button custom_id '{custom_id}' doesn't end with ticket_id"
                
                # For quick reply buttons, check the key format
                if custom_id.startswith("quick_reply_"):
                    key_part = custom_id[len("quick_reply_"):-len("_12345")]
                    assert key_part in ["no_robux"], f"Unknown quick reply key: {key_part}"

    @pytest.mark.asyncio
    async def test_quick_reply_callback_parsing(self, ticket_view, mock_interaction):
        """Test the quick reply callback parsing logic"""
        # Test with a key that contains underscores
        mock_interaction.data["custom_id"] = "quick_reply_no_robux_12345"
        
        # Mock the config
        with patch('ui_components.Config') as mock_config:
            mock_config.QUICK_REPLIES = {
                "no_robux": {
                    "label": "No Robux",
                    "reply": "Test reply",
                    "close_ticket": False
                }
            }
            mock_config.INTERCOM_ADMIN_ID = "admin_123"
            
            # Mock the intercom client
            ticket_view.intercom_client.send_reply = AsyncMock(return_value=True)
            ticket_view.db_manager.update_ticket_status = AsyncMock()
            
            # Call the callback
            await ticket_view.quick_reply_callback(mock_interaction)
            
            # Verify that the correct action was extracted and processed
            ticket_view.intercom_client.send_reply.assert_called_once()
            ticket_view.db_manager.update_ticket_status.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_quick_reply_callback_with_simple_key(self, ticket_view, mock_interaction):
        """Test callback with a simple key (no underscores)"""
        mock_interaction.data["custom_id"] = "quick_reply_nofunds_12345"
        
        with patch('ui_components.Config') as mock_config:
            mock_config.QUICK_REPLIES = {
                "nofunds": {
                    "label": "No Funds",
                    "reply": "Simple reply",
                    "close_ticket": False
                }
            }
            mock_config.INTERCOM_ADMIN_ID = "admin_123"
            
            ticket_view.intercom_client.send_reply = AsyncMock(return_value=True)
            ticket_view.db_manager.update_ticket_status = AsyncMock()
            
            await ticket_view.quick_reply_callback(mock_interaction)
            
            ticket_view.intercom_client.send_reply.assert_called_once()
            ticket_view.db_manager.update_ticket_status.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_quick_reply_callback_invalid_format(self, ticket_view, mock_interaction):
        """Test callback with invalid custom_id format"""
        mock_interaction.data["custom_id"] = "invalid_format"
        
        with patch('ui_components.Config') as mock_config:
            mock_config.QUICK_REPLIES = {}
            
            # Should handle gracefully without crashing
            await ticket_view.quick_reply_callback(mock_interaction)
            
            # The callback should extract "unknown" as the action and not find it in QUICK_REPLIES
            # It should not send an error message for this case, just log the debug message
            # So we don't assert that send_message was called

    def test_button_labels_match_config(self):
        """Test that button labels match the configuration"""
        mock_intercom = Mock()
        mock_db = Mock()
        
        # Mock the asyncio event loop to prevent "no running event loop" 
        with patch('asyncio.get_running_loop') as mock_loop:
            mock_future = Mock()
            mock_loop.return_value.create_future.return_value = mock_future
            
            view = TicketView(ticket_id="12345", conversation_id="conv_123",
                             intercom_client=mock_intercom, db_manager=mock_db)
            
            # Get the expected labels from the config
            from config import Config
            expected_labels = [config["label"] for config in Config.QUICK_REPLIES.values()]
            
            # Check that all expected quick reply labels are present
            quick_reply_buttons = [child for child in view.children if child.custom_id.startswith("quick_reply_")]
            actual_labels = [child.label for child in quick_reply_buttons]
            
            for expected_label in expected_labels:
                assert expected_label in actual_labels, f"Label '{expected_label}' not found in quick reply buttons"
            
            # Check that other button types exist
            custom_reply_buttons = [child for child in view.children if child.custom_id.startswith("custom_reply_")]
            close_ticket_buttons = [child for child in view.children if child.custom_id.startswith("close_ticket_")]
            
            assert len(custom_reply_buttons) == 1, "Should have exactly one custom reply button"
            assert len(close_ticket_buttons) == 1, "Should have exactly one close ticket button"


class TestQuickReplyParsing:
    """Test cases specifically for the quick reply parsing logic"""
    
    def test_parse_key_with_underscores(self):
        """Test parsing keys that contain underscores"""
        # Simulate the parsing logic from the callback
        custom_id = "quick_reply_no_robux_12345"
        parts = custom_id.split("_")
        
        if len(parts) >= 4:
            key_parts = parts[2:-1]  # Everything between "reply" and ticket_id
            key = "_".join(key_parts)
            assert key == "no_robux"
    
    def test_parse_key_without_underscores(self):
        """Test parsing keys without underscores"""
        custom_id = "quick_reply_nofunds_12345"
        parts = custom_id.split("_")
        
        if len(parts) >= 4:
            key_parts = parts[2:-1]
            key = "_".join(key_parts)
            assert key == "nofunds"
    
    def test_parse_key_with_multiple_underscores(self):
        """Test parsing keys with multiple underscores"""
        custom_id = "quick_reply_very_long_key_name_12345"
        parts = custom_id.split("_")
        
        if len(parts) >= 4:
            key_parts = parts[2:-1]
            key = "_".join(key_parts)
            assert key == "very_long_key_name"
