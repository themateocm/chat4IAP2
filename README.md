# Chat Message Management System

## Overview
A Python-based web application for managing and storing chat messages across GitHub repositories.

## Features
- Local message storage with SQLite
- GitHub repository synchronization
- Simple web interface for message management

## Setup

### Prerequisites
- Python 3.8+
- GitHub Personal Access Token

### Installation
1. Clone the repository
2. Create a virtual environment
```bash
python3 -m venv venv
source venv/bin/activate
```

3. Install dependencies
```bash
pip install -r requirements.txt
```

4. Copy `.env.template` to `.env` and fill in your GitHub credentials

### Running the Server
```bash
python chat_server.py
```

## Usage
- Access the web interface at `http://localhost:8080`
- Send messages
- Push messages to configured GitHub repository

## Environment Variables
- `GITHUB_TOKEN`: Personal GitHub access token
- `GITHUB_USERNAME`: Your GitHub username
- `REPOSITORY_NAME`: Target repository for message storage
- `SERVER_PORT`: Optional, defaults to 8080
