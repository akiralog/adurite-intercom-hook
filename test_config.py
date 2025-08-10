"""
Configuration test script for Discord Intercom Ticket Bot
Run this before starting the bot to verify your setup
"""

import os
import sys
from dotenv import load_dotenv

def test_config():
    """Test the bot configuration"""
    print("Testing Discord Intercom Ticket Bot Configuration...")
    print("=" * 50)

    load_dotenv()
    
    # Test Discord configuration
    print("\nDiscord Configuration:")
    discord_token = os.getenv('DISCORD_TOKEN')
    discord_channel = os.getenv('DISCORD_CHANNEL_ID')
    
    if discord_token:
        print("DISCORD_TOKEN: Set")
        if discord_token == "your_discord_bot_token_here":
            print("DISCORD_TOKEN: Still using placeholder value")
        else:
            print("DISCORD_TOKEN: Valid format")
    else:
        print("DISCORD_TOKEN: Not set")
    
    if discord_channel:
        print("DISCORD_CHANNEL_ID: Set")
        try:
            channel_id = int(discord_channel)
            print(f"DISCORD_CHANNEL_ID: Valid number ({channel_id})")
        except ValueError:
            print("DISCORD_CHANNEL_ID: Not a valid number")
    else:
        print("DISCORD_CHANNEL_ID: Not set")
    
    # Test Intercom configuration
    print("\nIntercom Configuration:")
    intercom_token = os.getenv('INTERCOM_ACCESS_TOKEN')
    intercom_secret = os.getenv('INTERCOM_WEBHOOK_SECRET')
    intercom_admin_id = os.getenv('INTERCOM_ADMIN_ID')
    
    if intercom_token:
        print("NTERCOM_ACCESS_TOKEN: Set")
        if intercom_token == "your_intercom_access_token_here":
            print("INTERCOM_ACCESS_TOKEN: Still using placeholder value")
        else:
            print("INTERCOM_ACCESS_TOKEN: Valid format")
    else:
        print("INTERCOM_ACCESS_TOKEN: Not set")
    
    if intercom_secret:
        print("INTERCOM_WEBHOOK_SECRET: Set")
        if intercom_secret == "your_intercom_webhook_secret_here":
            print("INTERCOM_WEBHOOK_SECRET: Still using placeholder value")
        else:
            print("INTERCOM_WEBHOOK_SECRET: Valid format")
    else:
        print("INTERCOM_WEBHOOK_SECRET: Not set")
    
    if intercom_admin_id:
        print("INTERCOM_ADMIN_ID: Set")
        print(f"INTERCOM_ADMIN_ID: {intercom_admin_id}")
    else:
        print("INTERCOM_ADMIN_ID: Not set (will use default: 6673256)")
    
    # Test dependencies
    print("\nDependencies:")
    try:
        import discord
        print("discord.py: Installed")
    except ImportError:
        print("discord.py: Not installed")
    
    try:
        import aiohttp
        print("aiohttp: Installed")
    except ImportError:
        print("aiohttp: Not installed")
    
    try:
        import sqlite3
        print("sqlite3: Available (built-in)")
    except ImportError:
        print("sqlite3: Not available")
    
    # Summary
    print("\n" + "=" * 50)
    print("Configuration Summary:")
    
    required_vars = ['DISCORD_TOKEN', 'DISCORD_CHANNEL_ID', 'INTERCOM_ACCESS_TOKEN', 'INTERCOM_WEBHOOK_SECRET']
    optional_vars = ['INTERCOM_ADMIN_ID']
    missing_vars = [var for var in required_vars if not os.getenv(var) or os.getenv(var).startswith('your_')]
    
    if not missing_vars:
        print("All required configuration is set!")
        print("You can now run the bot with: python bot.py")
    else:
        print("Missing or incomplete configuration:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\nPlease complete your .env file and try again.")
    
    print("\n" + "=" * 50)

if __name__ == "__main__":
    test_config()
