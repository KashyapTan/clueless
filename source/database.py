import sqlite3
import json
import uuid
import time
from typing import List, Dict, Any
import os

class DatabaseManager:
    def __init__(self, database_path = 'user_data/clueless_app.db'):
        """
        Initialize the database manager.
        We use a specific file path so the data persists between app restarts.
        """
        os.makedirs(os.path.dirname(database_path), exist_ok=True)
        self.database_path = database_path
        self._init_db()
    
    def _get_connection(self):
        """
        Establishes a connection to the SQLite file.
        
        CRITICAL CONCEPT: check_same_thread=False
        By default, SQLite enforces that a connection created in one thread 
        can only be used in that same thread. 
        
        However, FastAPI (and Python's asyncio) runs in a 'ThreadPool', meaning 
        different requests might happen on different threads. If we don't set 
        this to False, your app will crash with a ProgrammingError when 
        multiple messages come in quickly.
        """
        return sqlite3.connect(self.database_path, check_same_thread=False)
    
    def _init_db(self):
        """
        Schema Definition.
        We use 'IF NOT EXISTS' so this runs safely every time the app boots.
        """
        connection = self._get_connection()
        cursor = connection.cursor()

        # --- TABLE 1: CONVERSATIONS ---
        # This acts as the "Folder" for messages.
        # It holds metadata used for the Sidebar list.
        # We store 'updated_at' so we can sort the sidebar by the most active chat.
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,    -- UUID string (e.g., "550e8400-e29b...")
                title TEXT,             -- A short summary of the chat
                created_at REAL,        -- 'REAL' is SQLite's float type (Unix timestamp)
                updated_at REAL,        -- Updated every time a new message is added
                total_input_tokens INTEGER DEFAULT 0,   -- Cumulative input tokens
                total_output_tokens INTEGER DEFAULT 0   -- Cumulative output tokens
            )
        ''')

        # Migration: add token columns to existing databases that lack them
        try:
            cursor.execute("ALTER TABLE conversations ADD COLUMN total_input_tokens INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # Column already exists
        try:
            cursor.execute("ALTER TABLE conversations ADD COLUMN total_output_tokens INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # Column already exists

        # --- TABLE 2: MESSAGES ---
        # This holds the actual content.
        # The 'conversation_id' column links this message to a specific row 
        # in the 'conversations' table. This establishes a "One-to-Many" relationship:
        # One Conversation has Many Messages.
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                num_messages INTEGER PRIMARY KEY AUTOINCREMENT, -- Auto-numbers messages (1, 2, 3...)
                conversation_id TEXT,                 -- The link to the parent chat
                role TEXT,                            -- 'user' or 'assistant'
                content TEXT,                         -- The actual text body
                images TEXT,                          -- SEE NOTE BELOW
                created_at REAL,
                FOREIGN KEY(conversation_id) REFERENCES conversations(id)  
            )
        ''')

        # NOTE ON IMAGES: SQLite does not have an ARRAY type. 
        # To store a list of image paths like ["img1.png", "img2.png"], 
        # we must serialize it into a JSON string like '["img1.png", "img2.png"]'
        # before saving, and parse it back into a list when loading.

        connection.commit()
        connection.close()

    # ---------------------------------------------------------
    # WRITE OPERATIONS (Saving Data)
    # ---------------------------------------------------------

    def start_new_conversation(self, title:str) -> str:
        """
        Creates a 'Folder' for a new chat session.
        Returns the unique ID so the frontend knows which chat is active.
        """
        connection = self._get_connection()
        cursor = connection.cursor()

        # generate a unique random ID
        new_id = str(uuid.uuid4())
        time_stamp = time.time()

        cursor.execute(
            "INSERT INTO conversations (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (new_id, title, time_stamp, time_stamp)
        )

        connection.commit()
        connection.close()
        return new_id

    def add_message(self, conversation_id: str, role: str, content: str, images: List[str] | None = None):
        """
        Saves a message AND updates the parent conversation's timestamp.
        """

        connection = self._get_connection()
        cursor = connection.cursor()
        time_stamp = time.time()

        # 1. Serialize: Convert Python List -> JSON String
        # If images is None, store None (NULL in SQL). 
        # If it's a list, make it a string.
        images_json = json.dumps(images) if images else None

        cursor.execute(
            "INSERT INTO messages (conversation_id, role, content, images, created_at)  VALUES (?, ?, ?, ?, ?)",
            (conversation_id, role, content, images_json, time_stamp)
        )

        # 3. Update the Parent
        # This is crucial for the UI. When you send a message in an old chat,
        # that chat should jump to the top of the sidebar list.
        # We do this by updating 'updated_at' to right now.

        cursor.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?",
            (time_stamp, conversation_id)
        )

        connection.commit()
        connection.close()
    
    # ---------------------------------------------------------
    # READ OPERATIONS (Loading Data)
    # ---------------------------------------------------------

    def get_recent_conversations(self, limit:int = 5, offset:int = 0) -> List[Dict]:
        """
        LAZY LOADING IMPLEMENTATION:
        We don't select * (all columns). We only select metadata.
        We don't select the messages here. That would be too heavy.
        
        SQL:
        ORDER BY updated_at DESC -> puts newest chats first.
        LIMIT 10 OFFSET 0 -> Get items 1-10
        LIMIT 10 OFFSET 10 -> Get items 11-20 (User scrolled down)
        """
        connection = self._get_connection()
        cursor = connection.cursor()

        cursor.execute(
            '''SELECT id, title, updated_at from conversations
                ORDER BY updated_at DESC
                LIMIT ? OFFSET ?''',
            (limit, offset)
        )

        rows = cursor.fetchall()
        connection.close()

        # Convert raw tuples [(id, title), (id, title)] 
        # into nice Dictionaries for JSON response
        return [{'id': r[0], 'title': r[1], 'date': r[2]} for r in rows]
    
    def get_full_conversation(self, conversation_id:str) -> List[Dict]:
        """
        Detailed Load:
        When user clicks a sidebar item, we fetch the actual messages.
        """
        connection = self._get_connection()
        cursor = connection.cursor()

        cursor.execute(
            """SELECT role, content, images, created_at from messages
                WHERE conversation_id = ?
                ORDER BY created_at ASC""", # Oldest messages at top (like standard chat)
            (conversation_id,)
        )

        rows = cursor.fetchall()
        connection.close()

        results = []

        for row in rows:
            # Deserialize: JSON String -> Python List
            # If row[2] (images) is a string, parse it. If None, return empty list.
            img_list = json.loads(row[2]) if row[2] else []
            
            results.append({
                "role": row[0],
                "content": row[1],
                "images": img_list,
                "timestamp": row[3]
            })
        return results

    def delete_conversation(self, conversation_id: str):
        """
        Deletes a conversation and all its messages from the database.
        """
        connection = self._get_connection()
        cursor = connection.cursor()

        # Delete messages first (child rows), then the conversation (parent)
        cursor.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
        cursor.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))

        connection.commit()
        connection.close()

    def search_conversations(self, search_term: str, limit: int = 20) -> List[Dict]:
        """
        Search conversations by title or by message content.
        Returns matching conversation metadata.
        """
        connection = self._get_connection()
        cursor = connection.cursor()

        # Search in conversation titles AND message content
        cursor.execute(
            '''SELECT DISTINCT c.id, c.title, c.updated_at 
               FROM conversations c
               LEFT JOIN messages m ON c.id = m.conversation_id
               WHERE c.title LIKE ? OR m.content LIKE ?
               ORDER BY c.updated_at DESC
               LIMIT ?''',
            (f'%{search_term}%', f'%{search_term}%', limit)
        )

        rows = cursor.fetchall()
        connection.close()

        return [{'id': r[0], 'title': r[1], 'date': r[2]} for r in rows]

    def update_conversation_title(self, conversation_id: str, title: str):
        """
        Update the title of an existing conversation.
        """
        connection = self._get_connection()
        cursor = connection.cursor()

        cursor.execute(
            "UPDATE conversations SET title = ? WHERE id = ?",
            (title, conversation_id)
        )

        connection.commit()
        connection.close()

    def add_token_usage(self, conversation_id: str, input_tokens: int, output_tokens: int):
        """
        Accumulate token usage for a conversation.
        Adds the given counts to the running totals.
        """
        connection = self._get_connection()
        cursor = connection.cursor()

        cursor.execute(
            """UPDATE conversations 
               SET total_input_tokens = total_input_tokens + ?,
                   total_output_tokens = total_output_tokens + ?
               WHERE id = ?""",
            (input_tokens, output_tokens, conversation_id)
        )

        connection.commit()
        connection.close()

    def get_token_usage(self, conversation_id: str) -> Dict:
        """
        Get cumulative token usage for a conversation.
        """
        connection = self._get_connection()
        cursor = connection.cursor()

        cursor.execute(
            "SELECT total_input_tokens, total_output_tokens FROM conversations WHERE id = ?",
            (conversation_id,)
        )

        row = cursor.fetchone()
        connection.close()

        if row:
            return {
                'input': row[0] or 0,
                'output': row[1] or 0,
                'total': (row[0] or 0) + (row[1] or 0)
            }
        return {'input': 0, 'output': 0, 'total': 0}




    

