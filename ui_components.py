import discord
from discord.ext import commands
from typing import Dict, Optional
from config import Config
from intercom_client import IntercomClient
from database import DatabaseManager

class CustomReplyModal(discord.ui.Modal, title="Custom Reply"):
    """Modal for custom reply input"""
    
    def __init__(self, conversation_id: str, intercom_client: IntercomClient, db_manager: DatabaseManager, ticket_id: str):
        super().__init__()
        self.conversation_id = conversation_id
        self.intercom_client = intercom_client
        self.db_manager = db_manager
        self.ticket_id = ticket_id
        
        self.reply_text = discord.ui.TextInput(
            label="Your Reply",
            placeholder="Type your reply message here...",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=1000
        )
        self.add_item(self.reply_text)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal submission"""
        reply_text = self.reply_text.value
        
        # Send reply to Intercom
        success = await self.intercom_client.send_reply(
            self.conversation_id, 
            reply_text,
            Config.INTERCOM_ADMIN_ID
        )
        
        if success:
            # Update ticket status
            await self.db_manager.update_ticket_status(self.ticket_id, "replied")
            
            # Create reply embed
            embed = TicketEmbed.create_reply_embed(reply_text, self.conversation_id)
            
            # Send confirmation
            await interaction.response.send_message(
                f"✅ Custom reply sent successfully!\n\n**Reply:** {reply_text}",
                embed=embed,
                ephemeral=True
            )
            
            # Show updated conversation thread
            await self.show_conversation_thread(interaction)
        else:
            await interaction.response.send_message(
                "❌ Failed to send reply to Intercom. Please try again.",
                ephemeral=True
            )
    
    async def show_conversation_thread(self, interaction: discord.Interaction):
        """Show the updated conversation thread"""
        try:
            # Add a small delay to ensure Intercom has processed our reply
            import asyncio
            await asyncio.sleep(2)
            
            # Get updated conversation thread data
            conversation_data = await self.intercom_client.get_conversation_thread(self.conversation_id)
            if conversation_data:
                # Create thread embed
                thread_embed = discord.Embed(
                    title="📝 Conversation Thread Updated",
                    description="Latest conversation status:",
                    color=0x0099ff,
                    timestamp=discord.utils.utcnow()
                )
                
                thread_embed.add_field(
                    name="🆔 Conversation ID",
                    value=self.conversation_id,
                    inline=True
                )
                
                thread_embed.add_field(
                    name="📊 Status",
                    value=conversation_data.get('status', 'Unknown'),
                    inline=True
                )
                
                thread_embed.add_field(
                    name="💬 Message Count",
                    value=conversation_data.get('message_count', 0),
                    inline=True
                )
                
                # Add the full conversation thread
                body = conversation_data.get('body', 'No content')
                if len(body) > 1024:
                    body = body[:1021] + "..."
                
                thread_embed.add_field(
                    name="💬 Full Conversation Thread",
                    value=body,
                    inline=False
                )
                
                thread_embed.set_footer(text="Intercom Ticket Bot")
                
                # Send thread update (not ephemeral so others can see)
                await interaction.followup.send(
                    "🔄 **Conversation thread updated:**",
                    embed=thread_embed
                )
        except Exception as e:
            await interaction.followup.send(
                f"⚠️ Sent reply but couldn't fetch updated thread: {str(e)}",
                ephemeral=True
            )

class TicketEmbed:
    """Creates Discord embeds for tickets"""
    
    @staticmethod
    def create_ticket_embed(conversation_data: Dict) -> discord.Embed:
        """Create an embed for a ticket"""
        embed = discord.Embed(
            title=f"🎫 New Ticket: {conversation_data.get('subject', 'No Subject')}",
            description=conversation_data.get('body', 'No message content'),
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
        
        # Add status
        embed.add_field(
            name="📊 Status",
            value=conversation_data.get('status', 'Unknown'),
            inline=True
        )
        
        embed.set_footer(text="Intercom Ticket Bot")
        return embed
    
    @staticmethod
    def create_reply_embed(reply_text: str, conversation_id: str) -> discord.Embed:
        """Create an embed for a reply"""
        embed = discord.Embed(
            title="💬 Reply Sent",
            description=reply_text,
            color=0x0099ff,  # Blue for replies
            timestamp=discord.utils.utcnow()
        )
        
        embed.add_field(
            name="🆔 Conversation ID",
            value=conversation_id,
            inline=False
        )
        
        embed.set_footer(text="Intercom Ticket Bot")
        return embed

class TicketView(discord.ui.View):
    """Discord view with buttons for ticket actions"""
    
    def __init__(self, ticket_id: str, conversation_id: str, 
                 intercom_client: IntercomClient, db_manager: DatabaseManager):
        super().__init__(timeout=None)
        self.ticket_id = ticket_id
        self.conversation_id = conversation_id
        self.intercom_client = intercom_client
        self.db_manager = db_manager
        
        # Add quick reply buttons
        for key, config in Config.QUICK_REPLIES.items():
            button = discord.ui.Button(
                label=config["label"],
                custom_id=f"quick_reply_{key}_{ticket_id}",
                style=discord.ButtonStyle.primary
            )
            button.callback = self.quick_reply_callback
            self.add_item(button)
        
        # Add custom reply button
        custom_reply_button = discord.ui.Button(
            label="✏️ Custom Reply",
            custom_id=f"custom_reply_{ticket_id}",
            style=discord.ButtonStyle.secondary
        )
        custom_reply_button.callback = self.custom_reply_callback
        self.add_item(custom_reply_button)
        
        # Add close ticket button
        close_button = discord.ui.Button(
            label="Close Ticket",
            custom_id=f"close_ticket_{ticket_id}",
            style=discord.ButtonStyle.danger
        )
        close_button.callback = self.close_ticket_callback
        self.add_item(close_button)
    
    async def custom_reply_callback(self, interaction: discord.Interaction):
        """Handle custom reply button click"""
        # Show the custom reply modal
        modal = CustomReplyModal(
            self.conversation_id,
            self.intercom_client,
            self.db_manager,
            self.ticket_id
        )
        await interaction.response.send_modal(modal)
    
    async def quick_reply_callback(self, interaction: discord.Interaction):
        """Handle quick reply button clicks"""
        button_id = interaction.data["custom_id"]
        action = button_id.split("_")[2]  # Get the action (no_robux, out_of_stock, etc.)
        
        if action in Config.QUICK_REPLIES:
            config = Config.QUICK_REPLIES[action]
            
            # Send reply to Intercom
            success = await self.intercom_client.send_reply(
                self.conversation_id, 
                config["reply"],
                Config.INTERCOM_ADMIN_ID
            )
            
            if success:
                # Update ticket status
                await self.db_manager.update_ticket_status(self.ticket_id, "replied")
                
                # Create reply embed
                embed = TicketEmbed.create_reply_embed(config["reply"], self.conversation_id)
                
                # Send confirmation
                await interaction.response.send_message(
                    f"✅ Reply sent successfully!\n\n**Reply:** {config['reply']}",
                    embed=embed,
                    ephemeral=True
                )
                
                # Show updated conversation thread
                await self.show_conversation_thread(interaction)
                
                # If this reply should close the ticket
                if config.get("close_ticket", False):
                    await self.close_ticket(interaction)
            else:
                await interaction.response.send_message(
                    "❌ Failed to send reply to Intercom. Please try again.",
                    ephemeral=True
                )
    
    async def show_conversation_thread(self, interaction: discord.Interaction):
        """Show the updated conversation thread"""
        try:
            # Add a small delay to ensure Intercom has processed our reply
            import asyncio
            await asyncio.sleep(2)
            
            # Get updated conversation thread data
            conversation_data = await self.intercom_client.get_conversation_thread(self.conversation_id)
            if conversation_data:
                # Create thread embed
                thread_embed = discord.Embed(
                    title="📝 Conversation Thread Updated",
                    description="Latest conversation status:",
                    color=0x0099ff,
                    timestamp=discord.utils.utcnow()
                )
                
                thread_embed.add_field(
                    name="🆔 Conversation ID",
                    value=self.conversation_id,
                    inline=True
                )
                
                thread_embed.add_field(
                    name="📊 Status",
                    value=conversation_data.get('status', 'Unknown'),
                    inline=True
                )
                
                thread_embed.add_field(
                    name="💬 Message Count",
                    value=conversation_data.get('message_count', 0),
                    inline=True
                )
                
                # Add the full conversation thread
                body = conversation_data.get('body', 'No content')
                if len(body) > 1024:
                    body = body[:1021] + "..."
                
                thread_embed.add_field(
                    name="💬 Full Conversation Thread",
                    value=body,
                    inline=False
                )
                
                thread_embed.set_footer(text="Intercom Ticket Bot")
                
                # Send thread update (not ephemeral so others can see)
                await interaction.followup.send(
                    "🔄 **Conversation thread updated:**",
                    embed=thread_embed
                )
        except Exception as e:
            await interaction.followup.send(
                f"⚠️ Sent reply but couldn't fetch updated thread: {str(e)}",
                ephemeral=True
            )
    
    async def close_ticket_callback(self, interaction: discord.Interaction):
        """Handle close ticket button click"""
        await self.close_ticket(interaction)
    
    async def close_ticket(self, interaction: discord.Interaction):
        """Close the ticket and clean up"""
        # Close conversation in Intercom
        success = await self.intercom_client.close_conversation(self.conversation_id, Config.INTERCOM_ADMIN_ID)
        
        if success:
            # Update database
            await self.db_manager.update_ticket_status(self.ticket_id, "closed")
            
            # Remove the Discord message
            try:
                await interaction.message.delete()
            except discord.NotFound:
                pass  # Message already deleted
            
            await interaction.response.send_message(
                "✅ Ticket closed successfully!",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "❌ Failed to close ticket in Intercom. Please try again.",
                ephemeral=True
            )

class ConfirmationView(discord.ui.View):
    """View for confirming ticket closure"""
    
    def __init__(self, ticket_id: str, conversation_id: str, 
                 intercom_client: IntercomClient, db_manager: DatabaseManager):
        super().__init__(timeout=60)  # 60 second timeout
        self.ticket_id = ticket_id
        self.conversation_id = conversation_id
        self.intercom_client = intercom_client
        self.db_manager = db_manager
    
    @discord.ui.button(label="Yes, Close Ticket", style=discord.ButtonStyle.danger)
    async def confirm_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Confirm ticket closure"""
        success = await self.intercom_client.close_conversation(self.conversation_id, Config.INTERCOM_ADMIN_ID)
        
        if success:
            await self.db_manager.update_ticket_status(self.ticket_id, "closed")
            
            # Remove the Discord message
            try:
                await interaction.message.delete()
            except discord.NotFound:
                pass
            
            await interaction.response.send_message(
                "✅ Ticket closed successfully!",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "❌ Failed to close ticket. Please try again.",
                ephemeral=True
            )
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel ticket closure"""
        await interaction.response.send_message(
            "❌ Ticket closure cancelled.",
            ephemeral=True
        )
        
        # Remove the confirmation message
        try:
            await interaction.message.delete()
        except discord.NotFound:
            pass
