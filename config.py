import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
    DISCORD_CHANNEL_ID = int(os.getenv('DISCORD_CHANNEL_ID', 0))
    INTERCOM_ACCESS_TOKEN = os.getenv('INTERCOM_ACCESS_TOKEN')
    INTERCOM_WEBHOOK_SECRET = os.getenv('INTERCOM_WEBHOOK_SECRET')
    INTERCOM_ADMIN_ID = os.getenv('INTERCOM_ADMIN_ID', '6673256')  # Default admin ID
    WEBHOOK_HOST = 'localhost'
    WEBHOOK_PORT = 8000
    
    # Rate Limiting Configuration (Not in use at the moment)
    RATE_LIMIT_MIN_INTERVAL = float(os.getenv('RATE_LIMIT_MIN_INTERVAL', '0.1'))  # Minimum seconds between requests (10 req/sec)
    RATE_LIMIT_BATCH_SIZE = int(os.getenv('RATE_LIMIT_BATCH_SIZE', '5'))          # Number of conversations to process in parallel
    RATE_LIMIT_BATCH_DELAY = float(os.getenv('RATE_LIMIT_BATCH_DELAY', '0.5'))    # Delay between batches in seconds
    
    QUICK_REPLIES = {
        "no_robux": {
            "label": "nofunds",
            "reply": "Sorry, but we don't sell Robux anymore.",
            "close_ticket": False
        },
        # "out_of_stock": {
        #     "label": "Item out of stock",
        #     "reply": "Unfortunately, this item is currently out of stock. We'll notify you when it's available again.",
        #     "close_ticket": False
        # },
        # "pricing_info": {
        #     "label": "Pricing information",
        #     "reply": "Here's our current pricing information: [Link to pricing page]. Let me know if you need any clarification!",
        #     "close_ticket": False
        # },
        # "technical_support": {
        #     "label": "Technical support",
        #     "reply": "I'm transferring you to our technical support team. They'll be with you shortly.",
        #     "close_ticket": False
        # }
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
