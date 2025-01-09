import os
import sys
import json
import unittest
import tempfile
import sqlite3
import requests
from unittest.mock import patch, MagicMock
import io
import socket

# Add the project directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import chat_server

class TestDatabase(unittest.TestCase):
    def setUp(self):
        # Create a temporary database for testing
        self.temp_db = tempfile.mktemp()
        self.database = chat_server.Database(self.temp_db)

    def tearDown(self):
        # Close the database connection and remove the temporary file
        self.database.conn.close()
        if os.path.exists(self.temp_db):
            os.unlink(self.temp_db)

    def test_add_and_retrieve_messages(self):
        # Test adding a message
        message_id = self.database.add_message("Test message", "test_repo")
        self.assertIsNotNone(message_id)

        # Test retrieving messages
        messages = self.database.get_messages()
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]['content'], "Test message")
        self.assertEqual(messages[0]['repository'], "test_repo")

    def test_multiple_messages(self):
        # Add multiple messages
        self.database.add_message("Message 1", "repo1")
        self.database.add_message("Message 2", "repo2")

        messages = self.database.get_messages()
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]['content'], "Message 1")
        self.assertEqual(messages[1]['content'], "Message 2")

class TestRepositoryManager(unittest.TestCase):
    def setUp(self):
        # Mock GitHub credentials
        self.github_token = 'fake_token'
        self.github_username = 'test_user'
        self.repository_name = 'test_repo'
        
        self.repo_manager = chat_server.RepositoryManager(
            self.github_token, 
            self.github_username, 
            self.repository_name
        )

    @patch('requests.put')
    @patch('requests.get')
    def test_push_messages(self, mock_get, mock_put):
        # Mock GitHub API responses
        mock_get.return_value.status_code = 404  # File doesn't exist
        mock_put.return_value.raise_for_status = MagicMock()

        # Prepare test messages
        messages = [
            {
                'content': 'Test message 1', 
                'timestamp': '2025-01-08T19:20:00-05:00', 
                'repository': 'test_repo'
            },
            {
                'content': 'Test message 2', 
                'timestamp': '2025-01-08T19:21:00-05:00', 
                'repository': 'test_repo'
            }
        ]

        # Test pushing messages
        result = self.repo_manager.push_messages(messages)
        self.assertTrue(result)

        # Verify API calls
        mock_put.assert_called_once()
        
        # Check the content of the API call
        call_args = mock_put.call_args[1]
        payload = json.loads(call_args['data'])
        
        # Verify payload content
        self.assertIn('content', payload)
        self.assertIn('message', payload)
        self.assertEqual(payload['message'], 'Update chat messages')

class TestMessageHandler(unittest.TestCase):
    def setUp(self):
        # Create a mock server for testing HTTP handlers
        self.server_address = ('', 0)  # Automatically choose an available port
        self.handler = chat_server.MessageHandler

    @patch.object(chat_server.Database, 'get_messages')
    def test_get_messages(self, mock_get_messages):
        # Mock database messages
        mock_messages = [
            {'id': 1, 'content': 'Test message', 'timestamp': '2025-01-08T19:22:00-05:00'}
        ]
        mock_get_messages.return_value = mock_messages

        # Create a mock request handler with full socket simulation
        class MockSocket:
            def __init__(self):
                self.timeout = None
                self.disable_nagle_algorithm = False
                self.rbufsize = -1

            def makefile(self, mode, bufsize):
                return io.BytesIO()

            def settimeout(self, timeout):
                pass

            def setsockopt(self, *args):
                pass

        # Simulate a GET request to /messages
        handler = self.handler(MockSocket(), self.server_address, None)
        handler.path = '/messages'
        handler.wfile = MagicMock()  # Mock the wfile attribute
        handler.send_response = MagicMock()
        handler.send_header = MagicMock()
        handler.end_headers = MagicMock()

        # Call the method
        handler.do_GET()

        # Check if messages were written to wfile
        handler.wfile.write.assert_called_once()
        written_data = handler.wfile.write.call_args[0][0].decode()
        retrieved_messages = json.loads(written_data)
        
        self.assertEqual(len(retrieved_messages), 1)
        self.assertEqual(retrieved_messages[0]['content'], 'Test message')

def main():
    # Run tests
    unittest.main(argv=[''], exit=False)

if __name__ == '__main__':
    main()
