"""Loopback-only, same-origin static editor and JSON command bridge."""

import asyncio
import json
import mimetypes
import secrets
from pathlib import Path
from urllib.parse import unquote, urlsplit

from cozmo_desktop.code_lab.commands import ScratchCommandError, ScratchCommands
from cozmo_desktop.robot.base import RobotError

MAX_REQUEST = 16_384


class CodeLabServer:
    def __init__(self, commands: ScratchCommands, static_dir: Path) -> None:
        self.commands = commands
        self.static_dir = static_dir.resolve()
        self.token = secrets.token_urlsafe(32)
        self._server: asyncio.AbstractServer | None = None
        self.port = 0

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/?code_token={self.token}"

    async def start(self) -> None:
        if not (self.static_dir / "index.html").is_file():
            raise FileNotFoundError("The Scratch editor bundle is not installed.")
        self._server = await asyncio.start_server(self._handle, "127.0.0.1", 0)
        self.port = self._server.sockets[0].getsockname()[1]

    async def close(self) -> None:
        self.commands.cancel()
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    @staticmethod
    def _response(status: int, body: bytes, content_type: str = "application/json") -> bytes:
        reasons = {
            200: "OK",
            400: "Bad Request",
            403: "Forbidden",
            404: "Not Found",
            405: "Method Not Allowed",
            413: "Payload Too Large",
            500: "Internal Server Error",
        }
        return (
            f"HTTP/1.1 {status} {reasons[status]}\r\n"
            f"Content-Type: {content_type}\r\nContent-Length: {len(body)}\r\n"
            "Cache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\n"
            "Content-Security-Policy: default-src 'self' data: blob: 'unsafe-inline' "
            "'unsafe-eval'; connect-src 'self'; worker-src 'self' blob:; "
            "img-src 'self' data: blob:; media-src 'self' blob: data:\r\n"
            "Connection: close\r\n\r\n"
        ).encode("ascii") + body

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            response = await asyncio.wait_for(self._process(reader), timeout=40)
        except (TimeoutError, ValueError, UnicodeError, json.JSONDecodeError):
            response = self._response(400, b'{"error":"Invalid request."}')
        except Exception:
            response = self._response(500, b'{"error":"Code Lab is unavailable."}')
        writer.write(response)
        try:
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    async def _process(self, reader: asyncio.StreamReader) -> bytes:
        first = await reader.readline()
        if len(first) > 4096:
            return self._response(413, b'{"error":"Request too large."}')
        parts = first.decode("ascii").strip().split(" ")
        if len(parts) != 3 or parts[2] != "HTTP/1.1":
            return self._response(400, b'{"error":"Invalid request."}')
        method, raw_path, _ = parts
        headers: dict[str, str] = {}
        size = len(first)
        while True:
            line = await reader.readline()
            size += len(line)
            if size > MAX_REQUEST or not line:
                return self._response(413, b'{"error":"Request too large."}')
            if line == b"\r\n":
                break
            key, sep, value = line.decode("ascii").partition(":")
            if not sep or key.lower() in headers:
                return self._response(400, b'{"error":"Invalid headers."}')
            headers[key.lower()] = value.strip()
        host = f"127.0.0.1:{self.port}"
        if headers.get("host") != host:
            return self._response(403, b'{"error":"Local access only."}')
        origin = headers.get("origin")
        if origin is not None and origin != f"http://{host}":
            return self._response(403, b'{"error":"Local access only."}')
        path = urlsplit(raw_path).path
        if path.startswith("/api/"):
            if headers.get("x-code-token") != self.token:
                return self._response(403, b'{"error":"Code Lab session expired."}')
            if path == "/api/state" and method == "GET":
                return self._json(200, {"status": "ok", "state": self.commands.state()})
            if path == "/api/emergency-stop" and method == "POST":
                self.commands.controller.emergency_stop()
                return self._json(200, {"status": "ok", "result": None})
            if path != "/api/command" or method != "POST":
                return self._response(404, b'{"error":"Unknown endpoint."}')
            if headers.get("content-type", "").split(";")[0] != "application/json":
                return self._response(400, b'{"error":"JSON required."}')
            length = headers.get("content-length", "")
            if not length.isdigit() or int(length) > MAX_REQUEST:
                return self._response(413, b'{"error":"Request too large."}')
            body = await reader.readexactly(int(length))
            request = json.loads(body)
            if not isinstance(request, dict) or set(request) != {"command", "arguments"}:
                return self._response(400, b'{"error":"Invalid command."}')
            try:
                async with asyncio.timeout(35):
                    result = await self.commands.execute(request["command"], request["arguments"])
            except (ScratchCommandError, RobotError) as exc:
                return self._json(400, {"status": "error", "error": str(exc)})
            except asyncio.CancelledError:
                return self._json(400, {"status": "error", "error": "Cozmo stopped."})
            return self._json(200, {"status": "ok", "result": result})
        if method != "GET":
            return self._response(405, b'{"error":"Use GET."}')
        decoded = unquote(path)
        if "\\" in decoded or "\x00" in decoded:
            return self._response(404, b'{"error":"Not found."}')
        target = (self.static_dir / decoded.lstrip("/")).resolve()
        if decoded == "/":
            target = self.static_dir / "index.html"
        if not target.is_relative_to(self.static_dir) or not target.is_file():
            return self._response(404, b'{"error":"Not found."}')
        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        return self._response(200, target.read_bytes(), content_type)

    @classmethod
    def _json(cls, status: int, value: dict[str, object]) -> bytes:
        return cls._response(status, json.dumps(value, ensure_ascii=False).encode("utf-8"))
