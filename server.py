import socket
import threading
import os
from protocol import create_message, parse_message

HOST = 'localhost'
PORT = 12345
clients = {}
documents = {}  # dosya_adı -> içerik
active_editors = {}  # dosya_adı -> set(username) şeklinde aktif düzenleyiciler

LOCK = threading.Lock()

def load_documents():
    if not os.path.exists("documents"):
        os.makedirs("documents")
    for filename in os.listdir("documents"):
        with open(f"documents/{filename}", "r", encoding="utf-8") as f:
            documents[filename] = f.read()

def save_document(filename):
    with open(f"documents/{filename}", "w", encoding="utf-8") as f:
        f.write(documents[filename])

def broadcast_update(filename, new_text, exclude_username=None):
    print(f"Değişiklik gönderiliyor: {filename} - {new_text}")
    """Belirli bir dosyadaki değişikliği tüm aktif düzenleyicilere gönder"""
    if filename in active_editors:
        print(f"Aktif düzenleyiciler: {active_editors[filename]}")
        for username, conn in clients.items():
            if username != exclude_username and username in active_editors[filename]:
                try:
                    print(f"Güncelleme gönderiliyor: {username}")
                    conn.send(create_message("UPDATE", f"{filename}||{new_text}").encode())
                except:
                    print(f"{username} kullanıcısına güncelleme gönderilemedi")

def handle_client(conn, addr):
    username = ""
    try:
        print(f"Yeni bağlantı: {addr}")
        while True:
            msg = conn.recv(1024).decode()
            if not msg:
                print(f"Bağlantı kapatıldı: {username or addr}")
                break
            msg_type, content = parse_message(msg)
            print(f"Gelen mesaj [{username or addr}]: {msg_type} - {content[:50]}...")

            if msg_type == "HELLO":
                username = content
                clients[username] = conn
                conn.send(create_message("INFO", "Hoşgeldin, " + username).encode())
                print(f"Kullanıcı giriş yaptı: {username}")

            elif msg_type == "FILES":
                file_list = ",".join(documents.keys())
                conn.send(create_message("FILES", file_list).encode())
                print(f"{username} dosya listesi istedi")

            elif msg_type == "EDIT":
                filename, new_text = content.split("||", 1)
                with LOCK:
                    documents[filename] = new_text
                    save_document(filename)
                print(f"{username} {filename} dosyasını güncelledi")
                # Değişikliği tüm aktif düzenleyicilere gönder
                broadcast_update(filename, new_text, username)

            elif msg_type == "GET":
                filename = content
                with LOCK:
                    if filename in documents:
                        file_content = documents[filename]
                        conn.send(create_message("CONTENT", f"{filename}||{file_content}").encode())
                        # Aktif düzenleyicilere ekle
                        if filename not in active_editors:
                            active_editors[filename] = set()
                        active_editors[filename].add(username)
                        print(f"Aktif düzenleyiciler güncellendi: {active_editors[filename]}")
                        # Diğer kullanıcılara aktif düzenleyici bilgisini gönder
                        for user, cl in clients.items():
                            if user != username:
                                try:
                                    cl.send(create_message("ACTIVE_EDITORS", f"{filename}||{','.join(active_editors[filename])}").encode())
                                except:
                                    print(f"{user} kullanıcısına aktif düzenleyici bilgisi gönderilemedi")
                    else:
                        # Dosya yoksa boş içerikle oluştur
                        documents[filename] = ""
                        save_document(filename)
                        conn.send(create_message("CONTENT", f"{filename}||").encode())
                        if filename not in active_editors:
                            active_editors[filename] = set()
                        active_editors[filename].add(username)
                print(f"{username} {filename} dosyasını istedi")

            elif msg_type == "CLOSE_EDIT":
                filename = content
                with LOCK:
                    if filename in active_editors and username in active_editors[filename]:
                        active_editors[filename].remove(username)
                        if not active_editors[filename]:
                            del active_editors[filename]
                        # Diğer kullanıcılara aktif düzenleyici bilgisini gönder
                        for user, cl in clients.items():
                            if user != username:
                                try:
                                    if filename in active_editors:
                                        cl.send(create_message("ACTIVE_EDITORS", f"{filename}||{','.join(active_editors[filename])}").encode())
                                    else:
                                        cl.send(create_message("ACTIVE_EDITORS", f"{filename}||").encode())
                                except:
                                    print(f"{user} kullanıcısına aktif düzenleyici bilgisi gönderilemedi")

    finally:
        if username in clients:
            del clients[username]
            # Kullanıcının aktif olduğu tüm dosyalardan çıkar
            for filename in list(active_editors.keys()):
                if username in active_editors[filename]:
                    active_editors[filename].remove(username)
                    if not active_editors[filename]:
                        del active_editors[filename]
            print(f"{username} bağlantıyı kapattı")
        conn.close()

def main():
    load_documents()
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((HOST, PORT))
    server.listen()
    print("Sunucu dinleniyor...")

    while True:
        conn, addr = server.accept()
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

if __name__ == "__main__":
    main()
