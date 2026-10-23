#!/usr/bin/env python3
"""Headless-Chrome check for the web prototype using only the Python stdlib.

Launches the installed Chrome with --remote-debugging-port, drives it over the DevTools
protocol (minimal WebSocket client below), waits until document.title starts with
SELFTEST_ / E2E_, prints console output and the #log text, and optionally saves screenshots.

  python3 tools/web_e2e.py http://127.0.0.1:8777/selftest.html
  python3 tools/web_e2e.py http://127.0.0.1:8777/index.html?e2e=1 --shot /tmp/desk.png
  python3 tools/web_e2e.py URL --eval "js expression"   # print an expression after load
"""

import argparse
import base64
import json
import os
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
import urllib.request
from typing import Any, Dict, Optional

CHROME = os.environ.get("CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")


class WebSocket:
    def __init__(self, url: str) -> None:
        assert url.startswith("ws://")
        hostport, path = url[5:].split("/", 1)
        host, port = hostport.split(":")
        self.sock = socket.create_connection((host, int(port)))
        key = base64.b64encode(os.urandom(16)).decode()
        req = (
            f"GET /{path} HTTP/1.1\r\nHost: {hostport}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
        )
        self.sock.sendall(req.encode())
        resp = b""
        while b"\r\n\r\n" not in resp:
            resp += self.sock.recv(4096)
        if b" 101 " not in resp.split(b"\r\n", 1)[0]:
            raise RuntimeError(resp.decode(errors="replace"))
        self.buf = resp.split(b"\r\n\r\n", 1)[1]

    def send(self, text: str) -> None:
        data = text.encode()
        header = bytearray([0x81])
        n = len(data)
        if n < 126:
            header.append(0x80 | n)
        elif n < 65536:
            header.append(0x80 | 126)
            header += struct.pack(">H", n)
        else:
            header.append(0x80 | 127)
            header += struct.pack(">Q", n)
        mask = os.urandom(4)
        header += mask
        self.sock.sendall(bytes(header) + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

    def _read(self, n: int) -> bytes:
        while len(self.buf) < n:
            chunk = self.sock.recv(1 << 20)
            if not chunk:
                raise EOFError
            self.buf += chunk
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def recv(self) -> str:
        message = b""
        while True:
            b1, b2 = self._read(2)
            n = b2 & 0x7F
            if n == 126:
                n = struct.unpack(">H", self._read(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", self._read(8))[0]
            payload = self._read(n)
            message += payload
            if b1 & 0x80:
                return message.decode(errors="replace")


class Cdp:
    def __init__(self, ws: WebSocket) -> None:
        self.ws = ws
        self.next_id = 1
        self.events = []

    def call(self, method: str, params: Optional[Dict[str, Any]] = None, timeout: float = 60.0) -> Dict[str, Any]:
        mid = self.next_id
        self.next_id += 1
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        end = time.time() + timeout
        while time.time() < end:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == mid:
                if "error" in msg:
                    raise RuntimeError(msg["error"])
                return msg.get("result", {})
            self.events.append(msg)
        raise TimeoutError(method)

    def drain_console(self) -> None:
        for ev in self.events:
            m = ev.get("method")
            p = ev.get("params", {})
            if m == "Runtime.consoleAPICalled":
                args = " ".join(str(a.get("value", a.get("description", ""))) for a in p.get("args", []))
                print(f"[console.{p.get('type')}] {args}")
            elif m == "Runtime.exceptionThrown":
                d = p.get("exceptionDetails", {})
                print(f"[exception] {d.get('exception', {}).get('description', d.get('text'))}")
            elif m == "Log.entryAdded":
                e = p.get("entry", {})
                print(f"[log.{e.get('level')}] {e.get('text')} {e.get('url', '')}")
        self.events.clear()

    def eval(self, expr: str) -> Any:
        r = self.call("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True})
        return r.get("result", {}).get("value")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--shot", help="screenshot path (png)")
    ap.add_argument("--timeout", type=float, default=180)
    ap.add_argument("--eval", action="append", default=[], help="JS expression(s) to print after load")
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    ap.add_argument("--port", type=int, default=0, help="DevTools port (default: a free port)")
    args = ap.parse_args()

    port = args.port
    if not port:
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
    profile = tempfile.mkdtemp(prefix="chrome-e2e-")
    proc = subprocess.Popen(
        [CHROME, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
         f"--remote-debugging-port={port}", f"--user-data-dir={profile}",
         f"--window-size={args.width},{args.height}", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(100):
            try:
                tabs = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/json").read())
                page = next(t for t in tabs if t.get("type") == "page")
                break
            except Exception:  # noqa: BLE001
                time.sleep(0.1)
        else:
            print("chrome did not start")
            return 2
        cdp = Cdp(WebSocket(page["webSocketDebuggerUrl"]))
        cdp.call("Runtime.enable")
        cdp.call("Log.enable")
        cdp.call("Page.enable")
        cdp.call("Emulation.setDeviceMetricsOverride",
                 {"width": args.width, "height": args.height, "deviceScaleFactor": 1, "mobile": False})
        cdp.call("Page.navigate", {"url": args.url})
        start = time.time()
        title = ""
        while time.time() - start < args.timeout:
            title = cdp.eval("document.title") or ""
            cdp.drain_console()
            if title.startswith(("SELFTEST_", "E2E_")):
                break
            time.sleep(0.5)
        print(f"TITLE {title} after {time.time() - start:.1f}s")
        log = cdp.eval("(document.getElementById('log')||{}).textContent||''")
        if log:
            print(log)
        for expr in args.eval:
            print(f"EVAL {expr} => {json.dumps(cdp.eval(expr), ensure_ascii=False)[:4000]}")
        cdp.drain_console()
        if args.shot:
            data = cdp.call("Page.captureScreenshot", {"format": "png"})["data"]
            with open(args.shot, "wb") as f:
                f.write(base64.b64decode(data))
            print(f"SHOT {args.shot}")
        return 0 if "PASS" in title else 1
    finally:
        proc.terminate()
        try:
            proc.wait(5)
        except subprocess.TimeoutExpired:
            proc.kill()
        shutil.rmtree(profile, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
