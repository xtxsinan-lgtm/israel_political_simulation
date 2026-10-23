#!/usr/bin/env python3
"""Local dev server for the web prototype (web/).

  python3 tools/serve_web.py            # http://127.0.0.1:8777/
  python3 tools/serve_web.py --port 9000

Threaded, sends no-cache headers and correct MIME types for ES modules / wasm.
Run `python3 tools/build_web.py` first (or pass --build).
"""

import argparse
import functools
import http.server
import socketserver
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".js": "text/javascript; charset=utf-8",
        ".mjs": "text/javascript; charset=utf-8",
        ".json": "application/json; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".html": "text/html; charset=utf-8",
        ".wasm": "application/wasm",
        ".svg": "image/svg+xml",
    }

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def log_message(self, fmt: str, *args) -> None:  # quieter console
        if args and str(args[1]).startswith(("4", "5")):
            super().log_message(fmt, *args)


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    request_queue_size = 128


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8777)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--build", action="store_true", help="run tools/build_web.py first")
    args = ap.parse_args()
    if args.build or not (WEB / "build" / "sim_bundle.json").exists():
        subprocess.run([sys.executable, str(ROOT / "tools" / "build_web.py")], check=True)
    handler = functools.partial(Handler, directory=str(WEB))
    with Server((args.host, args.port), handler) as httpd:
        print(f"Serving web prototype at http://{args.host}:{args.port}/  (self-test: /selftest.html)", flush=True)
        httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
