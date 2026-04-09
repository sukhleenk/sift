import json
import logging
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, unquote, urlparse

from app import db

logger = logging.getLogger(__name__)

_server: HTTPServer | None = None
_port: int = 0


def get_port() -> int:
    return _port


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # silence default access log

    def do_GET(self):
        parsed = urlparse(self.path)
        parts = [p for p in parsed.path.strip("/").split("/") if p]
        action = parts[0] if parts else ""

        try:
            if action == "saved":
                self._serve_saved_papers()
            elif action == "mark-read" and len(parts) == 2:
                db.mark_paper_read(unquote(parts[1]))
                self._ok()
            elif action == "mark-unread" and len(parts) == 2:
                with db.get_connection() as conn:
                    conn.execute("UPDATE Papers SET is_read = 0 WHERE id = ?", (unquote(parts[1]),))
                self._ok()
            elif action == "save" and len(parts) == 2:
                db.save_paper(unquote(parts[1]))
                self._ok()
            elif action == "unsave" and len(parts) == 2:
                paper_id = unquote(parts[1])
                with db.get_connection() as conn:
                    conn.execute("UPDATE Papers SET is_saved = 0 WHERE id = ?", (paper_id,))
                    conn.execute("DELETE FROM SavedPapers WHERE paper_id = ?", (paper_id,))
                self._ok()
            elif action == "notes" and len(parts) >= 2:
                paper_id = unquote(parts[1])
                notes = unquote(parts[2]) if len(parts) > 2 else ""
                with db.get_connection() as conn:
                    conn.execute(
                        "UPDATE SavedPapers SET notes = ? WHERE paper_id = ?",
                        (notes, paper_id),
                    )
                self._ok()
            else:
                self._respond(404, "not found")
        except Exception as exc:
            logger.error("Action server error: %s", exc)
            self._respond(500, str(exc))

    def _serve_saved_papers(self):
        from app.renderer import render_saved_papers
        papers = db.get_saved_papers()
        html = render_saved_papers(papers, _port, as_string=True)
        data = html.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _ok(self):
        self._respond(200, "ok")

    def _respond(self, code: int, body: str):
        data = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)


def start() -> int:
    global _server, _port
    _port = _free_port()
    _server = HTTPServer(("127.0.0.1", _port), _Handler)
    t = threading.Thread(target=_server.serve_forever, daemon=True)
    t.start()
    logger.info("Action server listening on port %d", _port)
    return _port
