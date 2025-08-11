import discord
from discord.ext import commands
import asyncio
import logging
from config import Config
from database import DatabaseManager
from intercom_client import IntercomClient
from webhook_handler import WebhookHandler, start_webhook_server
from ui_components import TicketEmbed
from typing import Dict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class IntercomTicketBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.none()
        intents.message_content = True
        intents.guilds = True
        intents.guild_messages = True
        intents.guild_reactions = True
        
        super().__init__(command_prefix='!', intents=intents)
        
        self.db_manager = DatabaseManager()
        self.intercom_client = IntercomClient()
        self.webhook_handler = None
        self.webhook_runner = None
        self.add_commands()
    
    def add_commands(self):
        @self.command(name='sync')
        async def sync_command(ctx):
            """Sync current open tickets with Discord"""
            if not ctx.author.guild_permissions.administrator:
                await ctx.send("You need administrator permissions to use this command.")
                return
            
            await ctx.send("Syncing tickets with Intercom...")
            
            try:
                logger.info("Starting sync process...")
                
                # Get open conversations
                logger.info("Fetching open conversations from Intercom...")
                conversations = await self.intercom_client.get_open_conversations()
                logger.info(f"Found {len(conversations)} open conversations")
                
                # Filter for fresh conversations only
                logger.info("Filtering for fresh conversations...")
                fresh_conversations = []
                for i, conv in enumerate(conversations):
                    logger.info(f"🔍 Checking conversation {i+1}/{len(conversations)}: ID={conv['id']}, Type={type(conv['id'])}")
                    if await self.intercom_client.is_conversation_fresh(conv['id']):
                        fresh_conversations.append(conv)
                        logger.info(f"Conversation {conv['id']} is fresh")
                    else:
                        logger.info(f"Conversation {conv['id']} is not fresh")
                
                logger.info(f"Found {len(fresh_conversations)} fresh conversations")
                
                # Clear existing messages in the channel
                logger.info("Clearing existing messages in Discord channel...")
                channel = self.get_channel(Config.DISCORD_CHANNEL_ID)
                if channel:
                    async for message in channel.history(limit=100):
                        await message.delete()
                    logger.info("Cleared existing messages")
                
                # Post fresh tickets
                logger.info("Posting fresh tickets to Discord...")
                for i, conv in enumerate(fresh_conversations):
                    logger.info(f"Processing ticket {i+1}/{len(fresh_conversations)}: ID={conv['id']}")
                    
                    # Get the full conversation thread instead of just a summary
                    conversation_data = await self.intercom_client.get_conversation_thread(conv['id'])
                    if conversation_data:
                        logger.info(f"Got conversation thread data for {conv['id']}")
                        
                        # Create embed with the full conversation thread
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
                        
                        logger.info(f"Created embed for {conv['id']}")
                        
                        from ui_components import TicketView
                        logger.info(f"Creating TicketView for {conv['id']}...")
                        logger.info(f"   ticket_id: {str(conv['id'])} (type: {type(str(conv['id']))})")
                        logger.info(f"   conversation_id: {str(conv['id'])} (type: {type(str(conv['id']))})")
                        
                        view = TicketView(
                            str(conv['id']),  # ticket_id as string
                            str(conv['id']),  # conversation_id as string
                            self.intercom_client,
                            self.db_manager
                        )
                        logger.info(f"Created TicketView for {conv['id']}")
                        
                        message = await channel.send(embed=embed, view=view)
                        logger.info(f"Posted message to Discord for {conv['id']}")
                        
                        # If the conversation thread is long, send it in a separate message
                        if len(conversation_data.get('body', '')) > 2000:
                            await self._send_full_conversation_thread(channel, conversation_data, conv['id'])
                        
                        # Store in database
                        logger.info(f"Storing ticket {conv['id']} in database...")
                        await self.db_manager.add_ticket(
                            str(conv['id']),  # ticket_id as string
                            message.id,
                            'open',
                            str(conv['id'])  # conversation_id as string
                        )
                        logger.info(f"Stored ticket {conv['id']} in database")
                    else:
                        logger.error(f"Could not get conversation thread data for {conv['id']}")
                
                logger.info(f"Sync completed. Posted {len(fresh_conversations)} tickets to Discord.")
                if len(fresh_conversations) == 0:
                    await ctx.send(f"No fresh tickets found.")
                
            except Exception as e:
                logger.error(f"Error during sync: {str(e)}")
                await ctx.send(f"❌ Error during sync: {str(e)}")
    
    async def _send_full_conversation_thread(self, channel, conversation_data: Dict, conversation_id: str):
        """Send the full conversation thread to a channel"""
        thread_messages = conversation_data.get('thread_messages', [])
        
        if not thread_messages:
            return
        
        # Send notification
        notification_embed = discord.Embed(
            title="📝 Full Conversation Thread",
            description=f"Complete conversation thread for ticket {conversation_id}:",
            color=0x0099ff,
            timestamp=discord.utils.utcnow()
        )
        await channel.send(embed=notification_embed)
        
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
                await asyncio.sleep(0.5)
        
        @self.command(name='status')
        async def status_command(ctx):
            """Show bot status and ticket count"""
            try:
                # Get ticket counts
                all_tickets = await self.db_manager.get_all_tickets()
                open_tickets = [t for t in all_tickets if t['status'] == 'open']
                replied_tickets = [t for t in all_tickets if t['status'] in ['replied', 'admin_replied']]
                closed_tickets = [t for t in all_tickets if t['status'] == 'closed']
                
                embed = discord.Embed(
                    title="🤖 Bot Status",
                    color=0x00ff00,
                    timestamp=discord.utils.utcnow()
                )
                
                embed.add_field(name="📊 Total Tickets", value=len(all_tickets), inline=True)
                embed.add_field(name="🆕 Open Tickets", value=len(open_tickets), inline=True)
                embed.add_field(name="💬 Replied Tickets", value=len(replied_tickets), inline=True)
                embed.add_field(name="✅ Closed Tickets", value=len(closed_tickets), inline=True)
                embed.add_field(name="🌐 Webhook Status", value="🟢 Active" if self.webhook_runner else "🔴 Inactive", inline=True)
                
                embed.set_footer(text="Intercom Ticket Bot")
                
                await ctx.send(embed=embed)
                
            except Exception as e:
                logger.error(f"Error getting status: {e}")
                await ctx.send(f"Error getting status: {str(e)}")
        
        @self.command(name='cleanup')
        async def cleanup_command(ctx):
            """Clean up old tickets from database"""
            if not ctx.author.guild_permissions.administrator:
                await ctx.send("You need administrator permissions to use this command.")
                return
            
            try:
                await self.db_manager.cleanup_old_tickets(days=30)
                await ctx.send("Cleaned up tickets older than 30 days!")
                
            except Exception as e:
                logger.error(f"Error cleaning up tickets: {e}")
                await ctx.send(f"Error cleaning up tickets: {str(e)}")
        
        @self.command(name='commands')
        async def commands_command(ctx):
            """Show available commands and their usage"""
            embed = discord.Embed(
                title="🤖 Bot Commands",
                description="Here are all the available commands:",
                color=0x0099ff,
                timestamp=discord.utils.utcnow()
            )
            
            embed.add_field(
                name="🔄 `!sync`", 
                value="Sync current open tickets with Discord channel", 
                inline=False
            )
            embed.add_field(
                name="📊 `!status`", 
                value="Show bot status and ticket counts", 
                inline=False
            )
            embed.add_field(
                name="🧹 `!cleanup`", 
                value="Clean up old tickets from database (30+ days)", 
                inline=False
            )
            embed.add_field(
                name="📋 `!commands`", 
                value="Show this commands list", 
                inline=False
            )
            
            # Add ticket actions section
            embed.add_field(
                name="🎫 Ticket Actions",
                value="Each ticket has buttons for:\n• Quick replies (predefined messages)\n• ✏️ Custom Reply (type your own message)\n• Close Ticket (close the conversation)",
                inline=False
            )
            
            embed.set_footer(text="All commands require administrator permissions")
            
            await ctx.send(embed=embed)
    
    async def setup_hook(self):
        """Setup hook called when bot is starting"""
        logger.info("Setting up bot...")
        
        # Validate configuration
        try:
            Config.validate()
            logger.info("Configuration validated successfully")
        except ValueError as e:
            logger.error(f"Configuration error: {e}")
            raise
    
    async def on_ready(self):
        """Called when bot is ready"""
        logger.info(f'Bot is ready! Logged in as {self.user}')
        
        # Get the target channel
        channel = self.get_channel(Config.DISCORD_CHANNEL_ID)
        if not channel:
            logger.error(f"Could not find channel with ID: {Config.DISCORD_CHANNEL_ID}")
            return
        
        # Initialize webhook handler
        self.webhook_handler = WebhookHandler(
            self.db_manager,
            self.intercom_client,
            channel,
            self
        )
        
        # Start webhook server
        try:
            self.webhook_runner = await start_webhook_server(
                self.webhook_handler,
                Config.WEBHOOK_HOST,
                Config.WEBHOOK_PORT
            )
            logger.info("Webhook server started successfully")
        except Exception as e:
            logger.error(f"Failed to start webhook server: {e}")
        
        # Send startup message
        embed = discord.Embed(
            title="🤖 Bot Started",
            description="Intercom Ticket Bot is now online and listening for webhooks!",
            color=0x00ff00,
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="Commands", value="`!sync`, `!status`, `!cleanup`, `!commands`", inline=False)
        embed.add_field(name="Ticket Actions", value="Quick replies, custom replies, and ticket management", inline=False)
        embed.set_footer(text="Intercom Ticket Bot")
        
        await channel.send(embed=embed)
    
    async def close(self):
        """Cleanup when bot is shutting down"""
        logger.info("Shutting down bot...")
        
        if self.webhook_runner:
            await self.webhook_runner.cleanup()
            logger.info("Webhook server stopped")
        
        await super().close()

async def main():
    """Main function to run the bot"""
    try:
        # Create and run bot
        bot = IntercomTicketBot()
        await bot.start(Config.DISCORD_TOKEN)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Error running bot: {e}")
        raise

if __name__ == "__main__":
    # Run the bot
    asyncio.run(main())
