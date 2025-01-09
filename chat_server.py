import os
import json
import http.server
import socketserver
from urllib.parse import parse_qs, urlparse
import requests
import base64
from dotenv import load_dotenv
import sqlite3
from datetime import datetime
import socket

# Load environment variables
load_dotenv()

class Database:
    def __init__(self, db_path='messages.db'):
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self._create_table()

    def _create_table(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                repository TEXT
            )
        ''')
        self.conn.commit()

    def add_message(self, content, repository):
        self.cursor.execute(
            'INSERT INTO messages (content, repository) VALUES (?, ?)', 
            (content, repository)
        )
        self.conn.commit()
        return self.cursor.lastrowid

    def get_messages(self):
        self.cursor.execute('SELECT * FROM messages ORDER BY timestamp')
        columns = [col[0] for col in self.cursor.description]
        return [dict(zip(columns, row)) for row in self.cursor.fetchall()]

class RepositoryManager:
    def __init__(self, github_token, github_username, repository_name):
        self.github_token = github_token
        self.github_username = github_username
        self.repository_name = repository_name
        self.headers = {
            'Authorization': f'token {self.github_token}',
            'Accept': 'application/vnd.github.v3+json'
        }

    def push_messages(self, messages):
        try:
            # Extensive logging for debugging
            print(f"🔍 Attempting to push {len(messages)} messages to repository")
            print(f"Repository: {self.repository_name}")
            print(f"GitHub Username: {self.github_username}")
            print(f"GitHub Token: {'*' * 8 + self.github_token[-4:] if self.github_token else 'Not Set'}")

            # Validate inputs
            if not messages:
                print("❌ No messages to push")
                return False

            # Create a markdown file with messages
            content = "# Chat Messages\n\n"
            for msg in messages:
                timestamp = msg.get('timestamp', 'No Timestamp')
                message_content = msg.get('content', 'No Content')
                content += f"## {timestamp}\n{message_content}\n\n"

            # Get the current SHA of the file (if it exists)
            file_path = 'chat_messages.md'
            try:
                url = f'https://api.github.com/repos/{self.github_username}/{self.repository_name}/contents/{file_path}'
                
                # Log the exact API request details
                print(f"🌐 GitHub API URL: {url}")
                
                # First, try to get the existing file
                get_response = requests.get(url, headers=self.headers)
                print(f"GET Response Status: {get_response.status_code}")
                print(f"GET Response Content: {get_response.text}")
                
                # Prepare payload for creating/updating file
                payload = {
                    'message': f'Update chat messages ({len(messages)} total)',
                    'content': base64.b64encode(content.encode()).decode(),
                    'branch': 'master'  # Explicitly set to master
                }
                
                # If file exists, include its SHA for update
                if get_response.status_code == 200:
                    existing_file = get_response.json()
                    payload['sha'] = existing_file['sha']
                
                # Log the PUT payload
                print(f"📤 Payload Message: {payload['message']}")
                print(f"📤 Payload Content Length: {len(payload['content'])} bytes")
                
                # Perform the PUT request to create/update the file
                put_response = requests.put(url, 
                    headers=self.headers, 
                    data=json.dumps(payload)
                )
                
                # Log the PUT response details
                print(f"PUT Response Status: {put_response.status_code}")
                print(f"PUT Response Content: {put_response.text}")
                
                # Check for successful response
                if put_response.status_code in [200, 201]:
                    print("✅ Messages successfully pushed to GitHub!")
                    return True
                else:
                    print(f"❌ GitHub API Error: {put_response.text}")
                    return False
            
            except requests.exceptions.RequestException as e:
                print(f"❌ Network Error: {e}")
                return False
        
        except Exception as e:
            print(f"❌ Unexpected error pushing messages: {e}")
            import traceback
            traceback.print_exc()
            return False

class MessageHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        self.database = Database()
        self.repo_manager = RepositoryManager(
            os.getenv('GITHUB_TOKEN'),
            os.getenv('GITHUB_USERNAME'),
            os.getenv('REPOSITORY_NAME')
        )
        super().__init__(*args, **kwargs)

    def do_GET(self):
        parsed_path = urlparse(self.path)
        
        if parsed_path.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            with open('index.html', 'rb') as f:
                self.wfile.write(f.read())
        
        elif parsed_path.path == '/messages':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            messages = self.database.get_messages()
            self.wfile.write(json.dumps(messages).encode())
        
        else:
            self.send_error(404)

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        if self.path == '/messages':
            try:
                message_data = json.loads(post_data.decode('utf-8'))
                message_id = self.database.add_message(
                    message_data['content'], 
                    message_data.get('repository', 'default')
                )
                
                # Automatically push messages to repository
                messages = self.database.get_messages()
                push_success = self.repo_manager.push_messages(messages)
                
                self.send_response(201 if push_success else 206)  # 206 if message added but push failed
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'id': message_id, 
                    'push_success': push_success
                }).encode())
            except Exception as e:
                self.send_error(400, f'Invalid message: {str(e)}')
        
        elif self.path == '/push':
            messages = self.database.get_messages()
            success = self.repo_manager.push_messages(messages)
            
            self.send_response(200 if success else 500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'success': success}).encode())
        
        else:
            self.send_error(404)

def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port

def run_server(port=None):
    if port is None:
        port = find_free_port()
    
    print(f"🚀 Attempting to start Chat Message Server on port {port}")
    try:
        with socketserver.TCPServer(("", port), MessageHandler) as httpd:
            print(f"✅ Server successfully started on http://localhost:{port}")
            print("Press Ctrl+C to stop the server.")
            httpd.serve_forever()
    except Exception as e:
        print(f"❌ Failed to start server: {e}")

if __name__ == "__main__":
    port = 8090  # Explicitly set to 8090
    print(f"🚀 Starting server on port {port}")
    run_server(port)
