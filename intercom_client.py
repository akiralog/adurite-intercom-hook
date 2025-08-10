import aiohttp
import json
from typing import Dict, List, Optional
from config import Config

class IntercomClient:
    def __init__(self):
        self.access_token = Config.INTERCOM_ACCESS_TOKEN
        self.base_url = "https://api.intercom.io"
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
    
    async def get_conversation(self, conversation_id: str) -> Optional[Dict]:
        """Get conversation details from Intercom"""
        async with aiohttp.ClientSession() as session:
            url = f"{self.base_url}/conversations/{conversation_id}"
            async with session.get(url, headers=self.headers) as response:
                if response.status == 200:
                    return await response.json()
                return None
    
    async def get_open_conversations(self) -> List[Dict]:
        """Get all open conversations from Intercom"""
        async with aiohttp.ClientSession() as session:
            url = f"{self.base_url}/conversations"
            params = {
                "open": "true",
                "per_page": 50
            }
            
            conversations = []
            async with session.get(url, headers=self.headers, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    conversations.extend(data.get("conversations", []))
                    
                    # Handle pagination if needed
                    while data.get("pages", {}).get("next"):
                        next_url = data["pages"]["next"]
                        async with session.get(next_url, headers=self.headers) as next_response:
                            if next_response.status == 200:
                                data = await next_response.json()
                                conversations.extend(data.get("conversations", []))
                            else:
                                break
                
                return conversations
    
    async def send_reply(self, conversation_id: str, message: str, admin_id: Optional[str] = None) -> bool:
        """Send a reply to a conversation"""
        async with aiohttp.ClientSession() as session:
            url = f"{self.base_url}/conversations/{conversation_id}/reply"
            
            payload = {
                "message_type": "comment",
                "type": "admin",
                "body": message
            }
            
            if admin_id:
                payload["admin_id"] = admin_id
            
            async with session.post(url, headers=self.headers, json=payload) as response:
                return response.status == 200
    
    async def close_conversation(self, conversation_id: str, admin_id: Optional[str] = None) -> bool:
        """Close a conversation"""
        async with aiohttp.ClientSession() as session:
            url = f"{self.base_url}/conversations/{conversation_id}/reply"
            
            payload = {
                "message_type": "close",
                "type": "admin"
            }
            
            if admin_id:
                payload["admin_id"] = admin_id
            
            async with session.post(url, headers=self.headers, json=payload) as response:
                return response.status == 200
    
    async def assign_conversation(self, conversation_id: str, admin_id: str) -> bool:
        """Assign a conversation to a specific admin"""
        async with aiohttp.ClientSession() as session:
            url = f"{self.base_url}/conversations/{conversation_id}/reply"
            
            payload = {
                "message_type": "assignment",
                "type": "admin",
                "admin_id": admin_id
            }
            
            async with session.post(url, headers=self.headers, json=payload) as response:
                return response.status == 200
    
    async def get_conversation_parts(self, conversation_id: str) -> List[Dict]:
        """Get all parts (messages) of a conversation"""
        async with aiohttp.ClientSession() as session:
            url = f"{self.base_url}/conversations/{conversation_id}/parts"
            
            async with session.get(url, headers=self.headers) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("conversation_parts", [])
                return []
    
    async def is_conversation_fresh(self, conversation_id: str) -> bool:
        """Check if a conversation is fresh (no admin replies)"""
        parts = await self.get_conversation_parts(conversation_id)
        
        # Check if there are any admin replies
        for part in parts:
            if part.get("part_type") == "comment" and part.get("author", {}).get("type") == "admin":
                return False
        
        return True
    
    async def get_conversation_summary(self, conversation_id: str) -> Optional[Dict]:
        """Get a summary of conversation details"""
        conversation = await self.get_conversation(conversation_id)
        if not conversation:
            return None
        
        # Extract relevant information
        return {
            "id": conversation.get("id"),
            "status": conversation.get("state"),
            "subject": conversation.get("conversation_message", {}).get("subject"),
            "body": conversation.get("conversation_message", {}).get("body"),
            "user": conversation.get("user", {}),
            "created_at": conversation.get("created_at"),
            "updated_at": conversation.get("updated_at"),
            "is_fresh": await self.is_conversation_fresh(conversation_id)
        }
