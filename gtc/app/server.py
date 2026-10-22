"""Local web server (UI-1): a JSON API over gtc/app/service.py and the static frontend in web/.

Standard library only (http.server), bound to 127.0.0.1: the account data never leaves the machine.

  GET  /api/status                    loading progress and timings
  GET  /api/dashboard                 what to care about right now
  GET  /api/account                   account summary and plan
  GET  /api/characters                catalog, owned and unowned
  GET  /api/characters/<name>         one character
  POST /api/team   {"lineup": [...]}  Team Builder: any legal team
  GET  /api/teams?overlap=1|0         recommended teams (overlap allowed) or the account plan (no overlap)
  GET  /api/pulls                     account improvements, in confidence groups
  GET  /api/whatif/<name>             what pulling this character changes
"""
from __future__ import annotations

import json
import mimetypes
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

from gtc import ROOT
from gtc.app.service import service

WEB_DIR = ROOT / "web"


def _ready():
    s = service()
    if not s.loaded:
        return None, {"error": "loading", "status": s.status()}
    return s, None


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # quiet
        pass

    def _send(self, code: int, body, ctype: str = "application/json") -> None:
        data = json.dumps(body, default=_jsonable).encode() if ctype == "application/json" else body
        self.send_response(code)
        self.send_header("Content-Type", ctype + ("; charset=utf-8" if ctype.startswith(("application/json", "text/")) else ""))
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        url = urlparse(self.path)
        if not url.path.startswith("/api/"):
            return self._static(url.path)
        try:
            parts = [unquote(p) for p in url.path.split("/")[2:] if p]
            if parts == ["status"]:
                return self._send(200, service().status())
            s, wait = _ready()
            if wait:
                return self._send(503, wait)
            q = parse_qs(url.query)
            if parts == ["dashboard"]:
                return self._send(200, s.dashboard())
            if parts == ["account"]:
                return self._send(200, s.get_account())
            if parts == ["characters"]:
                return self._send(200, s.get_characters())
            if len(parts) == 2 and parts[0] == "characters":
                return self._send(200, s.get_character(parts[1]))
            if parts == ["teams"]:
                overlap = q.get("overlap", ["1"])[0] != "0"
                return self._send(200, s.recommended_teams() if overlap else s.recommended_plan())
            if parts == ["pulls"]:
                return self._send(200, s.recommended_pulls())
            if len(parts) == 2 and parts[0] == "whatif":
                return self._send(200, s.what_if(parts[1]))
            return self._send(404, {"error": "not found"})
        except KeyError as e:
            return self._send(404, {"error": f"unknown: {e}"})
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            return self._send(500, {"error": str(e)})

    def do_POST(self):
        url = urlparse(self.path)
        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n) or b"{}")
            s, wait = _ready()
            if wait:
                return self._send(503, wait)
            if url.path == "/api/team":
                lineup = body.get("lineup") or []
                if not isinstance(lineup, list) or not all(isinstance(x, str) for x in lineup):
                    return self._send(400, {"error": "lineup must be a list of character names"})
                return self._send(200, s.evaluate_team(lineup, substitutions=body.get("substitutions", True)))
            return self._send(404, {"error": "not found"})
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            return self._send(500, {"error": str(e)})

    def _static(self, path: str):
        rel = path.lstrip("/") or "index.html"
        f = (WEB_DIR / rel).resolve()
        if WEB_DIR.resolve() not in f.parents and f != WEB_DIR.resolve() or not f.is_file():
            f = WEB_DIR / "index.html"
        ctype = mimetypes.guess_type(str(f))[0] or "application/octet-stream"
        if f.suffix == ".js":
            ctype = "text/javascript"
        self._send(200, f.read_bytes(), ctype)


def _jsonable(o):
    if isinstance(o, (set, frozenset)):
        return sorted(o)
    if hasattr(o, "value") and hasattr(o, "sd"):
        return {"expected": round(o.value, 1), "sd": round(o.sd, 1), "tier": getattr(o, "tier", None)}
    return str(o)


def serve(port: int = 8765, open_browser: bool = False) -> None:
    threading.Thread(target=service().load, daemon=True).start()
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Genshin theorycraft: http://127.0.0.1:{port}  (loading your account in the background)")
    if open_browser:
        import webbrowser

        webbrowser.open(f"http://127.0.0.1:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
