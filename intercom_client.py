import aiohttp
import json
import logging
import asyncio
import time
import re
from typing import Dict, List, Optional
from config import Config

logger = logging.getLogger(__name__)

class IntercomClient:
    def __init__(self):
        self.base_url = "https://api.intercom.io"
        self.headers = {
            "Authorization": f"Bearer {Config.INTERCOM_ACCESS_TOKEN}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
    
    def _clean_html(self, html_content: str) -> str:
        """Remove HTML tags and clean up the content"""
        if not html_content:
            return ""
        
        # Remove HTML tags
        import re
        clean_text = re.sub(r'<[^>]+>', '', html_content)
        
        # Decode common HTML entities
        import html
        try:
            clean_text = html.unescape(clean_text)
        except Exception:
            # Fallback to manual replacement if html.unescape fails
            clean_text = clean_text.replace('&gt;', '>').replace('&lt;', '<').replace('&amp;', '&')
        
        # Clean up extra whitespace and newlines
        clean_text = re.sub(r'\s+', ' ', clean_text)
        clean_text = clean_text.strip()
        
        return clean_text
    
    async def get_conversation(self, conversation_id: str) -> Optional[Dict]:
        """Get conversation details from Intercom"""
        url = f"{self.base_url}/conversations/{conversation_id}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self.headers) as response:
                if response.status == 200:
                    return await response.json()
        return None
    
    async def get_open_conversations(self) -> List[Dict]:
        """Get all open conversations from Intercom"""
        url = f"{self.base_url}/conversations"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self.headers) as response:
                if response.status == 200:
                    data = await response.json()
                    all_conversations = data.get("conversations", [])
                    
                    # Filter for open conversations only
                    open_conversations = [conv for conv in all_conversations if conv.get("open")]
                    
                    # Filter for conversations that haven't been replied to by any admin
                    fresh_conversations = []
                    for conv in open_conversations:
                        stats = conv.get("statistics", {})
                        if not stats.get("time_to_admin_reply"):
                            # Skip starred tickets (developer tickets)
                            if not conv.get("starred", False):
                                fresh_conversations.append(conv)
                    
                    conversations = fresh_conversations
                    
                    # Handle pagination if needed
                    while data.get("pages", {}).get("next"):
                        next_url = data["pages"]["next"]
                        # Ensure next_url is a string and properly formatted
                        if isinstance(next_url, str):
                            if not next_url.startswith('http'):
                                next_url = f"{self.base_url}{next_url}"
                            async with session.get(next_url, headers=self.headers) as next_response:
                                if next_response.status == 200:
                                    data = await next_response.json()
                                    all_conversations = data.get("conversations", [])
                                    open_conversations = [conv for conv in all_conversations if conv.get("open")]
                                    
                                    for conv in open_conversations:
                                        stats = conv.get("statistics", {})
                                        if not stats.get("time_to_admin_reply"):
                                            # Skip starred tickets (developer tickets)
                                            if not conv.get("starred", False):
                                                fresh_conversations.append(conv)
                                else:
                                    break
                        else:
                            logger.warning(f"Invalid next_url format: {next_url} (type: {type(next_url)})")
                            break
                
                return conversations
    
    async def send_reply(self, conversation_id: str, message: str, admin_id: Optional[str] = None) -> bool:
        """Send a reply to a conversation"""
        if admin_id is None:
            admin_id = Config.INTERCOM_ADMIN_ID
        
        url = f"{self.base_url}/conversations/{conversation_id}/reply"
        
        payload = {
            "message_type": "comment",
            "type": "admin",
            "admin_id": admin_id,
            "body": message
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=self.headers, json=payload) as response:
                if response.status == 200:
                    # Log the response for debugging
                    try:
                        response_data = await response.json()
                        print(f"✅ Reply sent successfully. Response: {response_data}")
                    except:
                        print(f"✅ Reply sent successfully. Status: {response.status}")
                    return True
                else:
                    # Log error for debugging
                    try:
                        error_data = await response.text()
                        print(f"Failed to send reply. Status: {response.status}, Error: {error_data}")
                    except:
                        print(f"Failed to send reply. Status: {response.status}")
                    return False
    
    async def close_conversation(self, conversation_id: str, admin_id: Optional[str] = None) -> bool:
        """Close a conversation"""
        url = f"{self.base_url}/conversations/{conversation_id}/reply"
        
        payload = {
            "message_type": "close",
            "type": "admin"
        }
        
        if admin_id:
            payload["admin_id"] = admin_id
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=self.headers, json=payload) as response:
                return response.status == 200
    
    async def assign_conversation(self, conversation_id: str, admin_id: str) -> bool:
        """Assign a conversation to a specific admin"""
        url = f"{self.base_url}/conversations/{conversation_id}/reply"
        
        payload = {
            "message_type": "assignment",
            "type": "admin",
            "admin_id": admin_id
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=self.headers, json=payload) as response:
                return response.status == 200
    
    async def get_conversation_parts(self, conversation_id: str) -> List[Dict]:
        """Get conversation parts for a specific conversation"""
        url = f"{self.base_url}/conversations/{conversation_id}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self.headers) as response:
                if response.status == 200:
                    data = await response.json()
                    # The conversation_parts are nested under conversation_parts.conversation_parts
                    conversation_parts = data.get("conversation_parts", {}).get("conversation_parts", [])
                    return conversation_parts
                else:
                    print(f"Failed to get conversation parts: {response.status}")
                    return []
    
    async def is_conversation_fresh(self, conversation_id: str) -> bool:
        """Check if a conversation is fresh (no admin replies)"""
        parts = await self.get_conversation_parts(conversation_id)
        
        for part in parts:
            if part.get("part_type") == "comment" and part.get("author", {}).get("type") == "admin":
                return False
        
        return True
    
    async def get_conversation_summary(self, conversation_id: str) -> Optional[Dict]:
        """Get a summary of conversation details"""
        conversation = await self.get_conversation(conversation_id)
        if not conversation:
            return None
        
        user_messages = []
        
        # Initial message from source
        initial = conversation.get("source", {})
        if initial.get("author", {}).get("type") == "user":
            body = initial.get("body", "")
            if body:
                user_messages.append(self._clean_html(body))
        
        # Follow-up messages from conversation parts
        parts = conversation.get("conversation_parts", {}).get("conversation_parts", [])
        for part in parts:
            if part.get("author", {}).get("type") == "user":
                body = part.get("body", "")
                if body:
                    user_messages.append(self._clean_html(body))
        
        # Combine all messages for display
        combined_messages = "\n\n".join(user_messages) if user_messages else "No message content"
        
        # Extract relevant information
        return {
            "id": conversation.get("id"),
            "status": conversation.get("state"),
            "subject": self._clean_html(initial.get("subject", "No subject")),
            "body": combined_messages,
            "user": conversation.get("user", {}),
            "created_at": conversation.get("created_at"),
            "updated_at": conversation.get("updated_at"),
            "is_fresh": await self.is_conversation_fresh(conversation_id)
        }
    
    async def get_conversation_thread(self, conversation_id: str) -> Optional[Dict]:
        """Get the full conversation thread including all messages (user and admin) in proper chronological order"""
        print(f"Fetching conversation thread for: {conversation_id}")
        
        conversation = await self.get_conversation(conversation_id)
        if not conversation:
            print(f"Could not fetch conversation: {conversation_id}")
            return None
        
        # Get all conversation parts for the full thread
        parts = await self.get_conversation_parts(conversation_id)
        print(f"Found {len(parts)} conversation parts")
        
        # Build the full conversation thread
        thread_messages = []
        
        # Add initial message if it exists
        initial = conversation.get("source", {})
        if initial.get("body") or initial.get("attachments"):
            # Debug: Log the structure of the initial message
            print(f"Debug: Initial message structure: {initial.keys()}")
            if initial.get("attachments"):
                print(f"Debug: Initial message has attachments: {initial['attachments']}")
            
            author = initial.get("author", {})
            author_type = author.get("type", "unknown")
            
            author_name = self._get_author_display_name(author, author_type)
            message_content = self._extract_message_content(initial)
            
            # Add initial message if it has content OR attachments
            if message_content:
                timestamp = initial.get("created_at", "Unknown")
                timestamp_sort = self._parse_timestamp(timestamp)
                print(f"Initial message timestamp: '{timestamp}' (type: {type(timestamp)}) -> sort value: {timestamp_sort}")
                
                thread_messages.append({
                    "author": author_name,
                    "author_type": author_type,
                    "message": message_content,
                    "timestamp": timestamp,
                    "timestamp_sort": timestamp_sort,
                    "is_initial": True,
                    "part_type": initial.get("part_type", "initial"),
                    "attachments": initial.get("attachments", [])
                })
                print(f"Added initial message from {author_name}")
            else:
                print(f"Skipping initial message from {author_name} - no content or attachments to display")
        
        # Add all conversation parts
        for i, part in enumerate(parts):
            # Debug: Log the structure of this part
            print(f"Debug: Part {i+1} structure: {part.keys()}")
            if part.get("attachments"):
                print(f"Debug: Part {i+1} has attachments: {part['attachments']}")
            
            author = part.get("author", {})
            author_type = author.get("type", "unknown")
            author_name = self._get_author_display_name(author, author_type)
            
            # Handle different types of message content
            message_content = self._extract_message_content(part)
            
            # Add message if it has content OR attachments (don't skip attachment-only messages)
            if message_content:
                timestamp = part.get("created_at", "Unknown")
                timestamp_sort = self._parse_timestamp(timestamp)
                print(f"Part {i+1} timestamp: '{timestamp}' (type: {type(timestamp)}) -> sort value: {timestamp_sort}")
                
                thread_messages.append({
                    "author": author_name,
                    "author_type": author_type,
                    "message": message_content,
                    "timestamp": timestamp,
                    "timestamp_sort": timestamp_sort,
                    "is_initial": False,
                    "part_type": part.get("part_type", "unknown"),
                    "attachments": part.get("attachments", [])
                })
                print(f"Added part {i+1}: {author_name} - {message_content[:50] if message_content else '[Media content]'}...")
            else:
                print(f"Skipping part {i+1} from {author_name} - no content or attachments to display")
        
        # Sort messages by timestamp to ensure proper chronological order
        try:
            thread_messages.sort(key=lambda x: x.get("timestamp_sort", 0))
            print(f"Successfully sorted {len(thread_messages)} messages by timestamp")
        except Exception as e:
            print(f"Warning: Failed to sort messages by timestamp: {str(e)}")
            print("Messages will be displayed in original order")
            # Log timestamp details for debugging
            for i, msg in enumerate(thread_messages):
                print(f"  Message {i+1}: timestamp='{msg.get('timestamp')}' (type: {type(msg.get('timestamp'))}), sort_value={msg.get('timestamp_sort')}")
        
        print(f"Total messages in thread: {len(thread_messages)}")
        
        # Format the thread for display with better conversation flow
        if thread_messages:
            formatted_thread = self._format_conversation_thread(thread_messages)
        else:
            formatted_thread = "No messages in conversation"
        
        return {
            "id": conversation.get("id"),
            "status": conversation.get("state"),
            "subject": self._clean_html(initial.get("subject", "No subject")),
            "body": formatted_thread,
            "user": conversation.get("user", {}),
            "created_at": conversation.get("created_at"),
            "updated_at": conversation.get("updated_at"),
            "message_count": len(thread_messages),
            "thread_messages": thread_messages  # Include raw messages for advanced formatting
        }
    
    def _get_author_display_name(self, author: Dict, author_type: str) -> str:
        """Get a consistent display name for an author"""
        author_name = author.get("name")
        if not author_name:
            author_name = author.get("email")
        if not author_name:
            author_name = author.get("id")
        if not author_name:
            # Provide user-friendly names for different author types
            if author_type == "lead":
                author_name = "Lead User"
            elif author_type == "user":
                author_name = "User"
            elif author_type == "admin":
                author_name = "Admin"
            elif author_type == "bot":
                author_name = "Fin (AI Bot)"  # Special name for Intercom's AI bot
            else:
                author_name = f"{author_type.title()} User"
        
        return author_name
    
    def _format_conversation_thread(self, messages: List[Dict]) -> str:
        """Format conversation thread with better flow and readability"""
        if not messages:
            return "No messages in conversation"
        
        formatted_parts = []
        current_author = None
        current_messages = []
        
        for msg in messages:
            author = msg["author"]
            message = msg["message"]
            
            # If this is a new author, flush the previous group
            if current_author and current_author != author:
                formatted_parts.append(self._format_message_group(current_author, current_messages))
                current_messages = []
            
            current_author = author
            current_messages.append(message)
        
        # Don't forget the last group
        if current_author and current_messages:
            formatted_parts.append(self._format_message_group(current_author, current_messages))
        
        return "\n\n---\n\n".join(formatted_parts)
    
    def _format_message_group(self, author: str, messages: List[str]) -> str:
        """Format a group of messages from the same author"""
        if len(messages) == 1:
            return f"**{author}:** {messages[0]}"
        else:
            # Multiple messages from same author - group them together
            formatted_messages = []
            for i, msg in enumerate(messages, 1):
                if len(messages) > 1:
                    formatted_messages.append(f"{i}. {msg}")
                else:
                    formatted_messages.append(msg)
            
            return f"**{author}:**\n" + "\n".join(formatted_messages)
    
    async def process_conversations_in_batches(self, conversation_ids: List[str], batch_size: int = None) -> List[Dict]:
        """Process multiple conversations in batches to avoid overwhelming the API"""
        if batch_size is None:
            batch_size = Config.RATE_LIMIT_BATCH_SIZE
            
        results = []
        
        for i in range(0, len(conversation_ids), batch_size):
            batch = conversation_ids[i:i + batch_size]
            logger.info(f"Processing batch {i//batch_size + 1}/{(len(conversation_ids) + batch_size - 1)//batch_size} ({len(batch)} conversations)")
            
            # Process batch concurrently
            tasks = [self.get_conversation_summary(conv_id) for conv_id in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Filter out errors and add successful results
            for result in batch_results:
                if isinstance(result, Exception):
                    logger.warning(f"Error processing conversation: {result}")
                elif result:
                    results.append(result)
            
            # Add delay between batches to be extra safe with rate limits
            if i + batch_size < len(conversation_ids):
                await asyncio.sleep(Config.RATE_LIMIT_BATCH_DELAY)
        
        return results

    def _parse_timestamp(self, timestamp) -> int:
        """Parse timestamp into a sortable integer value"""
        if not timestamp:
            return 0
        
        # If it's already an integer, return it
        if isinstance(timestamp, int):
            return timestamp
        
        # If it's a string, try to parse it
        if isinstance(timestamp, str):
            try:
                # Try to parse ISO format timestamps
                import datetime
                if 'T' in timestamp and ('Z' in timestamp or '+' in timestamp):
                    # ISO format: "2024-01-01T10:00:00Z" or "2024-01-01T10:00:00+00:00"
                    dt = datetime.datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    return int(dt.timestamp())
                elif timestamp.isdigit():
                    # Unix timestamp as string
                    return int(timestamp)
                else:
                    # Try to parse other formats
                    dt = datetime.datetime.fromisoformat(timestamp)
                    return int(dt.timestamp())
            except (ValueError, TypeError) as e:
                # If parsing fails, return 0 (will sort to the beginning)
                print(f"Warning: Could not parse timestamp '{timestamp}' (error: {str(e)}), using 0")
                return 0
        
        # For any other type, return 0
        print(f"Warning: Unknown timestamp type '{type(timestamp)}' with value '{timestamp}', using 0")
        return 0

    def _extract_message_content(self, part: Dict) -> str:
        """Extract message content from a conversation part, handling different content types"""
        print(f"Debug: Extracting content from part: {part.get('part_type', 'unknown')} - body: '{part.get('body', '')}' - attachments: {len(part.get('attachments', []))}")
        
        # Skip system messages that don't have user-visible content
        part_type = part.get("part_type", "")
        system_message_types = [
            "language_detection_details",
            "conversation_attribute_updated_by_admin", 
            "conversation_attribute_updated_by_user",
            "conversation_attribute_updated_by_bot",
            "conversation_attribute_updated_by_team",
            "conversation_attribute_updated_by_workspace",
            "conversation_attribute_updated_by_system"
        ]
        
        if part_type in system_message_types:
            print(f"Debug: Skipping system message type: {part_type}")
            return None  # This will cause the message to be filtered out
        
        # Check for text body first (this will now handle HTML with images)
        body = part.get("body", "")
        if body and body.strip() and body.strip() != "None":
            # Check if this contains images first
            if '<img' in body:
                print(f"Debug: Found HTML with images, extracting directly")
                import re
                img_pattern = r'<img[^>]+src=["\']([^"\']+)["\'][^>]*>'
                img_matches = re.findall(img_pattern, body)
                
                if img_matches:
                    image_links = []
                    for img_src in img_matches:
                        # Extract filename from URL
                        filename = img_src.split('/')[-1].split('?')[0]
                        if filename and '.' in filename:
                            clean_filename = filename.replace('_', ' ').replace('-', ' ').title()
                        else:
                            clean_filename = 'Image'
                        
                        print(f"Debug: Creating link for image: '{clean_filename}' -> '{img_src[:50]}...'")
                        # Create clickable link
                        image_links.append(f"📷 [{clean_filename}]({img_src})")
                    
                    result = " | ".join(image_links)
                    print(f"Debug: Created image links: '{result}'")
                    return result
            
            # If no images, clean the HTML normally
            clean_body = self._clean_html(body)
            print(f"Debug: Cleaned body result: '{clean_body[:100]}...'")
            return clean_body
        
        # Check for attachments (images, files, etc.)
        attachments = part.get("attachments", [])
        if attachments:
            print(f"Debug: Found {len(attachments)} attachments")
            attachment_descriptions = []
            for i, attachment in enumerate(attachments):
                print(f"Debug: Attachment {i+1}: {attachment}")
                attachment_type = attachment.get("type", "unknown")
                if attachment_type == "image":
                    # For images, show a descriptive message with URL if available
                    image_url = attachment.get("url", "")
                    image_name = attachment.get("name", "Unnamed image")
                    if image_url:
                        attachment_descriptions.append(f"📷 [{image_name}]({image_url})")
                    else:
                        attachment_descriptions.append(f"📷 {image_name}")
                elif attachment_type == "file":
                    # For files, show file info
                    file_name = attachment.get("name", "Unnamed file")
                    file_size = attachment.get("size", 0)
                    if file_size:
                        # Convert bytes to human readable format
                        if file_size < 1024:
                            size_str = f"{file_size} B"
                        elif file_size < 1024 * 1024:
                            size_str = f"{file_size // 1024} KB"
                        else:
                            size_str = f"{file_size // (1024 * 1024)} MB"
                        attachment_descriptions.append(f"📎 {file_name} ({size_str})")
                    else:
                        attachment_descriptions.append(f"📎 {file_name}")
                else:
                    # For other attachment types
                    attachment_descriptions.append(f"📎 {attachment.get('name', 'Attachment')}")
            
            if attachment_descriptions:
                result = " | ".join(attachment_descriptions)
                print(f"Debug: Using attachment content: '{result}'")
                return result
        
        # Check for other content types
        if part_type == "comment":
            # Comment without body might be an image or other media
            if attachments:
                return "[Media content]"
            else:
                return "[Comment]"
        elif part_type == "assignment":
            return "[Conversation assigned]"
        elif part_type == "close":
            return "[Conversation closed]"
        elif part_type == "open":
            return "[Conversation opened]"
        
        # If we can't determine content, return None to filter it out
        print(f"Debug: No meaningful content found, filtering out this message")
        return None
