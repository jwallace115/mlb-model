#!/usr/bin/env python3
"""Tiny HTTP service for the "Check now" button on the picks page.

Bound to 127.0.0.1:8787 (Caddy reverse-proxies /api/check/* and /api/status/*).
Two routes:
  POST /check/<sport>  → start a watcher sweep if no run in the last 10 min
  GET  /status/<sport> → last run summary from status/check_now_<sport>.json

The service never touches the API key and runs nothing but window_watch.py.
Installs NOTHING new. P71 decision. OPS-CAD3 Item 2.
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

ROOT = Path(os.environ.get("MLB_REPO_ROOT") or Path(__file__).resolve().parent.parent.parent)
PY = sys.executable
GUARD_MINUTES = 10
VALID_SPORTS = {"nfl", "ncaaf"}
BIND = ("127.0.0.1", 8787)


def _status_path(sport, root=ROOT):
    return root / "status" / f"check_now_{sport}.json"


def _load_status(sport, root=ROOT):
    p = _status_path(sport, root)
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            pass
    return {}


def write_check_status(sport, data, root=ROOT):
    """Called by window_watch at the end of every run."""
    p = _status_path(sport, root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=1) + "\n")


class Handler(BaseHTTPRequestHandler):

    def _sport_from_path(self):
        parts = self.path.strip("/").split("/")
        if len(parts) >= 2:
            s = parts[-1].lower()
            if s in VALID_SPORTS:
                return s
        return None

    def do_POST(self):
        if not self.path.startswith("/check/"):
            self._send(404, {"error": "not found"})
            return
        sport = self._sport_from_path()
        if not sport:
            self._send(400, {"error": "invalid sport"})
            return

        # Guard (P76): only a BUTTON run in the last 10 min counts — the cron tick every 15 min must not block the button
        st = _load_status(sport)
        if st.get("started_utc") and st.get("requested_by") == "button":
            try:
                started = datetime.fromisoformat(st["started_utc"].replace("Z", "+00:00"))
                if (datetime.now(timezone.utc) - started).total_seconds() < GUARD_MINUTES * 60:
                    self._send(200, {"status": "recent", "last": st.get("started_utc")})
                    return
            except Exception:
                pass

        # Start detached watcher
        now = datetime.now(timezone.utc)
        cmd = [
            PY, str(ROOT / "shared" / "pipeline" / "window_watch.py"),
            "--once", "--sport", sport, "--mode", "sweep",
            "--requested-by", "button",
        ]
        try:
            subprocess.Popen(cmd, cwd=str(ROOT),
                             start_new_session=True,
                             stdout=open(f"/root/logs/check_now_{sport}.log", "a"),
                             stderr=subprocess.STDOUT)
        except Exception as e:
            self._send(500, {"error": str(e)[:200]})
            return

        # Write a pending status
        write_check_status(sport, {
            "started_utc": now.isoformat(),
            "finished_utc": None,
            "mode": "sweep",
            "requested_by": "button",
            "result": "running",
        })
        self._send(200, {"status": "started", "at": now.isoformat()})

    def do_GET(self):
        if not self.path.startswith("/status/"):
            self._send(404, {"error": "not found"})
            return
        sport = self._sport_from_path()
        if not sport:
            self._send(400, {"error": "invalid sport"})
            return
        st = _load_status(sport)
        self._send(200, st if st else {"status": "no runs yet"})

    def _send(self, code, data):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        # Suppress default stderr logging
        pass


def main():
    print(f"check_now_service starting on {BIND[0]}:{BIND[1]}")
    server = HTTPServer(BIND, Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()


if __name__ == "__main__":
    main()
