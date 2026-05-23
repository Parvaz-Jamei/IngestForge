from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest


class Handler(BaseHTTPRequestHandler):
    html = b"<html><head><title>Example Article</title><meta property='og:image' content='/image.png'></head><body><article><h1>Example Article</h1><p>This is a long enough example article for IngestForge extraction. It contains evidence text, source details, and enough content for a package.</p></article></body></html>"
    image = b"\x89PNG\r\n\x1a\n" + b"0" * 128

    def do_GET(self):
        if self.path == "/robots.txt":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"User-agent: *\nAllow: /\n")
            return
        if self.path == "/image.png":
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.end_headers()
            self.wfile.write(self.image)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(self.html)

    def log_message(self, *args):
        pass


@pytest.fixture
def local_server():
    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
