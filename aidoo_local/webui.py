"""Interfaz web de control/pruebas para Aidoo Local. Servidor HTTP integrado (sin
dependencias). Sirve un panel y una pequeña API REST sobre el AidooServer. Compatible con
el ingress de Home Assistant (usa rutas relativas)."""
from __future__ import annotations
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


def _make_handler(server):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _send(self, code, body, ctype="application/json; charset=utf-8"):
            b = body.encode("utf-8") if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            try:
                self.wfile.write(b)
            except Exception:
                pass

        def _path(self):
            return self.path.split("?", 1)[0].rstrip("/") or "/"

        def do_GET(self):
            p = self._path()
            if p in ("/", "/index.html"):
                try:
                    with open(os.path.join(STATIC, "index.html"), "rb") as f:
                        self._send(200, f.read(), "text/html; charset=utf-8")
                except Exception:
                    self._send(500, "index.html no encontrado", "text/plain")
            elif p == "/api/state":
                st = server.state.to_dict()
                st["connected"] = server.connected
                st["raw"] = server.state.raw
                self._send(200, json.dumps(st))
            else:
                self._send(404, json.dumps({"error": "not found"}))

        def do_POST(self):
            ln = int(self.headers.get("Content-Length", "0") or 0)
            raw = self.rfile.read(ln) if ln else b"{}"
            try:
                data = json.loads(raw or b"{}")
            except Exception:
                data = {}
            p = self._path()
            try:
                if p == "/api/command":
                    act = data.get("action")
                    if act == "power":
                        server.set_power(bool(data.get("value")))
                    elif act == "mode":
                        server.set_mode(str(data.get("value")))
                    elif act == "setpoint":
                        server.set_setpoint(float(data.get("value")))
                    elif act == "fan":
                        server.set_fan(str(data.get("value")))
                    else:
                        return self._send(400, json.dumps({"ok": False, "error": "acción desconocida"}))
                    self._send(200, json.dumps({"ok": True}))
                elif p == "/api/raw":
                    server.send_raw(str(data.get("hex", "")))
                    self._send(200, json.dumps({"ok": True}))
                else:
                    self._send(404, json.dumps({"error": "not found"}))
            except Exception as e:
                self._send(200, json.dumps({"ok": False, "error": str(e)}))

    return Handler


def start_webui(server, port=8098, logger=print):
    httpd = ThreadingHTTPServer(("0.0.0.0", port), _make_handler(server))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    logger(f"[webui] panel web en http://0.0.0.0:{port}")
    return httpd
