import socket
import threading
from protocol import create_message, parse_message

HOST = 'localhost'
PORT = 12345

def listen_server(sock):
    while True:
        try:
            msg = sock.recv(1024).decode()
            msg_type, content = parse_message(msg)
            if msg_type == "UPDATE":
                filename, new_text = content.split("||", 1)
                print(f"\n{filename} güncellendi:\n{new_text}\n> ", end="")
            elif msg_type == "FILES":
                print("Mevcut dosyalar:", content)
            elif msg_type == "INFO":
                print(content)
        except:
            break

def main():
    username = input("Kullanıcı adınızı girin: ")
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect((HOST, PORT))
    client.send(create_message("HELLO", username).encode())

    threading.Thread(target=listen_server, args=(client,), daemon=True).start()

    while True:
        cmd = input("> ").strip()
        if cmd == "files":
            client.send(create_message("FILES").encode())
        elif cmd.startswith("edit "):
            _, filename = cmd.split(" ", 1)
            print(f"{filename} için yeni içerik girin. Bitirmek için boş satır girin:")
            lines = []
            while True:
                line = input()
                if line == "":
                    break
                lines.append(line)
            new_text = "\n".join(lines)
            client.send(create_message("EDIT", f"{filename}||{new_text}").encode())
        elif cmd == "exit":
            break

if __name__ == "__main__":
    main()
