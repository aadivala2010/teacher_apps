#!/usr/bin/env python3
"""Local web app for teacher-facing tools."""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import tempfile
import time
import uuid
from email.parser import BytesParser
from email.policy import default
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote_plus, unquote
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

import table_app


ROOT = Path(__file__).resolve().parent
MAX_UPLOAD_BYTES = 80 * 1024 * 1024
DUMMY_GEMINI_API_KEY = "AIzaSyCRYJh9Kk6Pvsq3P9uV8naLMV2XcgYf2E4"
GEMINI_MODELS = ["gemini-2.5-flash-lite"]


class TeacherToolsHandler(SimpleHTTPRequestHandler):
    server_version = "TeacherTools/1.0"

    def translate_path(self, path: str) -> str:
        clean = unquote(path.split("?", 1)[0].split("#", 1)[0]).lstrip("/")
        if clean in {"", "/"}:
            clean = "index.html"
        target = (ROOT / clean).resolve()
        if not str(target).startswith(str(ROOT)):
            return str(ROOT / "index.html")
        return str(target)

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0]
        if path == "/api/lesson-plan-copier":
            try:
                self.handle_lesson_plan_copier()
            except Exception as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if path == "/api/book-theme-finder":
            try:
                self.handle_book_theme_finder()
            except Exception as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        else:
            self.send_error(HTTPStatus.NOT_FOUND)
            return

    def handle_lesson_plan_copier(self) -> None:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length <= 0:
            raise ValueError("No files were uploaded.")
        if content_length > MAX_UPLOAD_BYTES:
            raise ValueError("Upload is too large. Keep the DOCX and PDF under 80 MB total.")

        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            raise ValueError("Upload must be multipart form data.")

        body = self.rfile.read(content_length)
        message = BytesParser(policy=default).parsebytes(
            f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf-8") + body
        )

        fields: dict[str, str] = {}
        files: dict[str, tuple[str, bytes]] = {}
        for part in message.iter_parts():
            name = part.get_param("name", header="content-disposition")
            filename = part.get_filename()
            payload = part.get_payload(decode=True) or b""
            if not name:
                continue
            if filename:
                files[name] = (filename, payload)
            else:
                fields[name] = payload.decode(part.get_content_charset() or "utf-8", errors="replace")

        if "docx" not in files or "pdf" not in files:
            raise ValueError("Select both a filled DOCX and a matching PDF.")

        docx_name, docx_bytes = files["docx"]
        pdf_name, pdf_bytes = files["pdf"]
        if not docx_name.lower().endswith(".docx"):
            raise ValueError("The first file must be a .docx file.")
        if not pdf_name.lower().endswith(".pdf"):
            raise ValueError("The second file must be a .pdf file.")

        job_id = uuid.uuid4().hex
        with tempfile.TemporaryDirectory(prefix=f"lesson-plan-copier-{job_id}-") as tmp:
            tmp_path = Path(tmp)
            docx_path = tmp_path / "source.docx"
            pdf_path = tmp_path / "target.pdf"
            output_path = tmp_path / "lesson-plan-copied.pdf"
            docx_path.write_bytes(docx_bytes)
            pdf_path.write_bytes(pdf_bytes)

            args = argparse.Namespace(
                docx=docx_path,
                pdf=pdf_path,
                output=output_path,
                no_backup=True,
                layout_json=None,
                fallback_docx_geometry=True,
                font="Helvetica",
                font_size=10.0,
                min_font_size=6.0,
                padding=3.0,
                cover_existing=fields.get("coverExisting") == "true",
                all_cells=False,
                report_json=None,
            )
            table_app.transfer_text(args)
            result = output_path.read_bytes()

        download_name = Path(pdf_name).with_name(f"{Path(pdf_name).stem}-copied.pdf").name
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Length", str(len(result)))
        self.send_header("Content-Disposition", f'attachment; filename="{download_name}"')
        self.end_headers()
        self.wfile.write(result)

    def handle_book_theme_finder(self) -> None:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length <= 0 or content_length > 32_768:
            raise ValueError("Send a short theme for the book search.")
        data = json.loads(self.rfile.read(content_length).decode("utf-8-sig"))
        theme = str(data.get("theme", "")).strip()
        if not theme:
            raise ValueError("Enter a theme first.")
        if len(theme) > 120:
            raise ValueError("Keep the theme under 120 characters.")

        books = generate_preschool_books(theme)
        self.send_json({"theme": theme, "books": books})

    def send_json(self, payload: dict[str, str], status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def end_headers(self) -> None:
        static_path = self.path.split("?", 1)[0]
        if static_path.endswith((".css", ".js", ".html")) or static_path == "/":
            self.send_header("Cache-Control", "no-store")
        super().end_headers()


def gemini_api_key() -> str:
    return os.environ.get("GEMINI_API_KEY", DUMMY_GEMINI_API_KEY).strip()


def build_book_prompt(theme: str) -> str:
    return (
        "You are helping preschool teachers choose read-aloud books.\n"
        f"Theme: {theme}\n\n"
        "Return exactly 10 real, published picture books appropriate for preschoolers. "
        "Do not return 9 items. Do not include placeholders. "
        "Each book must have a non-empty title, author, and description. "
        "The description must be exactly two complete sentences. "
        "Use concise, classroom-friendly language.\n\n"
        "Return only valid JSON in this exact shape:\n"
        '{"books":[{"title":"...","author":"...","description":"Sentence one. Sentence two."},'
        '{"title":"...","author":"...","description":"Sentence one. Sentence two."},'
        '{"title":"...","author":"...","description":"Sentence one. Sentence two."},'
        '{"title":"...","author":"...","description":"Sentence one. Sentence two."},'
        '{"title":"...","author":"...","description":"Sentence one. Sentence two."},'
        '{"title":"...","author":"...","description":"Sentence one. Sentence two."},'
        '{"title":"...","author":"...","description":"Sentence one. Sentence two."},'
        '{"title":"...","author":"...","description":"Sentence one. Sentence two."},'
        '{"title":"...","author":"...","description":"Sentence one. Sentence two."},'
        '{"title":"...","author":"...","description":"Sentence one. Sentence two."}]}'
    )


def extract_response_text(payload: dict) -> str:
    parts: list[str] = []
    for candidate in payload.get("candidates", []):
        content = candidate.get("content", {})
        for part in content.get("parts", []):
            if "text" in part:
                parts.append(str(part["text"]))
    return "\n".join(parts).strip()


def extract_json_object(text: str) -> dict:
    cleaned = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.IGNORECASE | re.MULTILINE).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            raise ValueError("Gemini did not return a readable book list.")
        return json.loads(match.group(0))


def normalize_books(data: dict) -> list[dict[str, str]]:
    raw_books = data.get("books") or data.get("bookRecommendations") or data.get("recommendations")
    if not isinstance(raw_books, list):
        raise ValueError("Gemini response did not include books.")
    books: list[dict[str, str]] = []
    for item in raw_books:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or item.get("name") or item.get("book") or "").strip()
        author = str(item.get("author") or item.get("by") or "").strip()
        description = str(item.get("description") or item.get("summary") or item.get("desc") or "").strip()
        if title and author and description:
            youtube_query = quote_plus(f"{title} {author} read aloud")
            books.append(
                {
                    "title": title,
                    "author": author,
                    "description": description,
                    "youtubeUrl": f"https://www.youtube.com/results?search_query={youtube_query}",
                }
            )
        if len(books) == 10:
            break
    if len(books) < 10:
        raise ValueError("Gemini returned fewer than 10 complete book suggestions.")
    return books


def call_gemini_model(model: str, theme: str, attempt: int = 1) -> list[dict[str, str]]:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={gemini_api_key()}"
    body = {
        "contents": [{"parts": [{"text": build_book_prompt(theme)}]}],
        "generationConfig": {
            "temperature": 0.35 if attempt == 1 else 0.55,
            "maxOutputTokens": 4096,
            "responseMimeType": "application/json",
            "responseSchema": {
                "type": "object",
                "properties": {
                    "books": {
                        "type": "array",
                        "minItems": 10,
                        "maxItems": 10,
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "author": {"type": "string"},
                                "description": {"type": "string"},
                            },
                            "required": ["title", "author", "description"],
                        },
                    }
                },
                "required": ["books"],
            },
        },
    }
    request = Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return normalize_books(extract_json_object(extract_response_text(payload)))


def generate_preschool_books(theme: str) -> list[dict[str, str]]:
    errors: list[str] = []
    for model in GEMINI_MODELS:
        for attempt in range(1, 4):
            try:
                return call_gemini_model(model, theme, attempt)
            except HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")
                errors.append(f"{model} attempt {attempt}: HTTP {exc.code} {detail[:220]}")
            except (URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
                errors.append(f"{model} attempt {attempt}: {exc}")
            time.sleep(0.25)
    raise ValueError("Gemini could not generate the book list. " + " | ".join(errors))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Teacher Tools web app.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    mimetypes.add_type("text/css", ".css")
    server = ThreadingHTTPServer((args.host, args.port), TeacherToolsHandler)
    print(f"Teacher Tools is running at http://{args.host}:{args.port}")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
