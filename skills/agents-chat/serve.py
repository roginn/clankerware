#!/usr/bin/env python3
"""
Serve the agents-chat transcript viewer with live auto-refresh.

Running this avoids the file:// reload bugs (stale File handles, etc.) by
serving index.html and the transcript/peer files over localhost. The viewer
detects the http origin and fetches fresh content reliably.

Usage:
    python3 serve.py --cwd /path/to/repo [--port 8765]
"""

from __future__ import annotations

import argparse
import http.server
import socketserver
import sys
import webbrowser
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
VIEWER_HTML = SCRIPT_DIR / "index.html"


def make_handler(cwd: Path):
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path in ("/", "/index.html"):
                self._serve(VIEWER_HTML, "text/html; charset=utf-8")
            elif path == "/transcript.md":
                self._serve(cwd / "transcript.md", "text/markdown; charset=utf-8")
            elif path == "/peer_message.md":
                self._serve(cwd / "peer_message.md", "text/markdown; charset=utf-8")
            else:
                self.send_error(404, f"not found: {path}")

        def _serve(self, fpath: Path, mime: str):
            if not fpath.exists():
                self.send_error(404, f"not found: {fpath.name}")
                return
            body = fpath.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            return  # quiet

    return Handler


def main() -> int:
    ap = argparse.ArgumentParser(description="Serve the agents-chat viewer at localhost.")
    ap.add_argument("--cwd", default=".", help="Dir containing transcript.md / peer_message.md")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-open", action="store_true", help="Don't auto-open a browser")
    args = ap.parse_args()

    cwd = Path(args.cwd).expanduser().resolve()
    if not cwd.is_dir():
        sys.stderr.write(f"--cwd does not exist: {cwd}\n")
        return 2
    if not VIEWER_HTML.exists():
        sys.stderr.write(f"viewer not found: {VIEWER_HTML}\n")
        return 2

    handler = make_handler(cwd)
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", args.port), handler) as srv:
        url = f"http://127.0.0.1:{args.port}/"
        print(f"serving transcript from {cwd}")
        print(f"viewer:  {VIEWER_HTML}")
        print(f"open:    {url}")
        print("(ctrl-c to stop)")
        if not args.no_open:
            webbrowser.open(url)
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            print("\nstopping")
    return 0


if __name__ == "__main__":
    sys.exit(main())
