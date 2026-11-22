"""Single instance: a second launch (e.g. from the Chrome button) hands its links
to the running app over a local socket and exits."""
import json
import secrets
import socket
import threading
import time

from .paths import DATA_DIR

PORT = 48765
TOKEN_FILE = DATA_DIR / "ipc.token"


def send_to_running(message):
    """True if a running instance accepted the message."""
    try:
        token = TOKEN_FILE.read_text().strip()
        with socket.create_connection(("127.0.0.1", PORT), timeout=2) as s:
            s.sendall((json.dumps({"token": token, **message}) + "\n").encode())
            s.settimeout(3)
            return s.recv(8).startswith(b"ok")
    except OSError:
        return False


class Server:
    def __init__(self, on_message):
        self.on_message = on_message
        self.sock = None
        self.token = secrets.token_hex(16)

    def start(self, wait=0.0):
        """Bind the port. `wait` > 0 keeps retrying (used right after a restart)."""
        deadline = time.time() + wait
        while True:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            try:
                s.bind(("127.0.0.1", PORT))
                break
            except OSError:
                s.close()
                if time.time() >= deadline:
                    return False
                time.sleep(0.3)
        s.listen(8)
        self.sock = s
        try:
            TOKEN_FILE.write_text(self.token)
        except OSError:
            pass
        threading.Thread(target=self._serve, daemon=True).start()
        return True

    def _serve(self):
        while True:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            with conn:
                try:
                    conn.settimeout(3)
                    data = b""
                    while b"\n" not in data and len(data) < 65536:
                        chunk = conn.recv(4096)
                        if not chunk:
                            break
                        data += chunk
                    msg = json.loads(data.split(b"\n")[0])
                    if not secrets.compare_digest(str(msg.pop("token", "")), self.token):
                        continue
                    self.on_message(msg)
                    conn.sendall(b"ok")
                except Exception:
                    pass

    def close(self):
        if self.sock:
            try:
                self.sock.close()
            except OSError:
                pass
