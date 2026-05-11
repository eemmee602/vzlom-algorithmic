#!/usr/bin/env python3
"""Vzlom Mobile — Serveur web minimal pour l'interface mobile Vzlom"""
import http.server
import os

PORT = 8766
HTML_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mobile_index.html")

class MobileHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            try:
                with open(HTML_FILE, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(content)
            except FileNotFoundError:
                self.send_error(404, "Mobile companion not found")
        else:
            self.send_error(404)
    
    def log_message(self, format, *args):
        pass  # silencieux

if __name__ == "__main__":
    print(f"Vzlom Mobile — http://0.0.0.0:{PORT}/")
    server = http.server.HTTPServer(("0.0.0.0", PORT), MobileHandler)
    server.serve_forever()
