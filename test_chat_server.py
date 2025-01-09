import os
import sys
import json
import unittest
import tempfile
import sqlite3
import requests
from unittest.mock import patch, MagicMock, Mock
import io
import socket
import base64

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
        # Create a temporary database for testing
        self.temp_db = tempfile.mktemp()
        self.database = chat_server.Database(self.temp_db)

    def tearDown(self):
        # Close the database connection and remove the temporary file
        self.database.conn.close()
        if os.path.exists(self.temp_db):
            os.unlink(self.temp_db)

    @patch('requests.put')
    @patch('requests.get')
    def test_push_messages(self, mock_get, mock_put):
        # Setup mock responses that simulate successful GitHub interaction
        mock_get.return_value = MagicMock(
            status_code=404,
            json=lambda: {"message": "Not Found"}
        )
        mock_put.return_value = MagicMock(
            status_code=201,
            json=lambda: {"content": {"name": "chat_messages.md"}}
        )

        # Add a test message to the database
        message_id = self.database.add_message("Test message for GitHub push", "test_repo")
        
        # Retrieve the messages
        messages = self.database.get_messages()

        # Create a mock RepositoryManager
        repo_manager = chat_server.RepositoryManager(
            'mock_token', 
            'mock_username', 
            'mock_repo'
        )

        # Attempt to push messages
        result = repo_manager.push_messages(messages)

        # Assert that the push was successful
        self.assertTrue(result, "Messages should be successfully pushed to GitHub")

        # Verify that GitHub API methods were called
        mock_get.assert_called_once()
        mock_put.assert_called_once()

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

class TestGitHubIntegration(unittest.TestCase):
    def setUp(self):
        # Mock GitHub API credentials
        self.mock_token = 'test_github_token'
        self.mock_username = 'test_username'
        self.mock_repo = 'test_repo'

    @patch('requests.put')
    @patch('requests.get')
    def test_push_messages_to_github(self, mock_get, mock_put):
        # Setup mock responses
        mock_get.return_value = Mock(
            status_code=404, 
            text=json.dumps({"message": "Not Found"})
        )
        mock_put.return_value = Mock(
            status_code=201, 
            text=json.dumps({"content": {"name": "chat_messages.md"}})
        )

        # Create a RepositoryManager with mock credentials
        repo_manager = chat_server.RepositoryManager(
            self.mock_token, 
            self.mock_username, 
            self.mock_repo
        )

        # Prepare test messages
        test_messages = [
            {'content': 'First test message', 'timestamp': '2025-01-08T19:55:00'},
            {'content': 'Second test message', 'timestamp': '2025-01-08T19:56:00'}
        ]

        # Attempt to push messages
        result = repo_manager.push_messages(test_messages)

        # Assertions
        self.assertTrue(result, "Messages should be successfully pushed")
        
        # Verify GitHub API calls
        mock_get.assert_called_once()
        mock_put.assert_called_once()

        # Check the content of the PUT request
        put_args = mock_put.call_args[1]
        payload = json.loads(put_args['data'])
        
        # Decode base64 content and verify
        decoded_content = base64.b64decode(payload['content']).decode('utf-8')
        self.assertIn('First test message', decoded_content)
        self.assertIn('Second test message', decoded_content)

    def test_message_content_formatting(self):
        # Create a RepositoryManager with mock credentials
        repo_manager = chat_server.RepositoryManager(
            self.mock_token, 
            self.mock_username, 
            self.mock_repo
        )

        # Test messages with various content types
        test_cases = [
            {'content': 'Simple message'},
            {'content': 'Message with special characters: !@#$%^&*()'},
            {'content': 'Multi-line\nmessage\nwith\nnewlines'}
        ]

        for message in test_cases:
            # Attempt to format message content
            content = "# Chat Messages\n\n"
            content += f"## {message.get('timestamp', 'No Timestamp')}\n{message['content']}\n\n"
            
            # Basic assertions about content formatting
            self.assertTrue(content.startswith('# Chat Messages'))
            self.assertIn(message['content'], content)

    @patch('requests.put')
    def test_github_push_error_handling(self, mock_put):
        # Simulate GitHub API error
        mock_put.return_value = Mock(status_code=500)

        # Create a RepositoryManager with mock credentials
        repo_manager = chat_server.RepositoryManager(
            self.mock_token, 
            self.mock_username, 
            self.mock_repo
        )

        # Prepare test messages
        test_messages = [{'content': 'Error test message'}]

        # Attempt to push messages
        result = repo_manager.push_messages(test_messages)

        # Verify error handling
        self.assertFalse(result, "Push should fail on server error")
        mock_put.assert_called_once()

def main():
    unittest.main()

if __name__ == '__main__':
    main()
