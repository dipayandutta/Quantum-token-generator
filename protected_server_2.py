from http.server import BaseHTTPRequestHandler, HTTPServer
import time
from collections import deque
import subprocess

TOKEN_FILE = "/etc/myservice.token"
FAILED_WINDOW = 10      # seconds
FAILED_THRESHOLD = 5    # attempts

failures = deque()

def load_token():
    with open(TOKEN_FILE) as f:
        return f.read().strip()

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        global failures
        auth = self.headers.get("Authorization")
        token = load_token()

        now = time.time()

        # Clean old failures
        while failures and failures[0] < now - FAILED_WINDOW:
            failures.popleft()

        if auth != f"Bearer {token}":
            failures.append(now)

            # Emergency condition
            if len(failures) >= FAILED_THRESHOLD:
                print("[ALERT] Attack detected — triggering quantum lockdown")
                subprocess.run(["./rotate_token.sh"])
                failures.clear()

            self.send_response(401)
            self.end_headers()
            self.wfile.write(b"Unauthorized\n")
            return

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Access granted\n")

HTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
