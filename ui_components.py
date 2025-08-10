import discord
import asyncio
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
            print(f"DEBUG: show_conversation_thread called for conversation {self.conversation_id}")
            # Add a small delay to ensure Intercom has processed our reply
            import asyncio
            await asyncio.sleep(2)
            print(f"DEBUG: Delay completed, fetching conversation thread...")
            
            # Get updated conversation thread data
            conversation_data = await self.intercom_client.get_conversation_thread(self.conversation_id)
            print(f"DEBUG: Conversation thread data received: {conversation_data is not None}")
            
            if conversation_data:
                print(f"DEBUG: Creating thread embed...")
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
                print(f"DEBUG: Sending thread update via followup...")
                await interaction.followup.send(
                    "🔄 **Conversation thread updated:**",
                    embed=thread_embed
                )
                print(f"DEBUG: Thread update sent successfully")
            else:
                print(f"DEBUG: No conversation data received")
        except Exception as e:
            print(f"ERROR in show_conversation_thread: {str(e)}")
            import traceback
            traceback.print_exc()
            try:
                await interaction.followup.send(
                    f"⚠️ Sent reply but couldn't fetch updated thread: {str(e)}",
                    ephemeral=True
                )
            except Exception as followup_error:
                print(f"ERROR: Could not send followup error message: {followup_error}")

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
        try:
            print(f"DEBUG: quick_reply_callback called for interaction {interaction.id}")
            button_id = interaction.data["custom_id"]
            # Parse the button ID: "quick_reply_{key}_{ticket_id}"
            # We need to extract the key which may contain underscores
            parts = button_id.split("_")
            if len(parts) >= 4:  # quick_reply_{key}_{ticket_id}
                # Reconstruct the key by joining all parts between "reply" and the ticket_id
                key_parts = parts[2:-1]  # Everything between "reply" and ticket_id
                action = "_".join(key_parts)
            else:
                action = parts[2] if len(parts) > 2 else "unknown"
            print(f"DEBUG: Action extracted: {action}")
            
            if action in Config.QUICK_REPLIES:
                config = Config.QUICK_REPLIES[action]
                print(f"DEBUG: Config found: {config}")
                
                # Send reply to Intercom
                print(f"DEBUG: Sending reply to Intercom...")
                success = await self.intercom_client.send_reply(
                    self.conversation_id, 
                    config["reply"],
                    Config.INTERCOM_ADMIN_ID
                )
                print(f"DEBUG: Reply sent to Intercom: {success}")
                
                if success:
                    # Update ticket status
                    print(f"DEBUG: Updating ticket status...")
                    await self.db_manager.update_ticket_status(self.ticket_id, "replied")
                    
                    # Create reply embed
                    embed = TicketEmbed.create_reply_embed(config["reply"], self.conversation_id)
                    
                    # If this reply should close the ticket, handle it differently
                    if config.get("close_ticket", False):
                        print(f"DEBUG: Ticket should be closed, handling closure...")
                        # Close conversation in Intercom
                        close_success = await self.intercom_client.close_conversation(self.conversation_id, Config.INTERCOM_ADMIN_ID)
                        print(f"DEBUG: Conversation closed in Intercom: {close_success}")
                        
                        if close_success:
                            # Update database
                            await self.db_manager.update_ticket_status(self.ticket_id, "closed")
                            
                            # Send confirmation with closure info
                            print(f"DEBUG: Sending confirmation message...")
                            await interaction.response.send_message(
                                f"✅ Reply sent and ticket closed successfully!\n\n**Reply:** {config['reply']}",
                                embed=embed,
                                ephemeral=True
                            )
                            
                            # Remove the Discord message after a short delay
                            try:
                                await asyncio.sleep(1)
                                await interaction.message.delete()
                                print(f"DEBUG: Discord message deleted")
                            except discord.NotFound:
                                print(f"DEBUG: Discord message already deleted")
                                pass  # Message already deleted
                        else:
                            await interaction.response.send_message(
                                f"✅ Reply sent but failed to close ticket.\n\n**Reply:** {config['reply']}",
                                embed=embed,
                                ephemeral=True
                            )
                    else:
                        # Send confirmation for regular reply
                        print(f"DEBUG: Sending regular reply confirmation...")
                        await interaction.response.send_message(
                            f"✅ Reply sent successfully!\n\n**Reply:** {config['reply']}",
                            embed=embed,
                            ephemeral=True
                        )
                    
                    # Show updated conversation thread
                    print(f"DEBUG: Showing updated conversation thread...")
                    await self.show_conversation_thread(interaction)
                else:
                    print(f"DEBUG: Failed to send reply to Intercom")
                    await interaction.response.send_message(
                        "❌ Failed to send reply to Intercom. Please try again.",
                        ephemeral=True
                    )
            else:
                print(f"DEBUG: Action {action} not found in QUICK_REPLIES")
        except Exception as e:
            print(f"ERROR in quick_reply_callback: {str(e)}")
            import traceback
            traceback.print_exc()
            try:
                await interaction.response.send_message(
                    f"❌ An error occurred: {str(e)}",
                    ephemeral=True
                )
            except:
                print(f"ERROR: Could not send error message to user")
    
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
        try:
            print(f"DEBUG: close_ticket called for conversation {self.conversation_id}")
            # Close conversation in Intercom
            print(f"DEBUG: Closing conversation in Intercom...")
            success = await self.intercom_client.close_conversation(self.conversation_id, Config.INTERCOM_ADMIN_ID)
            print(f"DEBUG: Conversation closed in Intercom: {success}")
            
            if success:
                # Update database
                print(f"DEBUG: Updating database...")
                await self.db_manager.update_ticket_status(self.ticket_id, "closed")
                
                # Remove the Discord message
                try:
                    print(f"DEBUG: Deleting Discord message...")
                    await interaction.message.delete()
                    print(f"DEBUG: Discord message deleted successfully")
                except discord.NotFound:
                    print(f"DEBUG: Discord message already deleted")
                    pass  # Message already deleted
                
                print(f"DEBUG: Sending success response...")
                await interaction.response.send_message(
                    "✅ Ticket closed successfully!",
                    ephemeral=True
                )
                print(f"DEBUG: Success response sent")
            else:
                print(f"DEBUG: Failed to close ticket in Intercom")
                await interaction.response.send_message(
                    "❌ Failed to close ticket in Intercom. Please try again.",
                    ephemeral=True
                )
        except Exception as e:
            print(f"ERROR in close_ticket: {str(e)}")
            import traceback
            traceback.print_exc()
            try:
                await interaction.response.send_message(
                    f"❌ An error occurred while closing ticket: {str(e)}",
                    ephemeral=True
                )
            except Exception as response_error:
                print(f"ERROR: Could not send error response: {response_error}")

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
        try:
            print(f"DEBUG: confirm_close called for conversation {self.conversation_id}")
            print(f"DEBUG: Closing conversation in Intercom...")
            success = await self.intercom_client.close_conversation(self.conversation_id, Config.INTERCOM_ADMIN_ID)
            print(f"DEBUG: Conversation closed in Intercom: {success}")
            
            if success:
                print(f"DEBUG: Updating database...")
                await self.db_manager.update_ticket_status(self.ticket_id, "closed")
                
                # Remove the Discord message
                try:
                    print(f"DEBUG: Deleting Discord message...")
                    await interaction.message.delete()
                    print(f"DEBUG: Discord message deleted successfully")
                except discord.NotFound:
                    print(f"DEBUG: Discord message already deleted")
                    pass
                
                print(f"DEBUG: Sending success response...")
                await interaction.response.send_message(
                    "✅ Ticket closed successfully!",
                    ephemeral=True
                )
                print(f"DEBUG: Success response sent")
            else:
                print(f"DEBUG: Failed to close ticket in Intercom")
                await interaction.response.send_message(
                    "❌ Failed to close ticket. Please try again.",
                    ephemeral=True
                )
        except Exception as e:
            print(f"ERROR in confirm_close: {str(e)}")
            import traceback
            traceback.print_exc()
            try:
                await interaction.response.send_message(
                    f"❌ An error occurred while closing ticket: {str(e)}",
                    ephemeral=True
                )
            except Exception as response_error:
                print(f"ERROR: Could not send error response: {response_error}")
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel ticket closure"""
        try:
            print(f"DEBUG: cancel_close called for conversation {self.conversation_id}")
            print(f"DEBUG: Sending cancellation message...")
            await interaction.response.send_message(
                "❌ Ticket closure cancelled.",
                ephemeral=True
            )
            print(f"DEBUG: Cancellation message sent")
            
            # Remove the confirmation message
            try:
                print(f"DEBUG: Deleting confirmation message...")
                await interaction.message.delete()
                print(f"DEBUG: Confirmation message deleted successfully")
            except discord.NotFound:
                print(f"DEBUG: Confirmation message already deleted")
                pass
        except Exception as e:
            print(f"ERROR in cancel_close: {str(e)}")
            import traceback
            traceback.print_exc()
            try:
                await interaction.response.send_message(
                    f"❌ An error occurred while cancelling: {str(e)}",
                    ephemeral=True
                )
            except Exception as response_error:
                print(f"ERROR: Could not send error response: {response_error}")
