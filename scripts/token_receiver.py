"""One-shot local receiver for the ktalk session-token bookmarklet.

Run this, click the bookmarklet (see README) on a tab logged into your Talk
space, and it writes the token straight into .env's KTALK_SESSION_TOKEN line,
then exits. No DevTools console needed after the one-time bookmarklet setup.

Only accepts a POST whose Origin header matches KTALK_SPACE_URL (read from
.env) -- any other origin gets 403, so an unrelated open tab can't overwrite
your token file.
"""

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from dotenv import load_dotenv, dotenv_values  # noqa: E402

ENV_PATH = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(ENV_PATH)

SPACE_URL = os.environ.get("KTALK_SPACE_URL", "").strip().rstrip("/")
PORT = int(os.environ.get("KTALK_RECEIVER_PORT", "8765"))


def write_token(token: str) -> None:
    values = dotenv_values(ENV_PATH) if os.path.exists(ENV_PATH) else {}
    values["KTALK_SESSION_TOKEN"] = token
    lines = []
    seen = set()
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.rstrip("\n")
                key = stripped.split("=", 1)[0].strip() if "=" in stripped and not stripped.strip().startswith("#") else None
                if key == "KTALK_SESSION_TOKEN":
                    lines.append(f"KTALK_SESSION_TOKEN={token}\n")
                    seen.add(key)
                else:
                    lines.append(line if line.endswith("\n") else line + "\n")
    if "KTALK_SESSION_TOKEN" not in seen:
        lines.append(f"KTALK_SESSION_TOKEN={token}\n")
    tmp = ENV_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.writelines(lines)
    os.replace(tmp, ENV_PATH)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # keep stdout clean -- token/origin never get logged

    def do_POST(self):
        if self.path != "/ktalk-token":
            self.send_response(404)
            self.end_headers()
            return
        origin = self.headers.get("Origin", "")
        if not SPACE_URL or origin.rstrip("/") != SPACE_URL:
            self.send_response(403)
            self.end_headers()
            self.wfile.write(json.dumps({"ok": False, "message": "forbidden_origin"}).encode())
            print(f"Rejected POST from origin {origin!r} (expected {SPACE_URL!r})")
            return
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            data = json.loads(body)
            token = (data.get("token") or "").strip()
            expires_at = data.get("expiresAt")
        except (ValueError, AttributeError):
            token, expires_at = "", None
        if not token:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"ok": False, "message": "no token in body"}).encode())
            return
        write_token(token)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"ok": True, "expiresAt": expires_at, "path": ENV_PATH}).encode())
        print(f"Token saved to {ENV_PATH}" + (f" (expires {expires_at})" if expires_at else ""))
        self.server.done = True


def main():
    if not SPACE_URL:
        print("KTALK_SPACE_URL is not set in .env -- set it first.", file=sys.stderr)
        sys.exit(2)
    server = HTTPServer(("127.0.0.1", PORT), Handler)
    server.done = False
    print(f"Listening on http://127.0.0.1:{PORT}/ktalk-token for origin {SPACE_URL}")
    print("Click the bookmarklet on a tab logged into your Talk space now...")
    while not server.done:
        server.handle_request()


if __name__ == "__main__":
    main()
