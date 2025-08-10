"""
Tests for the config module
"""
import pytest
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add the parent directory to Python path so we can import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import Config


class TestConfig:
    """Test cases for Config class"""
    
    def test_quick_replies_structure(self):
        """Test that QUICK_REPLIES has the correct structure"""
        assert hasattr(Config, 'QUICK_REPLIES')
        assert isinstance(Config.QUICK_REPLIES, dict)
        
        # Test that each quick reply has required keys
        for key, config in Config.QUICK_REPLIES.items():
            assert 'label' in config, f"Missing 'label' in {key}"
            assert 'reply' in config, f"Missing 'reply' in {key}"
            assert 'close_ticket' in config, f"Missing 'close_ticket' in {key}"
            assert isinstance(config['close_ticket'], bool), f"'close_ticket' must be boolean in {key}"
    
    def test_quick_replies_no_robux(self):
        """Test the no_robux quick reply configuration"""
        assert 'no_robux' in Config.QUICK_REPLIES
        no_robux = Config.QUICK_REPLIES['no_robux']
        assert no_robux['label'] == 'nofunds'
        assert 'Robux' in no_robux['reply']
        assert no_robux['close_ticket'] is True
    
    @patch.dict(os.environ, {
        'DISCORD_TOKEN': 'test_token',
        'DISCORD_CHANNEL_ID': '123456789',
        'INTERCOM_ACCESS_TOKEN': 'test_access_token',
        'INTERCOM_WEBHOOK_SECRET': 'test_secret'
    })
    def test_environment_variables(self):
        """Test that environment variables are properly loaded"""
        # This test would require refactoring Config to use environment variables
        # For now, test the structure
        assert hasattr(Config, 'QUICK_REPLIES')
    
    def test_config_attributes_exist(self):
        """Test that all expected config attributes exist"""
        expected_attrs = ['QUICK_REPLIES']
        for attr in expected_attrs:
            assert hasattr(Config, attr), f"Config missing attribute: {attr}"


class TestQuickRepliesIntegration:
    """Integration tests for quick replies functionality"""
    
    def test_quick_reply_keys_format(self):
        """Test that quick reply keys can contain underscores"""
        keys_with_underscores = [key for key in Config.QUICK_REPLIES.keys() if '_' in key]
        assert len(keys_with_underscores) > 0, "Should have at least one key with underscores"
        
        assert 'no_robux' in Config.QUICK_REPLIES
        assert Config.QUICK_REPLIES['no_robux']['label'] == 'nofunds'
