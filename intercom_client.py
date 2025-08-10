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
        clean_text = re.sub(r'<[^>]+>', '', html_content)
        
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
                        print(f"❌ Failed to send reply. Status: {response.status}, Error: {error_data}")
                    except:
                        print(f"❌ Failed to send reply. Status: {response.status}")
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
                    print(f"❌ Failed to get conversation parts: {response.status}")
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
        
        # Extract user messages like in the old working code
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
        """Get the full conversation thread including all messages (user and admin)"""
        print(f"🔍 Fetching conversation thread for: {conversation_id}")
        
        conversation = await self.get_conversation(conversation_id)
        if not conversation:
            print(f"❌ Could not fetch conversation: {conversation_id}")
            return None
        
        # Debug: Print conversation structure
        print(f"📋 Conversation keys: {list(conversation.keys())}")
        print(f"📋 Source keys: {list(conversation.get('source', {}).keys())}")
        
        # Get all conversation parts for the full thread
        parts = await self.get_conversation_parts(conversation_id)
        print(f"📝 Found {len(parts)} conversation parts")
        
        # Debug: Print parts structure
        if parts:
            print(f"📋 First part keys: {list(parts[0].keys())}")
            print(f"📋 First part author: {parts[0].get('author', {})}")
        
        # Build the full conversation thread
        thread_messages = []
        
        # Add initial message if it exists
        initial = conversation.get("source", {})
        print(f"📋 Initial message keys: {list(initial.keys())}")
        print(f"📋 Initial author: {initial.get('author', {})}")
        print(f"📋 Initial body: {initial.get('body', 'No body')[:100]}...")
        
        if initial.get("body"):
            # Better author handling
            author = initial.get("author", {})
            author_type = author.get("type", "unknown")
            
            # Try different ways to get author name - Intercom might use different fields
            author_name = author.get("name")
            if not author_name:
                author_name = author.get("email")
            if not author_name:
                author_name = author.get("id")
            if not author_name:
                # Check if it's a lead/user with different structure
                if author_type == "lead":
                    author_name = "Lead User"
                elif author_type == "user":
                    author_name = "User"
                elif author_type == "admin":
                    author_name = "Admin"
                else:
                    author_name = f"Unknown {author_type.title()}"
            
            print(f"📋 Final author name: {author_name}")
            print(f"📋 Author type: {author_type}")
            
            body = self._clean_html(initial.get("body", ""))
            if body:
                thread_messages.append({
                    "author": f"{author_name} ({author_type})",
                    "message": body,
                    "timestamp": initial.get("created_at", "Unknown")
                })
                print(f"📤 Added initial message from {author_name} ({author_type})")
        
        # Add all conversation parts in chronological order
        for i, part in enumerate(parts):
            if part.get("body"):
                # Extract author information
                author = part.get("author", {})
                author_type = author.get("type", "unknown")
                
                # Get author name with better fallback logic
                author_name = author.get("name")
                if not author_name:
                    author_email = author.get("email")
                    if author_email:
                        author_name = author_email
                    else:
                        # Use descriptive names for different types
                        if author_type == "lead":
                            author_name = "Lead User"
                        elif author_type == "user":
                            author_name = "User"
                        elif author_type == "admin":
                            author_name = "Admin"
                        elif author_type == "bot":
                            author_name = "Bot"
                        else:
                            author_name = f"{author_type.title()} User"
                
                # Get message content
                body = part.get("body", "")
                if body:
                    # Clean HTML from the message
                    clean_body = self._clean_html(body)
                    thread_messages.append({
                        "author": f"{author_name} ({author_type})",
                        "message": clean_body,
                        "timestamp": part.get("created_at", "Unknown")
                    })
                    print(f"📤 Added part {i+1}: {author_name} ({author_type}) - {clean_body[:50]}...")
        
        print(f"📊 Total messages in thread: {len(thread_messages)}")
        
        # Format the thread for display
        if thread_messages:
            formatted_thread = []
            for msg in thread_messages:
                formatted_thread.append(f"**{msg['author']}:** {msg['message']}")
            thread_text = "\n\n".join(formatted_thread)
        else:
            thread_text = "No messages in conversation"
        
        return {
            "id": conversation.get("id"),
            "status": conversation.get("state"),
            "subject": self._clean_html(initial.get("subject", "No subject")),
            "body": thread_text,
            "user": conversation.get("user", {}),
            "created_at": conversation.get("created_at"),
            "updated_at": conversation.get("updated_at"),
            "message_count": len(thread_messages)
        }
    
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
