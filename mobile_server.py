#!/usr/bin/env python3
"""
Vzlom Mobile — Serveur léger sur le port 8766.
Sert mobile_index.html et proxifie les appels API vers le bridge (port 3456).
"""
import http.server, socketserver, os, json
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from http.client import HTTPConnection

PORT = 8766
BRIDGE_PORT = 3456
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

PROXY_PATHS = ("/api/", "/auth/", "/memory", "/bash", "/admin/")

HTML_FILES = {
    "/": "mobile_index.html",
    "/index.html": "mobile_index.html",
    "/mobile.html": "mobile_index.html",
    "/dex": "DEX_TLMN.html",
    "/dex.html": "DEX_TLMN.html",
    "/DEX_TLMN.html": "DEX_TLMN.html",
    "/mobile_v2": "mobile_v2.html",
    "/mobile_v2.html": "mobile_v2.html",
}

class MobileHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"
    log_message = lambda self, fmt, *args: None

    def do_GET(self):
        parsed_path = self.path.split("?")[0]

        # Proxy API vers le bridge
        if parsed_path.startswith(PROXY_PATHS):
            self._proxy_bridge()
            return

        # Fichiers statiques
        filename = HTML_FILES.get(parsed_path) or HTML_FILES.get("/")
        filepath = os.path.join(BASE_DIR, filename)

        if parsed_path == "/favicon.ico":
            fp = os.path.join(BASE_DIR, "favicon.ico")
            if os.path.exists(fp):
                with open(fp, "rb") as f:
                    data = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "image/x-icon")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            else:
                self.send_response(204)
                self.end_headers()
            return

        if not os.path.exists(filepath):
            self.send_error(404, "Not found")
            return

        with open(filepath, "rb") as f:
            content = f.read()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self):
        parsed_path = self.path.split("?")[0]
        if parsed_path.startswith(PROXY_PATHS):
            self._proxy_bridge()
        else:
            self.send_error(404)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def _proxy_bridge(self):
        """Proxy la requête vers le bridge sur le port 3456."""
        try:
            body = b""
            if "Content-Length" in self.headers:
                length = int(self.headers["Content-Length"])
                body = self.rfile.read(length)

            conn = HTTPConnection("127.0.0.1", BRIDGE_PORT, timeout=30)
            conn.request(
                self.command,
                self.path,
                body=body,
                headers={k: v for k, v in self.headers.items()
                         if k.lower() not in ("host", "connection")}
            )
            resp = conn.getresponse()

            # Lire tout le body du bridge (pour les réponses SSE, on stream)
            data = resp.read()
            conn.close()

            self.send_response(resp.status)
            for hdr, val in resp.getheaders():
                if hdr.lower() not in ("connection", "transfer-encoding"):
                    self.send_header(hdr, val)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(data)

        except Exception as e:
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": f"Bridge error: {str(e)}"}).encode())


if __name__ == "__main__":
    with socketserver.TCPServer(("0.0.0.0", PORT), MobileHandler) as httpd:
        print(f"[MOBILE] Vzlom Mobile sur le port {PORT}")
        httpd.serve_forever()