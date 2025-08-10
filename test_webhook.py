#!/usr/bin/env python3
"""
Webhook test script for Discord Intercom Ticket Bot
This script simulates Intercom webhooks to test your bot's webhook handling
"""

import asyncio
import aiohttp
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def test_webhook():
    """Test the webhook endpoint"""
    webhook_url = "http://localhost:8000/webhook"
    
    # Sample webhook data for a new ticket
    test_data = {
        "topic": "conversation.user.created",
        "data": {
            "item": {
                "id": "test_conversation_123",
                "type": "conversation",
                "created_at": 1234567890,
                "updated_at": 1234567890,
                "user": {
                    "id": "test_user_456",
                    "name": "Test User",
                    "email": "test@example.com"
                },
                "conversation_parts": {
                    "conversation_parts": [
                        {
                            "id": "test_part_789",
                            "type": "comment",
                            "body": "This is a test ticket message for testing the webhook functionality.",
                            "author": {
                                "id": "test_user_456",
                                "type": "user"
                            }
                        }
                    ]
                }
            }
        }
    }
    
    print("🧪 Testing webhook endpoint...")
    print(f"URL: {webhook_url}")
    print(f"Data: {json.dumps(test_data, indent=2)}")
    print("-" * 50)
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=test_data) as response:
                print(f"Status: {response.status}")
                print(f"Response: {await response.text()}")
                
                if response.status == 200:
                    print("✅ Webhook test successful!")
                else:
                    print("❌ Webhook test failed!")
                    
    except aiohttp.ClientConnectorError:
        print("❌ Could not connect to webhook server!")
        print("Make sure the bot is running and the webhook server is active.")
    except Exception as e:
        print(f"❌ Error testing webhook: {e}")

async def test_intercom_api():
    """Test Intercom API connectivity"""
    access_token = os.getenv('INTERCOM_ACCESS_TOKEN')
    
    if not access_token or access_token == "your_intercom_access_token_here":
        print("⚠️  INTERCOM_ACCESS_TOKEN not configured, skipping API test")
        return
    
    print("\n🌐 Testing Intercom API connectivity...")
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            # Test basic API call
            async with session.get("https://api.intercom.io/me", headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    print("✅ Intercom API connection successful!")
                    print(f"   App: {data.get('name', 'Unknown')}")
                else:
                    print(f"❌ Intercom API test failed: {response.status}")
                    print(f"   Response: {await response.text()}")
                    
    except Exception as e:
        print(f"❌ Error testing Intercom API: {e}")

def main():
    """Main test function"""
    print("🔍 Discord Intercom Ticket Bot - Webhook Test")
    print("=" * 60)
    
    # Check if bot is configured
    if not os.path.exists('.env'):
        print("❌ .env file not found!")
        print("Please create a .env file with your configuration first.")
        return
    
    # Run tests
    asyncio.run(test_webhook())
    asyncio.run(test_intercom_api())
    
    print("\n" + "=" * 60)
    print("📋 Test Summary:")
    print("1. Make sure the bot is running (python bot.py)")
    print("2. Check that port 8000 is accessible")
    print("3. Verify your Intercom webhook configuration")
    print("4. Check Discord for test ticket messages")

if __name__ == "__main__":
    main()
