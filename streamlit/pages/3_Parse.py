import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

import requests as _req
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv
from styles import apply_theme

load_dotenv()

st.set_page_config(page_title="Parse", page_icon="🔍", layout="wide")
apply_theme()

_PARSE_URL   = os.getenv("PARSE_URL", "").rstrip("/")
_PARSE_KEY   = os.getenv("PARSE_API_KEY", "")
_PROXY_PORT  = int(os.getenv("PARSE_PROXY_PORT", "8888"))
_PROXY_STARTED = False


class _ProxyHandler(BaseHTTPRequestHandler):
    def _forward(self, method):
        target  = _PARSE_URL + self.path
        headers = {
            "Authorization": f"Bearer {_PARSE_KEY}",
            "Host": _PARSE_URL.removeprefix("https://").removeprefix("http://"),
        }
        for h in ("Accept", "Accept-Encoding", "Content-Type", "Referer", "User-Agent"):
            if h in self.headers:
                headers[h] = self.headers[h]

        body = None
        if method in ("POST", "PUT", "PATCH"):
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length else None

        try:
            resp = _req.request(method, target, headers=headers, data=body,
                                timeout=30, stream=True, verify=True)
            self.send_response(resp.status_code)
            for k, v in resp.headers.items():
                if k.lower() in ("transfer-encoding", "connection", "content-encoding"):
                    continue
                self.send_header(k, v)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            for chunk in resp.iter_content(8192):
                self.wfile.write(chunk)
        except Exception:
            self.send_response(502)
            self.end_headers()

    def do_GET(self):     self._forward("GET")
    def do_POST(self):    self._forward("POST")
    def do_PUT(self):     self._forward("PUT")
    def do_DELETE(self):  self._forward("DELETE")
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def log_message(self, *args):
        pass


def _ensure_proxy():
    global _PROXY_STARTED
    if _PROXY_STARTED:
        return
    try:
        server = HTTPServer(("0.0.0.0", _PROXY_PORT), _ProxyHandler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        _PROXY_STARTED = True
    except OSError:
        _PROXY_STARTED = True  # já em execução


if not _PARSE_URL or not _PARSE_KEY:
    st.error("Define PARSE_URL e PARSE_API_KEY no .env")
    st.stop()

_ensure_proxy()

col1, col2 = st.columns([8, 1])
with col2:
    st.link_button("Abrir ↗", _PARSE_URL, use_container_width=True)

components.iframe(f"http://localhost:8503", height=900, scrolling=True)
