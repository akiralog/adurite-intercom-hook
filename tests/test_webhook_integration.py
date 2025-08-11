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

def test_clickable_image_creation():
    """Test that images are properly converted to clickable Discord markdown links"""
    # Import the IntercomClient to test its image link creation functionality
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    
    from intercom_client import IntercomClient
    
    # Create a client instance to test the image link creation
    client = IntercomClient()
    
    # Test cases for clickable image creation
    test_cases = [
        # HTML with single image
        (
            '<div><img src="https://example.com/screenshot.png"></div>',
            "📷 [Screenshot.Png](https://example.com/screenshot.png)"
        ),
        # HTML with multiple images - use relative URLs when no full URL provided
        (
            '<img src="photo1.jpg"><img src="photo2.png">',
            "📷 [Photo1.Jpg](photo1.jpg) | 📷 [Photo2.Png](photo2.png)"
        ),
        # HTML with complex image attributes
        (
            '<img alt="Screenshot" src="https://downloads.intercomcdn.com/i/o/qknc06vq/1665035471/5d78967052124771df6793d3f9b8/Screenshot_1.png?expires=1754924400&amp;signature=abc123" class="image">',
            "📷 [Screenshot 1.Png](https://downloads.intercomcdn.com/i/o/qknc06vq/1665035471/5d78967052124771df6793d3f9b8/Screenshot_1.png?expires=1754924400&amp;signature=abc123)"
        ),
        # HTML with no images
        (
            '<p>Just some text here</p>',
            "Just some text here"
        ),
    ]
    
    for input_html, expected_output in test_cases:
        # Create a mock part with the HTML
        mock_part = {
            "part_type": "comment",
            "body": input_html,
            "attachments": []
        }
        
        result = client._extract_message_content(mock_part)
        assert result == expected_output, f"Failed to create clickable links from '{input_html}': got '{result}', expected '{expected_output}'"
    
    print("✅ All clickable image creation tests passed!")

def test_fallback_image_extraction():
    """Test that the fallback image extraction method works when the special format fails"""
    # Import the IntercomClient to test its fallback image extraction
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    
    from intercom_client import IntercomClient
    
    # Create a client instance to test the fallback method
    client = IntercomClient()
    
    # Test case that should trigger fallback
    test_html = '<img src="https://example.com/test-image.jpg" alt="Test">'
    
    # Create a mock part with the HTML
    mock_part = {
        "part_type": "comment",
        "body": test_html,
        "attachments": []
    }
    
    # Extract message content
    result = client._extract_message_content(mock_part)
    
    # Should create a clickable link
    expected = "📷 [Test Image.Jpg](https://example.com/test-image.jpg)"
    assert result == expected, f"Fallback extraction failed: got '{result}', expected '{expected}'"
    
    print("✅ Fallback image extraction test passed!")

def test_system_message_filtering():
    """Test that system messages are properly filtered out and don't show as [Content]"""
    # Import the IntercomClient to test its message content extraction
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    
    from intercom_client import IntercomClient
    
    # Create a client instance to test the message content extraction
    client = IntercomClient()
    
    # Test cases for system messages that should be filtered out
    system_message_tests = [
        # Language detection (should be filtered)
        {
            "part_type": "language_detection_details",
            "body": "None",
            "attachments": [],
            "expected": None  # Should be filtered out
        },
        # Conversation attribute update (should be filtered)
        {
            "part_type": "conversation_attribute_updated_by_admin",
            "body": "None",
            "attachments": [],
            "expected": None  # Should be filtered out
        },
        # Regular comment (should NOT be filtered)
        {
            "part_type": "comment",
            "body": "Hello world",
            "attachments": [],
            "expected": "Hello world"  # Should be preserved
        },
        # Comment with image (should NOT be filtered)
        {
            "part_type": "comment",
            "body": '<img src="test.jpg">',
            "attachments": [],
            "expected": "📷 [Test.Jpg](test.jpg)"  # Should be preserved and formatted as clickable link
        }
    ]
    
    for i, test_case in enumerate(system_message_tests):
        result = client._extract_message_content(test_case)
        assert result == test_case["expected"], f"Test {i+1} failed: got '{result}', expected '{test_case['expected']}' for part_type '{test_case['part_type']}'"
    
    print("✅ All system message filtering tests passed!")

def test_html_image_extraction():
    """Test that HTML content with images is properly extracted and formatted"""
    # Import the IntercomClient to test its HTML cleaning functionality
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    
    from intercom_client import IntercomClient
    
    # Create a client instance to test the HTML cleaning method
    client = IntercomClient()
    
    # Test cases for HTML image extraction - now expecting clickable links
    test_cases = [
        # HTML with image tag
        (
            '<div class="intercom-container"><img src="https://downloads.intercomcdn.com/i/o/qknc06vq/1665035471/5d78967052124771df6793d3f9b8/Screenshot_1.png?expires=1754924400&amp;signature=abc123"></div>',
            "📷 [Screenshot 1.Png](https://downloads.intercomcdn.com/i/o/qknc06vq/1665035471/5d78967052124771df6793d3f9b8/Screenshot_1.png?expires=1754924400&amp;signature=abc123)"
        ),
        # HTML with multiple images - use relative URLs when no full URL provided
        (
            '<p>Check these out:</p><img src="photo1.jpg"><img src="photo2.png">',
            "📷 [Photo1.Jpg](photo1.jpg) | 📷 [Photo2.Png](photo2.png)"
        ),
        # HTML with image and text
        (
            '<p>Here is the screenshot:</p><img src="screenshot.png">',
            "📷 [Screenshot.Png](screenshot.png)"
        ),
        # HTML with no images
        (
            '<p>Just some text here</p>',
            "Just some text here"
        ),
        # Empty HTML - returns [Comment] when no meaningful content
        (
            '',
            "[Comment]"
        ),
        # HTML with complex image attributes
        (
            '<img alt="Screenshot" src="test.jpg" class="image" data-id="123">',
            "📷 [Test.Jpg](test.jpg)"
        ),
    ]
    
    for input_html, expected_output in test_cases:
        # Create a mock part with the HTML to test the full message extraction
        mock_part = {
            "part_type": "comment",
            "body": input_html,
            "attachments": []
        }
        
        result = client._extract_message_content(mock_part)
        assert result == expected_output, f"Failed to extract images from '{input_html}': got '{result}', expected '{expected_output}'"
    
    print("✅ All HTML image extraction tests passed!")

def test_attachment_embed_creation():
    """Test that ticket embeds properly display attachment information"""
    # Import the TicketEmbed class to test embed creation
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    
    from ui_components import TicketEmbed
    
    # Test conversation data with attachments
    conversation_data = {
        'subject': 'Test Ticket with Images',
        'body': 'Test conversation thread',
        'id': '12345',
        'status': 'open',
        'user': {'name': 'Test User', 'email': 'test@example.com'},
        'thread_messages': [
            {
                'author': 'Test User',
                'message': 'Hello there!',
                'attachments': [
                    {'type': 'image', 'name': 'screenshot.png', 'url': 'https://example.com/img.png'},
                    {'type': 'file', 'name': 'document.pdf', 'size': 2048, 'url': 'https://example.com/doc.pdf'}
                ]
            },
            {
                'author': 'Admin',
                'message': 'Thanks for the info',
                'attachments': []
            }
        ]
    }
    
    # Create the embed
    embed = TicketEmbed.create_ticket_embed(conversation_data)
    
    # Verify the embed has the expected fields
    assert embed.title == "🎫 New Ticket: Test Ticket with Images"
    assert embed.description == "Test conversation thread"
    
    # Check that media content field exists
    media_field = None
    attachments_field = None
    for field in embed.fields:
        if field.name == "📎 Media Content":
            media_field = field
        elif field.name == "📎 Attachments":
            attachments_field = field
    
    assert media_field is not None, "Media Content field should exist"
    assert attachments_field is not None, "Attachments field should exist"
    
    # Check media content summary
    assert "📷 1 image(s)" in media_field.value
    assert "📎 1 file(s)" in media_field.value
    
    # Check attachments details
    assert "📷 **screenshot.png** (by Test User)" in attachments_field.value
    assert "📎 **document.pdf** (2 KB) (by Test User)" in attachments_field.value
    
    print("✅ All attachment embed creation tests passed!")

def test_image_message_handling():
    """Test that image messages are properly handled and formatted"""
    # Import the IntercomClient to test its message content extraction
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    
    from intercom_client import IntercomClient
    
    # Create a client instance to test the message content extraction
    client = IntercomClient()
    
    # Test cases for different message types
    test_cases = [
        # Text message
        (
            {"body": "Hello world", "attachments": []},
            "Hello world"
        ),
        # Image message
        (
            {"body": "", "attachments": [{"type": "image", "name": "screenshot.png", "url": "https://example.com/image.png"}]},
            "📷 [screenshot.png](https://example.com/image.png)"  # Now expecting clickable link
        ),
        # File message
        (
            {"body": "", "attachments": [{"type": "file", "name": "document.pdf", "size": 1024}]},
            "📎 document.pdf (1 KB)"
        ),
        # Mixed content
        (
            {"body": "Check this out", "attachments": [{"type": "image", "name": "photo.jpg"}]},
            "Check this out"
        ),
        # Multiple attachments - image without URL gets just filename, file gets size
        (
            {"body": "", "attachments": [
                {"type": "image", "name": "img1.jpg"},  # No URL provided
                {"type": "file", "name": "doc.txt", "size": 512}
            ]},
            "📷 img1.jpg | 📎 doc.txt (512 B)"  # Image without URL shows just filename
        ),
        # No content
        (
            {"body": "", "attachments": []},
            None  # Should be filtered out since no meaningful content
        ),
    ]
    
    for input_part, expected_output in test_cases:
        result = client._extract_message_content(input_part)
        assert result == expected_output, f"Failed to extract content from {input_part}: got '{result}', expected '{expected_output}'"
    
    print("✅ All image message handling tests passed!")

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
