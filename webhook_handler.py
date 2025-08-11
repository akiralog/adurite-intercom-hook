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
import discord

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
        # Get conversation details with full thread
        conversation_data = await self.intercom_client.get_conversation_thread(conversation_id)
        if not conversation_data:
            return {"error": "Could not fetch conversation data"}
        
        # Check if conversation is fresh (no admin replies)
        if not conversation_data.get('is_fresh', True):
            return {"info": "Ticket already has admin replies, skipping"}
        
        # Create Discord embed with the full conversation thread
        embed = discord.Embed(
            title=f"🎫 New Ticket: {conversation_data.get('subject', 'No Subject')}",
            description="**Full conversation thread:**\n\n" + conversation_data.get('body', 'No message content')[:2000] + ("..." if len(conversation_data.get('body', '')) > 2000 else ""),
            color=0x00ff00,  # Green for new tickets
            timestamp=discord.utils.utcnow()
        )
        
        # Add user information
        user = conversation_data.get('user', {})
        if user:
            embed.add_field(
                name="👤 User",
                value=f"{user.get('name', 'Unknown')} ({user.get('email', 'No email')})",
                inline=True
            )
        
        # Add conversation ID
        embed.add_field(
            name="🆔 Conversation ID",
            value=conversation_data.get('id', 'Unknown'),
            inline=True
        )
        
        # Add status and message count
        embed.add_field(
            name="📊 Status",
            value=conversation_data.get('status', 'Unknown'),
            inline=True
        )
        
        embed.add_field(
            name="💬 Message Count",
            value=conversation_data.get('message_count', 0),
            inline=True
        )
        
        embed.set_footer(text="Intercom Ticket Bot")
        
        # Create view with buttons
        view = TicketView(
            str(conversation_id),
            conversation_id,
            self.intercom_client,
            self.db_manager
        )
        
        # Send to Discord
        message = await self.discord_channel.send(embed=embed, view=view)
        
        # If the conversation thread is long, send it in a separate message
        if len(conversation_data.get('body', '')) > 2000:
            await self._send_full_conversation_thread(self.discord_channel, conversation_data, conversation_id)
        
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
        
        # Get the updated conversation thread
        conversation_data = await self.intercom_client.get_conversation_thread(conversation_id)
        if not conversation_data:
            return {"error": "Could not fetch updated conversation data"}
        
        # Update the existing Discord message with the new conversation thread
        try:
            channel = self.discord_channel
            message = await channel.fetch_message(ticket_data['discord_message_id'])
            
            # Create updated embed with the full conversation thread
            updated_embed = discord.Embed(
                title=f"🎫 Updated Ticket: {conversation_data.get('subject', 'No Subject')}",
                description="**Latest conversation thread:**\n\n" + conversation_data.get('body', 'No content')[:2000] + ("..." if len(conversation_data.get('body', '')) > 2000 else ""),
                color=0xffa500,  # Orange for updated tickets
                timestamp=discord.utils.utcnow()
            )
            
            # Add user information
            user = conversation_data.get('user', {})
            if user:
                updated_embed.add_field(
                    name="👤 User",
                    value=f"{user.get('name', 'Unknown')} ({user.get('email', 'No email')})",
                    inline=True
                )
            
            # Add conversation ID
            updated_embed.add_field(
                name="🆔 Conversation ID",
                value=conversation_data.get('id', 'Unknown'),
                inline=True
            )
            
            # Add status and message count
            updated_embed.add_field(
                name="📊 Status",
                value=conversation_data.get('status', 'Unknown'),
                inline=True
            )
            
            updated_embed.add_field(
                name="💬 Message Count",
                value=conversation_data.get('message_count', 0),
                inline=True
            )
            
            updated_embed.set_footer(text="Intercom Ticket Bot - Updated")
            
            # Update the message
            await message.edit(embed=updated_embed)
            
            # Send a notification about the update
            notification_embed = discord.Embed(
                title="🔄 Ticket Updated",
                description=f"User sent a follow-up message to ticket {conversation_id}",
                color=0x0099ff,
                timestamp=discord.utils.utcnow()
            )
            
            # If the conversation thread is long, send it in a separate message
            if len(conversation_data.get('body', '')) > 2000:
                await channel.send(
                    f"📝 **Full conversation thread for ticket {conversation_id}:**",
                    embed=notification_embed
                )
                
                # Send the full conversation thread
                await self._send_full_conversation_thread(channel, conversation_data)
            
        except Exception as e:
            # If we can't update the message, log the error but don't fail
            print(f"Warning: Could not update Discord message for ticket {conversation_id}: {str(e)}")
        
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

    async def _send_full_conversation_thread(self, channel, conversation_data: Dict):
        """Send the full conversation thread to a channel"""
        thread_messages = conversation_data.get('thread_messages', [])
        
        if not thread_messages:
            return
        
        # Group messages by author for better readability
        current_author = None
        current_group = []
        all_groups = []
        
        for msg in thread_messages:
            author = msg["author"]
            message = msg["message"]
            
            if current_author and current_author != author:
                if current_group:
                    all_groups.append((current_author, current_group))
                current_group = []
            
            current_author = author
            current_group.append(message)
        
        # Don't forget the last group
        if current_author and current_group:
            all_groups.append((current_author, current_group))
        
        # Send each group as a separate embed
        for i, (author, messages) in enumerate(all_groups, 1):
            # Create embed for this author's messages
            author_embed = discord.Embed(
                title=f"💬 {author}",
                description="",
                color=0x00ff00,
                timestamp=discord.utils.utcnow()
            )
            
            # Format messages for this author
            if len(messages) == 1:
                content = messages[0]
            else:
                # Multiple messages from same author
                content = "\n\n".join([f"{j}. {msg}" for j, msg in enumerate(messages, 1)])
            
            # Split content if it's too long for Discord
            if len(content) > 4000:
                # Split into multiple embeds for this author
                chunks = [content[j:j+4000] for j in range(0, len(content), 4000)]
                for j, chunk in enumerate(chunks, 1):
                    chunk_embed = discord.Embed(
                        title=f"💬 {author} (Part {j}/{len(chunks)})",
                        description=chunk,
                        color=0x00ff00,
                        timestamp=discord.utils.utcnow()
                    )
                    chunk_embed.set_footer(text="Intercom Ticket Bot")
                    await channel.send(embed=chunk_embed)
            else:
                author_embed.description = content
                author_embed.set_footer(text="Intercom Ticket Bot")
                await channel.send(embed=author_embed)
            
            # Add a small delay between embeds to avoid rate limiting
            if i < len(all_groups):
                import asyncio
                await asyncio.sleep(0.5)

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
