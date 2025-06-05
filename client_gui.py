import socket
import threading
import tkinter as tk
from tkinter import scrolledtext, messagebox, simpledialog
from protocol import create_message, parse_message

HOST = 'localhost'
PORT = 12345

class TextEditorClient:
    def __init__(self, root):
        self.root = root
        self.root.title("Metin Editörü")
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.active_editors = {}  # filename -> [usernames]
        self.edit_windows = {}  # filename -> window
        self.text_widgets = {}  # filename -> text_widget
        self.last_cursor_positions = {}  # filename -> cursor_position
        self.is_updating = False  # Güncelleme sırasında yeni güncelleme göndermeyi engellemek için
        self.username = None  # Kullanıcı adını saklamak için
        
        self.setup_ui()
        self.connect_to_server()
        
    def setup_ui(self):
        # Menü Çubuğu
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Dosya Listesi", command=self.request_file_list)
        file_menu.add_command(label="Düzenle", command=self.edit_file)
        file_menu.add_separator()
        file_menu.add_command(label="Çıkış", command=self.exit_app)
        menubar.add_cascade(label="Dosya", menu=file_menu)
        self.root.config(menu=menubar)
        
        # Ana İçerik
        self.text_area = scrolledtext.ScrolledText(self.root, wrap=tk.WORD)
        self.text_area.pack(expand=True, fill='both')
        self.text_area.config(state='disabled')
        
        # Durum Çubuğu
        self.status_bar = tk.Label(self.root, text="Bağlantı kuruluyor...", bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    
    def connect_to_server(self):
        try:
            self.username = simpledialog.askstring("Kullanıcı Adı", "Kullanıcı adınızı girin:")
            if not self.username:
                self.root.destroy()
                return
                
            self.client_socket.connect((HOST, PORT))
            self.client_socket.send(create_message("HELLO", self.username).encode())
            
            # Sunucu dinleme thread'i
            threading.Thread(target=self.listen_server, daemon=True).start()
            self.status_bar.config(text=f"Bağlantı kuruldu - Kullanıcı: {self.username}")
            
        except Exception as e:
            messagebox.showerror("Hata", f"Sunucuya bağlanılamadı: {str(e)}")
            self.root.destroy()
    
    def on_text_change(self, event, filename):
        if self.is_updating:
            return
            
        text_widget = event.widget
        new_text = text_widget.get(1.0, tk.END)
        cursor_pos = text_widget.index(tk.INSERT)
        self.last_cursor_positions[filename] = cursor_pos
        print(f"Metin değişikliği gönderiliyor: {filename} - İmleç: {cursor_pos}")
        self.client_socket.send(create_message("EDIT", f"{filename}||{new_text}").encode())

    def get_text_widget(self, filename):
        """Belirli bir dosya için text widget'ı döndürür"""
        if filename in self.text_widgets:
            return self.text_widgets[filename]
        return None

    def update_text_content(self, text_widget, new_text, filename):
        if self.is_updating:
            return
            
        self.is_updating = True
        try:
            print(f"Metin güncelleniyor: {filename}")
            # Mevcut imleç pozisyonunu kaydet
            cursor_pos = text_widget.index(tk.INSERT)
            print(f"Mevcut imleç pozisyonu: {cursor_pos}")
            
            # Metni güncelle
            text_widget.delete(1.0, tk.END)
            text_widget.insert(tk.END, new_text)
            
            # İmleç pozisyonunu geri yükle
            if filename in self.last_cursor_positions:
                saved_pos = self.last_cursor_positions[filename]
                print(f"Kaydedilmiş imleç pozisyonu: {saved_pos}")
                text_widget.mark_set(tk.INSERT, saved_pos)
                text_widget.see(saved_pos)
            else:
                print(f"Kaydedilmiş imleç pozisyonu bulunamadı, mevcut pozisyon kullanılıyor: {cursor_pos}")
                text_widget.mark_set(tk.INSERT, cursor_pos)
                text_widget.see(cursor_pos)
        finally:
            self.is_updating = False

    def update_active_editors_display(self, filename):
        if filename in self.edit_windows:
            window = self.edit_windows[filename]
            editors = self.active_editors.get(filename, [])
            if editors:
                window.title(f"Düzenle: {filename} (Aktif düzenleyiciler: {', '.join(editors)})")
            else:
                window.title(f"Düzenle: {filename}")

    def listen_server(self):
        while True:
            try:
                msg = self.client_socket.recv(1024).decode()
                if not msg:
                    break
                    
                msg_type, content = parse_message(msg)
                print(f"Sunucudan gelen mesaj: {msg_type} - {content[:50]}...")
                
                if msg_type == "UPDATE":
                    filename, new_text = content.split("||", 1)
                    print(f"Güncelleme alındı: {filename}")
                    text_widget = self.get_text_widget(filename)
                    if text_widget:
                        print(f"Deneme 1: Metin güncelleniyor: {filename}")
                        self.update_text_content(text_widget, new_text, filename)
                        print(f"Deneme 2: Metin güncellendi: {filename}")
                elif msg_type == "FILES":
                    self.show_file_list(content)
                elif msg_type == "INFO":
                    messagebox.showinfo("Bilgi", content)
                elif msg_type == "CONTENT":
                    filename, file_content = content.split("||", 1)
                    print(f"Dosya içeriği alındı: {filename}")
                    text_widget = self.get_text_widget(filename)
                    if text_widget:
                        print(f"İlk içerik yükleniyor: {filename}")
                        self.update_text_content(text_widget, file_content, filename)
                        print(f"İlk içerik yüklendi: {filename}")
                elif msg_type == "ACTIVE_EDITORS":
                    filename, editors = content.split("||", 1)
                    if editors:
                        self.active_editors[filename] = editors.split(",")
                    else:
                        self.active_editors[filename] = []
                    print(f"Aktif düzenleyiciler güncellendi: {filename} - {self.active_editors[filename]}")
                    self.update_active_editors_display(filename)
                    
            except Exception as e:
                print(f"Sunucu dinleme hatası: {str(e)}")
                break
    
    def display_content(self, filename, content):
        self.text_area.config(state='normal')
        self.text_area.delete(1.0, tk.END)
        self.text_area.insert(tk.END, f"{filename}\n\n{content}")
        self.text_area.config(state='disabled')
        self.status_bar.config(text=f"{filename} güncellendi")
    
    def show_file_list(self, files):
        file_list = files.split(',')
        selected = simpledialog.askstring("Dosya Seç", "Düzenlemek için dosya adı girin:\n\n" + "\n".join(file_list))
        if selected:
            self.edit_file(selected)
    
    def request_file_list(self):
        self.client_socket.send(create_message("FILES").encode())
    
    def edit_file(self, filename=None):
        if not filename:
            filename = simpledialog.askstring("Dosya Adı", "Düzenlemek istediğiniz dosya adını girin:")
            if not filename:
                return
                
        if filename in self.edit_windows:
            self.edit_windows[filename].lift()
            return

        edit_window = tk.Toplevel(self.root)
        edit_window.title(f"Düzenle: {filename}")
        self.edit_windows[filename] = edit_window
        
        # Text widget'ı oluştur ve referansını sakla
        text_area = scrolledtext.ScrolledText(edit_window, wrap=tk.WORD)
        text_area.pack(expand=True, fill='both')
        self.text_widgets[filename] = text_area
        
        # Metin değişikliği olayını dinle
        text_area.bind('<KeyRelease>', lambda e: self.on_text_change(e, filename))
        
        # Sunucudan dosya içeriğini iste
        print(f"Dosya içeriği isteniyor: {filename}")
        self.client_socket.send(create_message("GET", filename).encode())
        
        def on_window_close():
            print(f"Dosya düzenleme kapatılıyor: {filename}")
            self.client_socket.send(create_message("CLOSE_EDIT", filename).encode())
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
        self.client_socket.close()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = TextEditorClient(root)
    root.mainloop() 