import asyncio
import websockets
import json
import tkinter as tk
from tkinter import scrolledtext, messagebox, simpledialog
from typing import Dict, Optional
import threading
import queue

HOST = 'localhost'
PORT = 8765

class TextEditorClient:
    def __init__(self, root):
        self.root = root
        self.root.title("Text Editor")
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.active_editors: Dict[str, list] = {}
        self.edit_windows: Dict[str, tk.Toplevel] = {}
        self.text_widgets: Dict[str, scrolledtext.ScrolledText] = {}
        self.last_cursor_positions: Dict[str, str] = {}
        self.is_updating = False
        self.username = None
        self.message_queue = queue.Queue()
        self.loop = None
        
        self.setup_ui()
        self.connect_to_server()
        
    def setup_ui(self):
        # Menu Bar
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="File List", command=self.request_file_list)
        file_menu.add_command(label="Edit", command=self.edit_file)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.exit_app)
        menubar.add_cascade(label="File", menu=file_menu)
        self.root.config(menu=menubar)
        
        # Main Content
        self.text_area = scrolledtext.ScrolledText(self.root, wrap=tk.WORD)
        self.text_area.pack(expand=True, fill='both')
        self.text_area.config(state='disabled')
        
        # Status Bar
        self.status_bar = tk.Label(self.root, text="Connecting...", bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    
    def connect_to_server(self):
        try:
            self.username = simpledialog.askstring("Username", "Enter your username:")
            if not self.username:
                self.root.destroy()
                return
            
            # Start WebSocket connection in a separate thread
            self.ws_thread = threading.Thread(target=self._run_websocket, daemon=True)
            self.ws_thread.start()
            
            # Start processing messages from the queue
            self.process_messages()
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not connect to server: {str(e)}")
            self.root.destroy()
    
    def _run_websocket(self):
        """Run WebSocket connection in a separate thread"""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._connect_and_listen())
    
    async def _connect_and_listen(self):
        """Connect to WebSocket server and start listening"""
        try:
            self.websocket = await websockets.connect(f'ws://{HOST}:{PORT}')
            await self.websocket.send(json.dumps({
                "type": "HELLO",
                "username": self.username
            }))
            
            # Update UI in the main thread
            self.message_queue.put(("STATUS", f"Connected - User: {self.username}"))
            
            while True:
                try:
                    message = await self.websocket.recv()
                    self.message_queue.put(("MESSAGE", message))
                except websockets.exceptions.ConnectionClosed:
                    self.message_queue.put(("ERROR", "Connection to server lost"))
                    break
                except Exception as e:
                    print(f"Error in server listener: {str(e)}")
                    break
                    
        except Exception as e:
            self.message_queue.put(("ERROR", f"Could not connect to server: {str(e)}"))
    
    def process_messages(self):
        """Process messages from the queue in the main thread"""
        try:
            while True:
                msg_type, content = self.message_queue.get_nowait()
                
                if msg_type == "STATUS":
                    self.status_bar.config(text=content)
                elif msg_type == "ERROR":
                    messagebox.showerror("Error", content)
                    self.root.destroy()
                    return
                elif msg_type == "MESSAGE":
                    self._handle_message(content)
                    
        except queue.Empty:
            pass
        
        # Schedule next check
        self.root.after(100, self.process_messages)
    
    def _handle_message(self, message):
        """Handle incoming WebSocket messages"""
        data = json.loads(message)
        msg_type = data["type"]
        
        if msg_type == "UPDATE":
            filename = data["filename"]
            new_text = data["content"]
            text_widget = self.get_text_widget(filename)
            if text_widget:
                self.update_text_content(text_widget, new_text, filename)
                
        elif msg_type == "FILES":
            self.show_file_list(data["content"])
            
        elif msg_type == "INFO":
            messagebox.showinfo("Info", data["content"])
            
        elif msg_type == "CONTENT":
            filename = data["filename"]
            file_content = data["content"]
            text_widget = self.get_text_widget(filename)
            if text_widget:
                self.update_text_content(text_widget, file_content, filename)
                
        elif msg_type == "ACTIVE_EDITORS":
            filename = data["filename"]
            editors = data["editors"]
            self.active_editors[filename] = editors
            self.update_active_editors_display(filename)
    
    def on_text_change(self, event, filename):
        if self.is_updating:
            return
            
        text_widget = event.widget
        new_text = text_widget.get(1.0, tk.END)
        cursor_pos = text_widget.index(tk.INSERT)
        self.last_cursor_positions[filename] = cursor_pos
        
        # Send update in the WebSocket thread
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.websocket.send(json.dumps({
                    "type": "EDIT",
                    "filename": filename,
                    "content": new_text
                })),
                self.loop
            )

    def get_text_widget(self, filename):
        """Get text widget for a specific file"""
        if filename in self.text_widgets:
            return self.text_widgets[filename]
        return None

    def update_text_content(self, text_widget, new_text, filename):
        if self.is_updating:
            return
            
        self.is_updating = True
        try:
            # Save current cursor position
            cursor_pos = text_widget.index(tk.INSERT)
            
            # Update text
            text_widget.delete(1.0, tk.END)
            text_widget.insert(tk.END, new_text)
            
            # Restore cursor position
            if filename in self.last_cursor_positions:
                saved_pos = self.last_cursor_positions[filename]
                text_widget.mark_set(tk.INSERT, saved_pos)
                text_widget.see(saved_pos)
            else:
                text_widget.mark_set(tk.INSERT, cursor_pos)
                text_widget.see(cursor_pos)
        finally:
            self.is_updating = False

    def update_active_editors_display(self, filename):
        if filename in self.edit_windows:
            window = self.edit_windows[filename]
            editors = self.active_editors.get(filename, [])
            if editors:
                window.title(f"Edit: {filename} (Active editors: {', '.join(editors)})")
            else:
                window.title(f"Edit: {filename}")

    def display_content(self, filename, content):
        self.text_area.config(state='normal')
        self.text_area.delete(1.0, tk.END)
        self.text_area.insert(tk.END, f"{filename}\n\n{content}")
        self.text_area.config(state='disabled')
        self.status_bar.config(text=f"{filename} updated")
    
    def show_file_list(self, files):
        selected = simpledialog.askstring("Select File", "Enter filename to edit:\n\n" + "\n".join(files))
        if selected:
            self.edit_file(selected)
    
    def request_file_list(self):
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.websocket.send(json.dumps({
                    "type": "FILES"
                })),
                self.loop
            )
    
    def edit_file(self, filename=None):
        if not filename:
            filename = simpledialog.askstring("Filename", "Enter filename to edit:")
            if not filename:
                return
                
        if filename in self.edit_windows:
            self.edit_windows[filename].lift()
            return

        edit_window = tk.Toplevel(self.root)
        edit_window.title(f"Edit: {filename}")
        self.edit_windows[filename] = edit_window
        
        # Create text widget
        text_area = scrolledtext.ScrolledText(edit_window, wrap=tk.WORD)
        text_area.pack(expand=True, fill='both')
        self.text_widgets[filename] = text_area
        
        # Listen for text changes
        text_area.bind('<KeyRelease>', lambda e: self.on_text_change(e, filename))
        
        # Request file content
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.websocket.send(json.dumps({
                    "type": "GET",
                    "filename": filename
                })),
                self.loop
            )
        
        def on_window_close():
            if self.loop and self.loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    self.websocket.send(json.dumps({
                        "type": "CLOSE_EDIT",
                        "filename": filename
                    })),
                    self.loop
                )
            if filename in self.edit_windows:
                del self.edit_windows[filename]
            if filename in self.text_widgets:
                del self.text_widgets[filename]
            if filename in self.active_editors:
                del self.active_editors[filename]
            if filename in self.last_cursor_positions:
                del self.last_cursor_positions[filename]
            edit_window.destroy()
        
        edit_window.protocol("WM_DELETE_WINDOW", on_window_close)
    
    def exit_app(self):
        if self.websocket and self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.websocket.close(),
                self.loop
            )
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = TextEditorClient(root)
    root.mainloop() 