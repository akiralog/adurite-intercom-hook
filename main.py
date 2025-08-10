import discord
from discord.ext import commands
import asyncio
import logging
from config import Config
from database import DatabaseManager
from intercom_client import IntercomClient
from webhook_handler import WebhookHandler, start_webhook_server
from ui_components import TicketEmbed

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class IntercomTicketBot(commands.Bot):
    """Main bot class for handling Intercom tickets"""
    
    def __init__(self):
        intents = discord.Intents.none()
        intents.message_content = True
        intents.guilds = True
        intents.guild_messages = True
        intents.guild_reactions = True
        
        super().__init__(command_prefix='!', intents=intents)
        
        # Initialize components
        self.db_manager = DatabaseManager()
        self.intercom_client = IntercomClient()
        self.webhook_handler = None
        self.webhook_runner = None
        
        # Add commands
        self.add_commands()
    
    def add_commands(self):
        """Add bot commands"""
        
        @self.command(name='sync')
        async def sync_command(ctx):
            """Sync current open tickets with Discord"""
            if not ctx.author.guild_permissions.administrator:
                await ctx.send("❌ You need administrator permissions to use this command.")
                return
            
            await ctx.send("🔄 Syncing tickets with Intercom...")
            
            try:
                # Get open conversations
                conversations = await self.intercom_client.get_open_conversations()
                
                # Filter for fresh conversations only
                fresh_conversations = []
                for conv in conversations:
                    if await self.intercom_client.is_conversation_fresh(conv['id']):
                        fresh_conversations.append(conv)
                
                # Clear existing messages in the channel
                channel = self.get_channel(Config.DISCORD_CHANNEL_ID)
                if channel:
                    async for message in channel.history(limit=100):
                        await message.delete()
                
                # Post fresh tickets
                for conv in fresh_conversations:
                    conversation_data = await self.intercom_client.get_conversation_summary(conv['id'])
                    if conversation_data:
                        embed = TicketEmbed.create_ticket_embed(conversation_data)
                        
                        from ui_components import TicketView
                        view = TicketView(
                            str(conv['id']),
                            conv['id'],
                            self.intercom_client,
                            self.db_manager
                        )
                        
                        message = await channel.send(embed=embed, view=view)
                        
                        # Store in database
                        await self.db_manager.add_ticket(
                            str(conv['id']),
                            message.id,
                            'open',
                            conv['id']
                        )
                
                await ctx.send(f"✅ Synced {len(fresh_conversations)} fresh tickets!")
                
            except Exception as e:
                logger.error(f"Error syncing tickets: {e}")
                await ctx.send(f"❌ Error syncing tickets: {str(e)}")
        
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
                await ctx.send(f"❌ Error getting status: {str(e)}")
        
        @self.command(name='cleanup')
        async def cleanup_command(ctx):
            """Clean up old tickets from database"""
            if not ctx.author.guild_permissions.administrator:
                await ctx.send("❌ You need administrator permissions to use this command.")
                return
            
            try:
                await self.db_manager.cleanup_old_tickets(days=30)
                await ctx.send("✅ Cleaned up tickets older than 30 days!")
                
            except Exception as e:
                logger.error(f"Error cleaning up tickets: {e}")
                await ctx.send(f"❌ Error cleaning up tickets: {str(e)}")
    
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
        embed.add_field(name="Commands", value="`!sync`, `!status`, `!cleanup`", inline=False)
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
