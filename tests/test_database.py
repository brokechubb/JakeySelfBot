#!/usr/bin/env python3
"""
Tests for database functionality
"""

import unittest
import os
import tempfile
import sys
from unittest.mock import patch, MagicMock

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from data.database import DatabaseManager

class TestDatabaseManager(unittest.TestCase):
    """Test cases for the DatabaseManager class"""
    
    def setUp(self):
        """Set up test fixtures before each test method"""
        # Create a temporary database for testing
        self.test_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.test_db.close()
        
        # Create database manager with test database
        with patch('data.database.DATABASE_PATH', self.test_db.name):
            self.db = DatabaseManager()
    
    def tearDown(self):
        """Tear down test fixtures after each test method"""
        # Clean up temporary database file
        if os.path.exists(self.test_db.name):
            os.unlink(self.test_db.name)
    
    def test_init_database(self):
        """Test that database is initialized with correct tables"""
        # Check that tables exist
        import sqlite3
        conn = sqlite3.connect(self.test_db.name)
        cursor = conn.cursor()
        
        # Check users table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        self.assertIsNotNone(cursor.fetchone())
        
        # Check conversations table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='conversations'")
        self.assertIsNotNone(cursor.fetchone())
        
        # Check memories table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='memories'")
        self.assertIsNotNone(cursor.fetchone())
        
        conn.close()
    
    def test_create_or_update_user(self):
        """Test creating and updating user data"""
        user_id = "123456789"
        username = "testuser"
        
        # Create user
        self.db.create_or_update_user(user_id, username)
        
        # Check user was created
        user_data = self.db.get_user(user_id)
        self.assertIsNotNone(user_data)
        self.assertEqual(user_data['user_id'], user_id)
        self.assertEqual(user_data['username'], username)
        self.assertEqual(user_data['preferences'], {})
        self.assertEqual(user_data['important_facts'], {})
    
    def test_add_and_get_memory(self):
        """Test adding and retrieving user memories"""
        user_id = "123456789"
        key = "favorite_team"
        value = "Dallas Cowboys"
        
        # Add memory
        self.db.add_memory(user_id, key, value)
        
        # Retrieve memory
        retrieved_value = self.db.get_memory(user_id, key)
        self.assertEqual(retrieved_value, value)
    
    def test_get_memories(self):
        """Test retrieving all memories for a user"""
        user_id = "123456789"
        
        # Add multiple memories
        self.db.add_memory(user_id, "favorite_team", "Dallas Cowboys")
        self.db.add_memory(user_id, "location", "Las Vegas")
        
        # Retrieve all memories
        memories = self.db.get_memories(user_id)
        self.assertEqual(len(memories), 2)
        self.assertEqual(memories["favorite_team"], "Dallas Cowboys")
        self.assertEqual(memories["location"], "Las Vegas")
    
    def test_get_nonexistent_user(self):
        """Test getting a user that doesn't exist"""
        user_data = self.db.get_user("nonexistent")
        self.assertIsNone(user_data)
    
    def test_get_nonexistent_memory(self):
        """Test getting a memory that doesn't exist"""
        value = self.db.get_memory("nonexistent", "nonexistent_key")
        self.assertIsNone(value)
    
    def test_add_conversation(self):
        """Test adding conversation history"""
        user_id = "123456789"
        message_history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"}
        ]
        
        # Add conversation
        self.db.add_conversation(user_id, message_history, "test_channel")
        
        # Retrieve recent conversations
        conversations = self.db.get_recent_conversations(user_id)
        self.assertEqual(len(conversations), 1)
        self.assertEqual(conversations[0]['messages'], message_history)

if __name__ == '__main__':
    unittest.main()