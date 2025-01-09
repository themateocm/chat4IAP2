import os
import sys
import requests
import base64
import json

# Manually read .env file
def load_env():
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    print(f"🔍 Checking .env file at: {env_path}")
    print("📄 Raw .env File Contents:")
    
    try:
        with open(env_path, 'r') as f:
            raw_contents = f.read()
            print(repr(raw_contents))
    except Exception as e:
        print(f"❌ Error reading file: {e}")
    
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            env_contents = f.read()
            print("\n📄 .env File Contents:")
            print(env_contents)
            
            for line in env_contents.split('\n'):
                line = line.strip()
                if line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

# Load environment variables
load_env()

# GitHub credentials from environment
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
GITHUB_USERNAME = os.getenv('GITHUB_USERNAME')
REPOSITORY_NAME = os.getenv('REPOSITORY_NAME')

def test_github_push():
    print("🔍 Starting GitHub Push Diagnostic Test")
    
    # Print ALL environment variables for debugging
    print("\n🔑 ALL Environment Variables:")
    for key, value in os.environ.items():
        print(f"{key}: {value}")
    
    # Validate environment variables
    print("\n📋 Checking Specific GitHub Variables:")
    print(f"GitHub Token: {GITHUB_TOKEN[:5]}...{GITHUB_TOKEN[-5:]} {'✓' if GITHUB_TOKEN else '✗'}")
    print(f"GitHub Username: {GITHUB_USERNAME}")
    print(f"Repository Name: {REPOSITORY_NAME}")
    
    if not all([GITHUB_TOKEN, GITHUB_USERNAME, REPOSITORY_NAME]):
        print("❌ Missing required environment variables!")
        return False
    
    # Prepare headers for GitHub API
    headers = {
        'Authorization': f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3+json'
    }
    
    # Prepare file content
    file_path = 'chat_messages.md'
    content = f"# Diagnostic Test Message\n\nThis is a test message to diagnose GitHub push functionality.\n\nTimestamp: {os.getenv('TIMESTAMP', 'No Timestamp')}"
    
    # GitHub API URL
    url = f'https://api.github.com/repos/{GITHUB_USERNAME}/{REPOSITORY_NAME}/contents/{file_path}'
    
    try:
        # First, check if file exists
        print("\n🌐 Checking File Existence:")
        get_response = requests.get(url, headers=headers)
        print(f"GET Request Status: {get_response.status_code}")
        print(f"GET Response Content: {get_response.text}")
        
        # Prepare payload
        payload = {
            'message': 'Diagnostic test push',
            'content': base64.b64encode(content.encode()).decode(),
            'branch': 'master'
        }
        
        # Include SHA if file exists
        if get_response.status_code == 200:
            existing_file = get_response.json()
            payload['sha'] = existing_file['sha']
        
        # Perform push
        print("\n📤 Attempting to Push File:")
        put_response = requests.put(url, headers=headers, data=json.dumps(payload))
        
        print(f"PUT Request Status: {put_response.status_code}")
        print(f"PUT Response Content: {put_response.text}")
        
        # Check for successful response
        if put_response.status_code in [200, 201]:
            print("✅ Successfully pushed to GitHub!")
            return True
        else:
            print("❌ Failed to push to GitHub")
            return False
    
    except Exception as e:
        print(f"❌ Unexpected Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    success = test_github_push()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
