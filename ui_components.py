import discord
from discord.ext import commands
from typing import Dict, Optional
from config import Config
from intercom_client import IntercomClient
from database import DatabaseManager

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
        
        # Add close ticket button
        close_button = discord.ui.Button(
            label="Close Ticket",
            custom_id=f"close_ticket_{ticket_id}",
            style=discord.ButtonStyle.danger
        )
        close_button.callback = self.close_ticket_callback
        self.add_item(close_button)
    
    async def quick_reply_callback(self, interaction: discord.Interaction):
        """Handle quick reply button clicks"""
        button_id = interaction.data["custom_id"]
        action = button_id.split("_")[2]  # Get the action (no_robux, out_of_stock, etc.)
        
        if action in Config.QUICK_REPLIES:
            config = Config.QUICK_REPLIES[action]
            
            # Send reply to Intercom
            success = await self.intercom_client.send_reply(
                self.conversation_id, 
                config["reply"]
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
                
                # If this reply should close the ticket
                if config.get("close_ticket", False):
                    await self.close_ticket(interaction)
            else:
                await interaction.response.send_message(
                    "❌ Failed to send reply to Intercom. Please try again.",
                    ephemeral=True
                )
    
    async def close_ticket_callback(self, interaction: discord.Interaction):
        """Handle close ticket button click"""
        await self.close_ticket(interaction)
    
    async def close_ticket(self, interaction: discord.Interaction):
        """Close the ticket and clean up"""
        # Close conversation in Intercom
        success = await self.intercom_client.close_conversation(self.conversation_id)
        
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
        success = await self.intercom_client.close_conversation(self.conversation_id)
        
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
