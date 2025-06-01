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
            username = simpledialog.askstring("Kullanıcı Adı", "Kullanıcı adınızı girin:")
            if not username:
                self.root.destroy()
                return
                
            self.client_socket.connect((HOST, PORT))
            self.client_socket.send(create_message("HELLO", username).encode())
            
            # Sunucu dinleme thread'i
            threading.Thread(target=self.listen_server, daemon=True).start()
            self.status_bar.config(text=f"Bağlantı kuruldu - Kullanıcı: {username}")
            
        except Exception as e:
            messagebox.showerror("Hata", f"Sunucuya bağlanılamadı: {str(e)}")
            self.root.destroy()
    
    def listen_server(self):
        while True:
            try:
                msg = self.client_socket.recv(1024).decode()
                if not msg:
                    break
                    
                msg_type, content = parse_message(msg)
                
                if msg_type == "UPDATE":
                    filename, new_text = content.split("||", 1)
                    self.display_content(filename, new_text)
                elif msg_type == "FILES":
                    self.show_file_list(content)
                elif msg_type == "INFO":
                    messagebox.showinfo("Bilgi", content)
                elif msg_type == "CONTENT":
                    filename, file_content = content.split("||", 1)
                    print(f"Gelen dosya: {filename}")
                    
                    def find_text_widget(widget):
                        if isinstance(widget, tk.Text):
                            return widget
                        for child in widget.winfo_children():
                            result = find_text_widget(child)
                            if result:
                                return result
                        return None

                    for window in self.root.winfo_children():
                        if isinstance(window, tk.Toplevel) and (filename in window.title() or filename == window.title()):
                            print(f"Eşleşen pencere bulundu: {window.title()}")
                            text_widget = find_text_widget(window)
                            if text_widget:
                                text_widget.delete(1.0, tk.END)
                                text_widget.insert(tk.END, file_content)
                                text_widget.update_idletasks()
                            else:
                                print("Text widget bulunamadı!")
                            break
                    else:
                        print(f"Açık pencere bulunamadı. Ana alana yazılıyor: {filename}")
                        self.display_content(filename, file_content)


                    
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
                
        edit_window = tk.Toplevel(self.root)
        edit_window.title(f"Düzenle: {filename}")
        
        text_area = scrolledtext.ScrolledText(edit_window, wrap=tk.WORD)
        text_area.pack(expand=True, fill='both')
        
        # Sunucudan dosya içeriğini iste
        self.client_socket.send(create_message("GET", filename).encode())
        
        def save_changes():
            new_text = text_area.get(1.0, tk.END).strip()
            self.client_socket.send(create_message("EDIT", f"{filename}||{new_text}").encode())
            edit_window.destroy()
            messagebox.showinfo("Başarılı", "Değişiklikler kaydedildi!")
        
        save_button = tk.Button(edit_window, text="Kaydet", command=save_changes)
        save_button.pack()
    
    def exit_app(self):
        self.client_socket.close()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = TextEditorClient(root)
    root.mainloop() 