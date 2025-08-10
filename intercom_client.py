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
        url = f"{self.base_url}/conversations/{conversation_id}/reply"
        
        payload = {
            "message_type": "comment",
            "type": "admin",
            "body": message
        }
        
        if admin_id:
            payload["admin_id"] = admin_id
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=self.headers, json=payload) as response:
                return response.status == 200
    
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
        """Get all parts (messages) of a conversation"""
        url = f"{self.base_url}/conversations/{conversation_id}/parts"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self.headers) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("conversation_parts", [])
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
