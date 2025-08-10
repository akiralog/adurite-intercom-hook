import aiohttp
from aiohttp import web
import json
import hmac
import hashlib
from typing import Dict, Optional
from config import Config
from database import DatabaseManager
from intercom_client import IntercomClient
from ui_components import TicketEmbed, TicketView

class WebhookHandler:
    """Handles Intercom webhook notifications"""
    
    def __init__(self, db_manager: DatabaseManager, intercom_client: IntercomClient, 
                 discord_channel, bot):
        self.db_manager = db_manager
        self.intercom_client = intercom_client
        self.discord_channel = discord_channel
        self.bot = bot
    
    def verify_webhook_signature(self, payload: str, signature: str) -> bool:
        """Verify that the webhook came from Intercom"""
        if not Config.INTERCOM_WEBHOOK_SECRET:
            return True  # Skip verification if no secret configured
        
        expected_signature = hmac.new(
            Config.INTERCOM_WEBHOOK_SECRET.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)
    
    async def process_webhook(self, data: Dict) -> Dict:
        """Process webhook data and determine action"""
        topic = data.get('topic')
        conversation_id = data.get('data', {}).get('id')
        
        if not topic or not conversation_id:
            return {"error": "Invalid webhook data"}
        
        try:
            if topic == 'conversation.user.created':
                return await self.handle_new_ticket(conversation_id)
            elif topic == 'conversation.user.replied':
                return await self.handle_user_reply(conversation_id)
            elif topic == 'conversation.admin.replied':
                return await self.handle_admin_reply(conversation_id)
            elif topic == 'conversation.admin.closed':
                return await self.handle_ticket_closed(conversation_id)
            elif topic == 'conversation.admin.assigned':
                return await self.handle_ticket_assigned(conversation_id)
            else:
                return {"info": f"Unhandled topic: {topic}"}
        
        except Exception as e:
            return {"error": f"Error processing webhook: {str(e)}"}
    
    async def handle_new_ticket(self, conversation_id: str) -> Dict:
        """Handle a new ticket creation"""
        # Get conversation details
        conversation_data = await self.intercom_client.get_conversation_summary(conversation_id)
        if not conversation_data:
            return {"error": "Could not fetch conversation data"}
        
        # Check if conversation is fresh (no admin replies)
        if not conversation_data.get('is_fresh', True):
            return {"info": "Ticket already has admin replies, skipping"}
        
        # Create Discord embed
        embed = TicketEmbed.create_ticket_embed(conversation_data)
        
        # Create view with buttons
        view = TicketView(
            str(conversation_id),
            conversation_id,
            self.intercom_client,
            self.db_manager
        )
        
        # Send to Discord
        message = await self.discord_channel.send(embed=embed, view=view)
        
        # Store in database
        await self.db_manager.add_ticket(
            str(conversation_id),
            message.id,
            'open',
            conversation_id
        )
        
        return {"success": f"New ticket posted to Discord: {conversation_id}"}
    
    async def handle_user_reply(self, conversation_id: str) -> Dict:
        """Handle when a user replies to a ticket"""
        # Check if we have this ticket in our database
        ticket_data = await self.db_manager.get_ticket_by_conversation(conversation_id)
        if not ticket_data:
            return {"info": "Ticket not found in database"}
        
        # Remove the Discord message since it's no longer "fresh"
        try:
            channel = self.discord_channel
            message = await channel.fetch_message(ticket_data['discord_message_id'])
            await message.delete()
        except:
            pass  # Message might already be deleted
        
        # Update database
        await self.db_manager.update_ticket_status(ticket_data['id'], 'user_replied')
        
        return {"success": f"User reply handled for ticket: {conversation_id}"}
    
    async def handle_admin_reply(self, conversation_id: str) -> Dict:
        """Handle when an admin replies to a ticket"""
        # Check if we have this ticket in our database
        ticket_data = await self.db_manager.get_ticket_by_conversation(conversation_id)
        if not ticket_data:
            return {"info": "Ticket not found in database"}
        
        # Remove the Discord message since it's no longer "fresh"
        try:
            channel = self.discord_channel
            message = await channel.fetch_message(ticket_data['discord_message_id'])
            await message.delete()
        except:
            pass  # Message might already be deleted
        
        # Update database
        await self.db_manager.update_ticket_status(ticket_data['id'], 'admin_replied')
        
        return {"success": f"Admin reply handled for ticket: {conversation_id}"}
    
    async def handle_ticket_closed(self, conversation_id: str) -> Dict:
        """Handle when a ticket is closed"""
        # Check if we have this ticket in our database
        ticket_data = await self.db_manager.get_ticket_by_conversation(conversation_id)
        if not ticket_data:
            return {"info": "Ticket not found in database"}
        
        # Remove the Discord message
        try:
            channel = self.discord_channel
            message = await channel.fetch_message(ticket_data['discord_message_id'])
            await message.delete()
        except:
            pass  # Message might already be deleted
        
        # Update database
        await self.db_manager.update_ticket_status(ticket_data['id'], 'closed')
        
        return {"success": f"Ticket closure handled: {conversation_id}"}
    
    async def handle_ticket_assigned(self, conversation_id: str) -> Dict:
        """Handle when a ticket is assigned to an admin"""
        # Check if we have this ticket in our database
        ticket_data = await self.db_manager.get_ticket_by_conversation(conversation_id)
        if not ticket_data:
            return {"info": "Ticket not found in database"}
        
        # Update database
        await self.db_manager.update_ticket_status(ticket_data['id'], 'assigned')
        
        return {"success": f"Ticket assignment handled: {conversation_id}"}

async def webhook_endpoint(request: web.Request, handler: WebhookHandler) -> web.Response:
    """HTTP endpoint for receiving webhooks"""
    try:
        # Get the request body
        body = await request.text()
        
        # Verify signature if secret is configured
        signature = request.headers.get('X-Hub-Signature-256', '')
        if signature and not handler.verify_webhook_signature(body, signature):
            return web.Response(status=401, text="Invalid signature")
        
        # Parse JSON data
        data = json.loads(body)
        
        # Process the webhook
        result = await handler.process_webhook(data)
        
        # Return success response
        return web.json_response(result)
    
    except json.JSONDecodeError:
        return web.Response(status=400, text="Invalid JSON")
    except Exception as e:
        return web.Response(status=500, text=f"Internal error: {str(e)}")

async def start_webhook_server(handler: WebhookHandler, host: str = 'localhost', port: int = 8000):
    """Start the webhook server"""
    app = web.Application()
    app.router.add_post('/webhook', lambda req: webhook_endpoint(req, handler))
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    site = web.TCPSite(runner, host, port)
    await site.start()
    
    print(f"Webhook server started on http://{host}:{port}")
    return runner
