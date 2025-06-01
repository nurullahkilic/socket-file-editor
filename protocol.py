def create_message(type, content=""):
    return f"{type}:{content}"

def parse_message(msg):
    if ':' not in msg:
        return msg, ""
    type, content = msg.split(':', 1)
    return type, content
