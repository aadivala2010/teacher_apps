from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler

from web_app import generate_preschool_books


class handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length <= 0 or content_length > 32_768:
                raise ValueError("Send a short theme for the book search.")

            data = json.loads(self.rfile.read(content_length).decode("utf-8-sig"))
            theme = str(data.get("theme", "")).strip()
            if not theme:
                raise ValueError("Enter a theme first.")
            if len(theme) > 120:
                raise ValueError("Keep the theme under 120 characters.")

            self.send_json({"theme": theme, "books": generate_preschool_books(theme)})
        except Exception as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def do_GET(self) -> None:
        self.send_json({"error": "Use POST for this endpoint."}, HTTPStatus.METHOD_NOT_ALLOWED)

    def send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
