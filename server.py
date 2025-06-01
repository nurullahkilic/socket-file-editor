import socket
import threading
import os
from protocol import create_message, parse_message

HOST = 'localhost'
PORT = 12345
clients = {}
documents = {}  # dosya_adı -> içerik

LOCK = threading.Lock()

def load_documents():
    for filename in os.listdir("documents"):
        with open(f"documents/{filename}", "r", encoding="utf-8") as f:
            documents[filename] = f.read()

def save_document(filename):
    with open(f"documents/{filename}", "w", encoding="utf-8") as f:
        f.write(documents[filename])

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
                # tüm istemcilere değişikliği gönder
                for user, cl in clients.items():
                    if user != username:
                        try:
                            cl.send(create_message("UPDATE", f"{filename}||{new_text}").encode())
                        except:
                            print(f"{user} kullanıcısına güncelleme gönderilemedi")

            elif msg_type == "GET":
                filename = content
                with LOCK:
                    if filename in documents:
                        # Dosya içeriğini gönderirken başında boşluk karakteri kalmamasına dikkat edelim
                        file_content = documents[filename].strip()
                        conn.send(create_message("CONTENT", f"{filename}||{file_content}").encode())
                    else:
                        conn.send(create_message("INFO", f"{filename} dosyası bulunamadı").encode())
                print(f"{username} {filename} dosyasını istedi")

    finally:
        if username in clients:
            del clients[username]
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
