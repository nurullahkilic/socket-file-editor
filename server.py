import asyncio
import websockets
import json
import os
from typing import Dict, Set

HOST = 'localhost'
PORT = 8765

# Global state
clients: Dict[str, websockets.WebSocketServerProtocol] = {}
documents: Dict[str, str] = {}
active_editors: Dict[str, Set[str]] = {}

async def load_documents():
    if not os.path.exists("documents"):
        os.makedirs("documents")
    for filename in os.listdir("documents"):
        with open(f"documents/{filename}", "r", encoding="utf-8") as f:
            documents[filename] = f.read()

async def save_document(filename: str):
    with open(f"documents/{filename}", "w", encoding="utf-8") as f:
        f.write(documents[filename])

async def broadcast_update(filename: str, new_text: str, exclude_username: str = None):
    """Send update to all active editors except the sender"""
    if filename in active_editors:
        for username, websocket in clients.items():
            if username != exclude_username and username in active_editors[filename]:
                try:
                    await websocket.send(json.dumps({
                        "type": "UPDATE",
                        "filename": filename,
                        "content": new_text
                    }))
                except:
                    print(f"Failed to send update to {username}")

async def handle_client(websocket: websockets.WebSocketServerProtocol, path: str):
    username = None
    try:
        # Wait for HELLO message
        message = await websocket.recv()
        data = json.loads(message)
        if data["type"] == "HELLO":
            username = data["username"]
            clients[username] = websocket
            await websocket.send(json.dumps({
                "type": "INFO",
                "content": f"Welcome, {username}"
            }))
            print(f"User logged in: {username}")

        # Main message loop
        async for message in websocket:
            data = json.loads(message)
            msg_type = data["type"]

            if msg_type == "FILES":
                await websocket.send(json.dumps({
                    "type": "FILES",
                    "content": list(documents.keys())
                }))

            elif msg_type == "EDIT":
                filename = data["filename"]
                new_text = data["content"]
                documents[filename] = new_text
                await save_document(filename)
                await broadcast_update(filename, new_text, username)

            elif msg_type == "GET":
                filename = data["filename"]
                if filename in documents:
                    file_content = documents[filename]
                    if filename not in active_editors:
                        active_editors[filename] = set()
                    active_editors[filename].add(username)
                    
                    # Send file content
                    await websocket.send(json.dumps({
                        "type": "CONTENT",
                        "filename": filename,
                        "content": file_content
                    }))
                    
                    # Notify others about active editors
                    for user, ws in clients.items():
                        if user != username:
                            try:
                                await ws.send(json.dumps({
                                    "type": "ACTIVE_EDITORS",
                                    "filename": filename,
                                    "editors": list(active_editors[filename])
                                }))
                            except:
                                print(f"Failed to send active editors info to {user}")
                else:
                    # Create new file
                    documents[filename] = ""
                    await save_document(filename)
                    if filename not in active_editors:
                        active_editors[filename] = set()
                    active_editors[filename].add(username)
                    await websocket.send(json.dumps({
                        "type": "CONTENT",
                        "filename": filename,
                        "content": ""
                    }))

            elif msg_type == "CLOSE_EDIT":
                filename = data["filename"]
                if filename in active_editors and username in active_editors[filename]:
                    active_editors[filename].remove(username)
                    if not active_editors[filename]:
                        del active_editors[filename]
                    
                    # Notify others about active editors
                    for user, ws in clients.items():
                        if user != username:
                            try:
                                await ws.send(json.dumps({
                                    "type": "ACTIVE_EDITORS",
                                    "filename": filename,
                                    "editors": list(active_editors.get(filename, []))
                                }))
                            except:
                                print(f"Failed to send active editors info to {user}")

    except websockets.exceptions.ConnectionClosed:
        print(f"Connection closed for {username}")
    finally:
        if username:
            if username in clients:
                del clients[username]
            # Remove user from all active editors
            for filename in list(active_editors.keys()):
                if username in active_editors[filename]:
                    active_editors[filename].remove(username)
                    if not active_editors[filename]:
                        del active_editors[filename]
            print(f"{username} disconnected")

async def main():
    await load_documents()
    async with websockets.serve(handle_client, HOST, PORT):
        print(f"Server started on ws://{HOST}:{PORT}")
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    asyncio.run(main())
