import sqlite3
import aiosqlite
from datetime import datetime
from typing import Optional, Dict, List

class DatabaseManager:
    def __init__(self, db_path: str = 'tickets.db'):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize the database with required tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tickets (
                id TEXT PRIMARY KEY,
                discord_message_id INTEGER,
                status TEXT,
                last_updated TIMESTAMP,
                intercom_conversation_id TEXT
            )
        ''')
        conn.commit()
        conn.close()
    
    async def add_ticket(self, ticket_id: str, discord_message_id: int, 
                        status: str, conversation_id: str):
        """Add a new ticket to the database"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT OR REPLACE INTO tickets 
                (id, discord_message_id, status, last_updated, intercom_conversation_id)
                VALUES (?, ?, ?, ?, ?)
            ''', (ticket_id, discord_message_id, status, 
                  datetime.now().isoformat(), conversation_id))
            await db.commit()
    
    async def update_ticket_status(self, ticket_id: str, status: str):
        """Update the status of a ticket"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                UPDATE tickets 
                SET status = ?, last_updated = ?
                WHERE id = ?
            ''', (status, datetime.now().isoformat(), ticket_id))
            await db.commit()
    
    async def get_ticket(self, ticket_id: str) -> Optional[Dict]:
        """Get ticket information by ID"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('''
                SELECT * FROM tickets WHERE id = ?
            ''', (ticket_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return {
                        'id': row[0],
                        'discord_message_id': row[1],
                        'status': row[2],
                        'last_updated': row[3],
                        'intercom_conversation_id': row[4]
                    }
                return None
    
    async def get_ticket_by_conversation(self, conversation_id: str) -> Optional[Dict]:
        """Get ticket information by Intercom conversation ID"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('''
                SELECT * FROM tickets WHERE intercom_conversation_id = ?
            ''', (conversation_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return {
                        'id': row[0],
                        'discord_message_id': row[1],
                        'status': row[2],
                        'last_updated': row[3],
                        'intercom_conversation_id': row[4]
                    }
                return None
    
    async def remove_ticket(self, ticket_id: str):
        """Remove a ticket from the database"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('DELETE FROM tickets WHERE id = ?', (ticket_id,))
            await db.commit()
    
    async def get_all_tickets(self) -> List[Dict]:
        """Get all tickets from the database"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('SELECT * FROM tickets') as cursor:
                rows = await cursor.fetchall()
                return [
                    {
                        'id': row[0],
                        'discord_message_id': row[1],
                        'status': row[2],
                        'last_updated': row[3],
                        'intercom_conversation_id': row[4]
                    }
                    for row in rows
                ]
    
    async def cleanup_old_tickets(self, days: int = 30):
        """Remove tickets older than specified days"""
        cutoff_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        cutoff_date = cutoff_date.replace(day=cutoff_date.day - days)
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                DELETE FROM tickets 
                WHERE last_updated < ?
            ''', (cutoff_date.isoformat(),))
            await db.commit()
