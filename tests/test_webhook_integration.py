"""
Pytest-compatible tests for webhook integration
"""
import pytest
import asyncio
import aiohttp
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

@pytest.mark.asyncio
async def test_webhook_endpoint_connectivity():
    """Test that webhook endpoint is reachable"""
    webhook_url = "http://localhost:8000/webhook"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(webhook_url) as response:
                # Even if it's not a GET endpoint, we should get some response
                assert response.status in [200, 405, 404]  # 405 = Method Not Allowed is expected
    except aiohttp.ClientConnectorError:
        pytest.skip("Webhook server not running - skipping connectivity test")

@pytest.mark.asyncio
async def test_intercom_api_configuration():
    """Test that Intercom API configuration is present"""
    access_token = os.getenv('INTERCOM_ACCESS_TOKEN')
    
    if not access_token or access_token == "your_intercom_access_token_here":
        pytest.skip("INTERCOM_ACCESS_TOKEN not configured")
    
    # Basic validation that token exists and has reasonable length
    assert len(access_token) > 10, "Access token seems too short"
    assert not access_token.startswith("your_"), "Access token not properly configured"

@pytest.mark.asyncio
async def test_environment_variables():
    """Test that required environment variables are set"""
    required_vars = [
        'DISCORD_TOKEN',
        'DISCORD_CHANNEL_ID',
        'INTERCOM_ACCESS_TOKEN',
        'INTERCOM_WEBHOOK_SECRET'
    ]
    
    missing_vars = []
    for var in required_vars:
        value = os.getenv(var)
        if not value or value.startswith("your_"):
            missing_vars.append(var)
    
    if missing_vars:
        pytest.skip(f"Missing or unconfigured environment variables: {', '.join(missing_vars)}")
    
    # If we get here, all vars are configured
    assert True

def test_html_entity_decoding():
    """Test that HTML entities are properly decoded"""
    # Import the IntercomClient to test its HTML cleaning functionality
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    
    from intercom_client import IntercomClient
    
    # Create a client instance to test the HTML cleaning method
    client = IntercomClient()
    
    # Test cases for HTML entity decoding
    test_cases = [
        ("Hello &gt; World", "Hello > World"),
        ("Hello &lt; World", "Hello < World"),
        ("Hello &amp; World", "Hello & World"),
        ("Hello -> World", "Hello -> World"),  # Should remain unchanged
        ("Hello <- World", "Hello <- World"),  # Should remain unchanged
        ("<p>Hello World</p>", "Hello World"),  # HTML tags should be removed
        ("Hello &gt; World &lt; Test", "Hello > World < Test"),  # Multiple entities
    ]
    
    for input_text, expected_output in test_cases:
        result = client._clean_html(input_text)
        assert result == expected_output, f"Failed to decode '{input_text}': got '{result}', expected '{expected_output}'"
    
    print("✅ All HTML entity decoding tests passed!")

def test_dotenv_file_exists():
    """Test that .env file exists (skipped in CI)"""
    # Skip this test in CI environment where .env file shouldn't exist
    if os.getenv('CI'):
        pytest.skip("Skipping .env file check in CI environment")
    
    # Only run this test locally where .env file should exist
    assert os.path.exists('.env'), ".env file not found - please create one with your configuration"
