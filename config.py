import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    # Discord Bot Configuration
    DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
    DISCORD_CHANNEL_ID = int(os.getenv('DISCORD_CHANNEL_ID', 0))
    
    # Intercom Configuration
    INTERCOM_ACCESS_TOKEN = os.getenv('INTERCOM_ACCESS_TOKEN')
    INTERCOM_WEBHOOK_SECRET = os.getenv('INTERCOM_WEBHOOK_SECRET')
    
    # Webhook Configuration
    WEBHOOK_HOST = 'localhost'
    WEBHOOK_PORT = 8000
    
    # Quick reply buttons configuration
    QUICK_REPLIES = {
        "no_robux": {
            "label": "Sorry, we don't sell Robux anymore",
            "reply": "I apologize, but we no longer sell Robux. Is there anything else I can help you with?",
            "close_ticket": True
        },
        "out_of_stock": {
            "label": "Item out of stock",
            "reply": "Unfortunately, this item is currently out of stock. We'll notify you when it's available again.",
            "close_ticket": False
        },
        "pricing_info": {
            "label": "Pricing information",
            "reply": "Here's our current pricing information: [Link to pricing page]. Let me know if you need any clarification!",
            "close_ticket": False
        },
        "technical_support": {
            "label": "Technical support",
            "reply": "I'm transferring you to our technical support team. They'll be with you shortly.",
            "close_ticket": False
        }
    }
    
    @classmethod
    def validate(cls):
        """Validate that all required configuration is present"""
        required = [
            'DISCORD_TOKEN',
            'DISCORD_CHANNEL_ID', 
            'INTERCOM_ACCESS_TOKEN',
            'INTERCOM_WEBHOOK_SECRET'
        ]
        
        missing = []
        for key in required:
            if not getattr(cls, key):
                missing.append(key)
        
        if missing:
            raise ValueError(f"Missing required configuration: {', '.join(missing)}")
        
        return True
