import discord
import asyncio
from discord.ext import commands
from typing import Dict, Optional, List
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
                # Create main thread embed
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
                
                # Send the main embed first
                await interaction.followup.send(
                    "🔄 **Conversation thread updated:**",
                    embed=thread_embed
                )
                
                # Now send the full conversation thread
                await self._send_conversation_thread(interaction, conversation_data)
                
        except Exception as e:
            await interaction.followup.send(
                f"⚠️ Sent reply but couldn't fetch updated thread: {str(e)}",
                ephemeral=True
            )
    
    async def _send_conversation_thread(self, interaction: discord.Interaction, conversation_data: Dict):
        """Send the full conversation thread, handling long content appropriately"""
        body = conversation_data.get('body', 'No content')
        thread_messages = conversation_data.get('thread_messages', [])
        
        if not body or body == 'No content':
            await interaction.followup.send("📭 No conversation content available", ephemeral=True)
            return
        
        # If the thread is short enough, send it in one message
        if len(body) <= 2000:
            thread_embed = discord.Embed(
                title="💬 Full Conversation Thread",
                description=body,
                color=0x00ff00,
                timestamp=discord.utils.utcnow()
            )
            thread_embed.set_footer(text="Intercom Ticket Bot")
            
            await interaction.followup.send(embed=thread_embed)
            return
        
        # For long threads, split into multiple embeds
        await self._send_split_conversation_thread(interaction, thread_messages)
    
    async def _send_split_conversation_thread(self, interaction: discord.Interaction, thread_messages: List[Dict]):
        """Send a long conversation thread split across multiple embeds"""
        if not thread_messages:
            await interaction.followup.send("📭 No conversation messages available", ephemeral=True)
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
                    await interaction.followup.send(embed=chunk_embed)
            else:
                author_embed.description = content
                author_embed.set_footer(text="Intercom Ticket Bot")
                await interaction.followup.send(embed=author_embed)
            
            # Add a small delay between embeds to avoid rate limiting
            if i < len(all_groups):
                await asyncio.sleep(0.5)

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
            button_id = interaction.data["custom_id"]
            # Parse the button ID: "quick_reply_{key}_{ticket_id}"
            parts = button_id.split("_")
            if len(parts) >= 4:  # quick_reply_{key}_{ticket_id}
                # Reconstruct the key by joining all parts between "reply" and the ticket_id
                key_parts = parts[2:-1]  # Everything between "reply" and ticket_id
                action = "_".join(key_parts)
            else:
                action = parts[2] if len(parts) > 2 else "unknown"
            
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
                    
                    # If this reply should close the ticket, handle it differently
                    if config.get("close_ticket", False):
                        # Close conversation in Intercom
                        close_success = await self.intercom_client.close_conversation(self.conversation_id, Config.INTERCOM_ADMIN_ID)
                        
                        if close_success:
                            # Update database
                            await self.db_manager.update_ticket_status(self.ticket_id, "closed")
                            
                            # Send confirmation with closure info
                            await interaction.response.send_message(
                                f"✅ Reply sent and ticket closed successfully!\n\n**Reply:** {config['reply']}",
                                embed=embed,
                                ephemeral=True
                            )
                            
                            # Remove the Discord message after a short delay
                            try:
                                await asyncio.sleep(1)
                                await interaction.message.delete()
                            except discord.NotFound:
                                pass  # Message already deleted
                        else:
                            await interaction.response.send_message(
                                f"✅ Reply sent but failed to close ticket.\n\n**Reply:** {config['reply']}",
                                embed=embed,
                                ephemeral=True
                            )
                    else:
                        # Send confirmation for regular reply
                        await interaction.response.send_message(
                            f"✅ Reply sent successfully!\n\n**Reply:** {config['reply']}",
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
            else:
                await interaction.response.send_message(
                    f"❌ Unknown quick reply action: {action}",
                    ephemeral=True
                )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ An error occurred: {str(e)}",
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
                # Create main thread embed
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
                
                # Send the main embed first
                await interaction.followup.send(
                    "🔄 **Conversation thread updated:**",
                    embed=thread_embed
                )
                
                # Now send the full conversation thread
                await self._send_conversation_thread(interaction, conversation_data)
                
        except Exception as e:
            await interaction.followup.send(
                f"⚠️ Sent reply but couldn't fetch updated thread: {str(e)}",
                ephemeral=True
            )
    
    async def _send_conversation_thread(self, interaction: discord.Interaction, conversation_data: Dict):
        """Send the full conversation thread, handling long content appropriately"""
        body = conversation_data.get('body', 'No content')
        thread_messages = conversation_data.get('thread_messages', [])
        
        if not body or body == 'No content':
            await interaction.followup.send("📭 No conversation content available", ephemeral=True)
            return
        
        # If the thread is short enough, send it in one message
        if len(body) <= 2000:
            thread_embed = discord.Embed(
                title="💬 Full Conversation Thread",
                description=body,
                color=0x00ff00,
                timestamp=discord.utils.utcnow()
            )
            thread_embed.set_footer(text="Intercom Ticket Bot")
            
            await interaction.followup.send(embed=thread_embed)
            return
        
        # For long threads, split into multiple embeds
        await self._send_split_conversation_thread(interaction, thread_messages)
    
    async def _send_split_conversation_thread(self, interaction: discord.Interaction, thread_messages: List[Dict]):
        """Send a long conversation thread split across multiple embeds"""
        if not thread_messages:
            await interaction.followup.send("📭 No conversation messages available", ephemeral=True)
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
                    await interaction.followup.send(embed=chunk_embed)
            else:
                author_embed.description = content
                author_embed.set_footer(text="Intercom Ticket Bot")
                await interaction.followup.send(embed=author_embed)
            
            # Add a small delay between embeds to avoid rate limiting
            if i < len(all_groups):
                await asyncio.sleep(0.5)
    
    async def close_ticket_callback(self, interaction: discord.Interaction):
        """Handle close ticket button click"""
        await self.close_ticket(interaction)
    
    async def close_ticket(self, interaction: discord.Interaction):
        """Close the ticket and clean up"""
        try:
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
        except Exception as e:
            await interaction.response.send_message(
                f"❌ An error occurred while closing the ticket: {str(e)}",
                ephemeral=True
            )

class ConfirmationView(discord.ui.View):
    """Confirmation view for closing tickets"""
    
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
        except Exception as e:
            await interaction.response.send_message(
                f"❌ An error occurred while closing the ticket: {str(e)}",
                ephemeral=True
            )
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel ticket closure"""
        await interaction.response.send_message(
            "❌ Ticket closure cancelled.",
            ephemeral=True
        )
