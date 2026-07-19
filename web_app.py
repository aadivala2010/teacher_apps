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
from urllib.parse import parse_qs, quote_plus, unquote, urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

import planner_db
import planner_docx
import planner_pdf
import blob_storage
import grid_pdf
import table_app
import supabase_sync
import activity_descriptor_pptx


ROOT = Path(__file__).resolve().parent / "public"
MAX_UPLOAD_BYTES = 80 * 1024 * 1024
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
        route = self.route_name()
        if route == "planner-save":
            try:
                self.handle_planner_save()
            except Exception as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if route == "planner-upload-attachment":
            try:
                self.handle_planner_upload_attachment()
            except Exception as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if route == "planner-load":
            try:
                self.handle_planner_load()
            except Exception as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if route == "planner-template-save":
            try:
                self.handle_planner_template_save()
            except Exception as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if route == "planner-template-load":
            try:
                self.handle_planner_template_load()
            except Exception as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if route == "planner-export-pdf":
            try:
                self.handle_planner_export_pdf()
            except Exception as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if route == "planner-export-docx":
            try:
                self.handle_planner_export_docx()
            except Exception as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if route == "planner-export-database-docx":
            try:
                self.handle_planner_export_database_docx()
            except Exception as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if route == "planner-export-saved-pdf":
            try:
                self.handle_planner_export_saved_pdf()
            except Exception as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if route == "lesson-plan-copier":
            try:
                self.handle_lesson_plan_copier()
            except Exception as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if route == "activity-descriptor-export":
            try:
                self.handle_activity_descriptor_export()
            except Exception as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if route == "activity-descriptor-sync-save":
            try:
                self.handle_activity_descriptor_sync_save()
            except Exception as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if route == "activity-descriptor-sync-load":
            try:
                self.handle_activity_descriptor_sync_load()
            except Exception as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if route == "activity-descriptor-sync-list":
            try:
                self.handle_activity_descriptor_sync_list()
            except Exception as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if route == "grid-pdf":
            try:
                self.handle_grid_pdf()
            except Exception as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if route == "grid-print-pdf":
            try:
                self.handle_grid_print_pdf()
            except Exception as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if route == "book-theme-finder":
            try:
                self.handle_book_theme_finder()
            except Exception as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if route == "auth-signup":
            try:
                self.handle_auth_signup()
            except Exception as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if route == "auth-login":
            try:
                self.handle_auth_login()
            except Exception as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if route == "auth-refresh":
            try:
                self.handle_auth_refresh()
            except Exception as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if route == "auth-me":
            try:
                self.handle_auth_me()
            except Exception as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if route == "sync-save":
            try:
                self.handle_sync_save()
            except Exception as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if route == "sync-load":
            try:
                self.handle_sync_load()
            except Exception as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if route == "sync-list":
            try:
                self.handle_sync_list()
            except Exception as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if route == "sync-delete":
            try:
                self.handle_sync_delete()
            except Exception as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if route == "sync-attachment":
            try:
                self.handle_sync_attachment()
            except Exception as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if route == "sync-upload-attachment":
            try:
                self.handle_sync_upload_attachment()
            except Exception as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        else:
            self.send_error(HTTPStatus.NOT_FOUND)
            return

    def do_GET(self) -> None:
        route = self.route_name()
        if route == "attachment":
            try:
                self.handle_attachment_download()
            except Exception as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if route == "sync-attachment":
            try:
                self.handle_sync_attachment()
            except Exception as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if route in {
            "book-theme-finder",
            "lesson-plan-copier",
            "grid-pdf",
            "activity-descriptor-export",
            "planner-save",
            "planner-upload-attachment",
            "planner-load",
            "planner-template-save",
            "planner-template-load",
            "planner-export-pdf",
            "planner-export-docx",
            "planner-export-database-docx",
            "planner-export-saved-pdf",
            "auth-signup",
            "auth-login",
            "auth-me",
            "sync-save",
            "sync-load",
            "sync-list",
            "sync-delete",
            "sync-upload-attachment",
        }:
            self.send_json({"ok": True, "route": route, "method": "POST"})
            return
        super().do_GET()

    def route_name(self) -> str:
        parsed = urlparse(self.path)
        query_route = parse_qs(parsed.query).get("route", [""])[0]
        if query_route:
            return query_route
        path = parsed.path.rstrip("/")
        if path.endswith("/book-theme-finder") or path.endswith("/book_theme_finder"):
            return "book-theme-finder"
        if path.endswith("/lesson-plan-copier") or path.endswith("/lesson_plan_copier"):
            return "lesson-plan-copier"
        if path.endswith("/grid-pdf") or path.endswith("/grid_pdf"):
            return "grid-pdf"
        if path.endswith("/grid-print-pdf") or path.endswith("/grid_print_pdf"):
            return "grid-print-pdf"
        if path.endswith("/planner-save"):
            return "planner-save"
        if path.endswith("/planner-upload-attachment"):
            return "planner-upload-attachment"
        if path.endswith("/planner-load"):
            return "planner-load"
        if path.endswith("/planner-template-save"):
            return "planner-template-save"
        if path.endswith("/planner-template-load"):
            return "planner-template-load"
        if path.endswith("/planner-export-pdf"):
            return "planner-export-pdf"
        if path.endswith("/planner-export-docx"):
            return "planner-export-docx"
        if path.endswith("/planner-export-database-docx"):
            return "planner-export-database-docx"
        if path.endswith("/planner-export-saved-pdf"):
            return "planner-export-saved-pdf"
        if path.endswith("/attachment"):
            return "attachment"
        if path.endswith("/auth-signup"):
            return "auth-signup"
        if path.endswith("/auth-login"):
            return "auth-login"
        if path.endswith("/auth-refresh"):
            return "auth-refresh"
        if path.endswith("/auth-me"):
            return "auth-me"
        if path.endswith("/sync-save"):
            return "sync-save"
        if path.endswith("/sync-load"):
            return "sync-load"
        if path.endswith("/sync-list"):
            return "sync-list"
        if path.endswith("/sync-delete"):
            return "sync-delete"
        if path.endswith("/sync-attachment"):
            return "sync-attachment"
        if path.endswith("/sync-upload-attachment"):
            return "sync-upload-attachment"
        return path.rsplit("/", 1)[-1]

    def read_json_body(self, max_bytes: int = 1_000_000) -> dict[str, object]:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length <= 0 or content_length > max_bytes:
            raise ValueError("Request body is missing or too large.")
        return json.loads(self.rfile.read(content_length).decode("utf-8-sig"))

    def parse_multipart_body(self, max_bytes: int = 25 * 1024 * 1024) -> tuple[dict[str, str], dict[str, dict[str, object]]]:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length <= 0 or content_length > max_bytes:
            raise ValueError("Upload is missing or too large.")

        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            raise ValueError("Upload must be multipart form data.")

        body = self.rfile.read(content_length)
        message = BytesParser(policy=default).parsebytes(
            f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf-8") + body
        )

        fields: dict[str, str] = {}
        files: dict[str, dict[str, object]] = {}
        for part in message.iter_parts():
            name = part.get_param("name", header="content-disposition")
            filename = part.get_filename()
            payload = part.get_payload(decode=True) or b""
            if not name:
                continue
            if filename:
                files[name] = {
                    "filename": filename,
                    "mimeType": part.get_content_type() or "application/octet-stream",
                    "content": payload,
                }
            else:
                fields[name] = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
        return fields, files

    def planner_attachments_from_files(self, files: dict[str, dict[str, object]]) -> dict[str, dict[str, object]]:
        result: dict[str, dict[str, object]] = {}
        for key, value in files.items():
            if key.startswith("attachment::"):
                result[key.split("attachment::", 1)[1]] = value
        return result

    def handle_planner_save(self) -> None:
        fields, files = self.parse_multipart_body()
        payload = json.loads(fields.get("payload", "{}"))
        attachments = self.planner_attachments_from_files(files)
        try:
            result = planner_db.save_plan(payload, attachments)
            if attachments and blob_storage.is_configured():
                result["attachments"] = blob_storage.upload_file_attachments(attachments)
        except Exception:
            if not blob_storage.is_configured():
                raise
            result = dict(payload)
            result["attachments"] = blob_storage.upload_file_attachments(attachments)
        self.send_json({"plan": result})

    def handle_planner_upload_attachment(self) -> None:
        fields, files = self.parse_multipart_body()
        field_key = fields.get("fieldKey", "")
        attachment = next(iter(files.values()), None)
        if not field_key or not attachment:
            raise ValueError("Attachment upload is missing.")
        result = blob_storage.upload_attachment(
            str(attachment.get("filename") or "attachment"),
            str(attachment.get("mimeType") or "application/octet-stream"),
            bytes(attachment.get("content") or b""),
        )
        self.send_json({"fieldKey": field_key, "attachment": result})

    def handle_planner_load(self) -> None:
        payload = self.read_json_body()
        result = planner_db.load_plan(int(payload["year"]), int(payload["month"]), int(payload["weekNumber"]))
        if not result:
            self.send_json({"plan": None})
            return
        self.send_json({"plan": result})

    def handle_planner_template_save(self) -> None:
        fields, files = self.parse_multipart_body()
        payload = json.loads(fields.get("payload", "{}"))
        result = planner_db.save_template(payload, self.planner_attachments_from_files(files))
        self.send_json({"template": result})

    def handle_planner_template_load(self) -> None:
        payload = self.read_json_body()
        result = planner_db.load_template(int(payload["month"]), int(payload["weekNumber"]))
        if not result:
            self.send_json({"template": None})
            return
        self.send_json({"template": result})

    def handle_attachment_download(self) -> None:
        parsed = urlparse(self.path)
        attachment_id = parse_qs(parsed.query).get("id", [""])[0]
        if not attachment_id.isdigit():
            raise ValueError("Attachment id is missing.")
        attachment = planner_db.get_attachment(int(attachment_id))
        if not attachment:
            self.send_json({"error": "Attachment was not found."}, HTTPStatus.NOT_FOUND)
            return
        content = bytes(attachment["content"])
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", str(attachment["mimeType"]))
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Content-Disposition", f'attachment; filename="{attachment["filename"]}"')
        self.end_headers()
        self.wfile.write(content)

    def handle_planner_export_pdf(self) -> None:
        payload = self.read_json_body()
        result, filename = planner_pdf.build_planner_pdf(payload)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Length", str(len(result)))
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(result)

    def handle_activity_descriptor_export(self) -> None:
        payload = self.read_json_body()
        result, filename = activity_descriptor_pptx.build_activity_descriptor_pptx(payload)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.presentationml.presentation")
        self.send_header("Content-Length", str(len(result)))
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(result)

    def handle_activity_descriptor_sync_save(self) -> None:
        token = (self.headers.get("Authorization") or "").removeprefix("Bearer ").strip()
        payload = self.read_json_body()
        result = supabase_sync.save_activity(token, payload)
        self.send_json({"activity": result})

    def handle_activity_descriptor_sync_load(self) -> None:
        token = (self.headers.get("Authorization") or "").removeprefix("Bearer ").strip()
        payload = self.read_json_body()
        result = supabase_sync.load_activity(token, str(payload.get("date", "")))
        self.send_json({"activity": result})

    def handle_activity_descriptor_sync_list(self) -> None:
        token = (self.headers.get("Authorization") or "").removeprefix("Bearer ").strip()
        result = supabase_sync.list_activities(token)
        self.send_json({"activities": result})

    def handle_planner_export_docx(self) -> None:
        payload = self.read_json_body(max_bytes=MAX_UPLOAD_BYTES)
        result, filename = planner_docx.build_planner_docx(payload)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        self.send_header("Content-Length", str(len(result)))
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(result)

    def handle_planner_export_database_docx(self) -> None:
        payload = self.read_json_body(max_bytes=MAX_UPLOAD_BYTES)
        plans = payload.get("savedWeeks") or []
        if not isinstance(plans, list) or not plans:
            raise ValueError("Select at least one saved week to download.")
        plans = blob_storage.ensure_plan_attachment_urls(plans)
        base_url = str(payload.get("baseUrl") or f"http://{self.headers.get('Host', '')}")
        result, filename = planner_docx.build_database_docx(plans, base_url)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        self.send_header("Content-Length", str(len(result)))
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(result)

    def handle_planner_export_saved_pdf(self) -> None:
        payload = self.read_json_body()
        plan = planner_db.load_plan(int(payload["year"]), int(payload["month"]), int(payload["weekNumber"]))
        if not plan:
            self.send_json({"error": "No saved week was found for this month and week."}, HTTPStatus.NOT_FOUND)
            return
        plan["monthLabel"] = payload.get("monthLabel") or plan.get("monthLabel") or ""
        result, filename = planner_pdf.build_planner_pdf(plan)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Length", str(len(result)))
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(result)

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

    def handle_grid_pdf(self) -> None:
        fields, files = self.parse_multipart_body(max_bytes=MAX_UPLOAD_BYTES)
        image_files = [value for key, value in files.items() if key.startswith("images")]
        for f in image_files:
            f["content"] = grid_pdf.compress_image_bytes(f.get("content") or b"")
        if fields.get("layout") == "two-per-page":
            result = grid_pdf.build_two_per_page_pdf(image_files, fields.get("orientation") == "stack")
            filename = "2-per-page.pdf"
        else:
            result = grid_pdf.build_grid_pdf(image_files)
            filename = "2x2.pdf"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Length", str(len(result)))
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(result)

    def handle_grid_print_pdf(self) -> None:
        _, files = self.parse_multipart_body(max_bytes=MAX_UPLOAD_BYTES)
        slots: list[dict[str, object] | None] = [None] * grid_pdf.GRID_SLOTS
        for key, value in files.items():
            if not key.startswith("slot::"):
                continue
            try:
                index = int(key.split("::", 1)[1])
            except ValueError:
                continue
            if 0 <= index < grid_pdf.GRID_SLOTS:
                value["content"] = grid_pdf.compress_image_bytes(value.get("content") or b"")
                slots[index] = value
        result = grid_pdf.build_grid_3x4_pdf(slots)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Length", str(len(result)))
        self.send_header("Content-Disposition", 'attachment; filename="grid-print.pdf"')
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

    def _read_body_json(self) -> dict:
        return self.read_json_body()

    def _get_auth_token(self) -> str:
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return auth[7:]
        return ""

    def handle_auth_signup(self) -> None:
        data = self._read_body_json()
        email = str(data.get("email", "")).strip()
        password = str(data.get("password", "")).strip()
        if not email or not password:
            raise ValueError("Email and password are required.")
        if len(password) < 6:
            raise ValueError("Password must be at least 6 characters.")
        result = supabase_sync.sign_up(email, password)
        self.send_json(result)

    def handle_auth_login(self) -> None:
        data = self._read_body_json()
        email = str(data.get("email", "")).strip()
        password = str(data.get("password", "")).strip()
        if not email or not password:
            print(f"[auth-login] Missing email or password", flush=True)
            raise ValueError("Email and password are required.")
        print(f"[auth-login] Attempting login for {email}", flush=True)
        result = supabase_sync.sign_in(email, password)
        self.send_json(result)

    def handle_auth_refresh(self) -> None:
        data = self._read_body_json()
        refresh_token = str(data.get("refresh_token", "")).strip()
        if not refresh_token:
            raise ValueError("Missing refresh token.")
        result = supabase_sync.refresh_session(refresh_token)
        self.send_json(result)

    def handle_auth_me(self) -> None:
        token = self._get_auth_token()
        if not token:
            self.send_json({"user": None})
            return
        user = supabase_sync.get_user(token)
        if not user:
            self.send_json({"user": None})
            return
        self.send_json({"user": user})

    def handle_sync_save(self) -> None:
        token = self._get_auth_token()
        if not token:
            self.send_json({"error": "Authentication required."}, HTTPStatus.UNAUTHORIZED)
            return
        data = self._read_body_json()
        result = supabase_sync.save_plan(token, data)
        self.send_json({"plan": result})

    def handle_sync_load(self) -> None:
        token = self._get_auth_token()
        if not token:
            self.send_json({"error": "Authentication required."}, HTTPStatus.UNAUTHORIZED)
            return
        data = self._read_body_json()
        result = supabase_sync.load_plan(token, int(data["year"]), int(data["month"]), int(data["weekNumber"]))
        if not result:
            self.send_json({"plan": None})
            return
        self.send_json({"plan": result})

    def handle_sync_list(self) -> None:
        token = self._get_auth_token()
        if not token:
            self.send_json({"error": "Authentication required."}, HTTPStatus.UNAUTHORIZED)
            return
        plans = supabase_sync.list_plans(token)
        self.send_json({"plans": plans})

    def handle_sync_delete(self) -> None:
        token = self._get_auth_token()
        if not token:
            self.send_json({"error": "Authentication required."}, HTTPStatus.UNAUTHORIZED)
            return
        data = self._read_body_json()
        ok = supabase_sync.delete_plan(token, int(data["year"]), int(data["month"]), int(data["weekNumber"]))
        self.send_json({"ok": ok})

    def handle_sync_attachment(self) -> None:
        token = self._get_auth_token()
        if not token:
            self.send_json({"error": "Authentication required."}, HTTPStatus.UNAUTHORIZED)
            return
        from urllib.parse import parse_qs, unquote
        parsed = urlparse(self.path)
        path = unquote(parse_qs(parsed.query).get("path", [""])[0])
        if not path:
            raise ValueError("Attachment path is missing.")
        attachment = supabase_sync.get_attachment(token, path)
        if not attachment:
            self.send_json({"error": "Attachment was not found."}, HTTPStatus.NOT_FOUND)
            return
        content = bytes(attachment["content"])
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", str(attachment["mimeType"]))
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Content-Disposition", f'attachment; filename="{attachment["filename"]}"')
        self.end_headers()
        self.wfile.write(content)

    def handle_sync_upload_attachment(self) -> None:
        token = self._get_auth_token()
        if not token:
            self.send_json({"error": "Authentication required."}, HTTPStatus.UNAUTHORIZED)
            return
        fields, files = self.parse_multipart_body()
        field_key = fields.get("fieldKey", "")
        lookup = json.loads(fields.get("planLookup", "{}"))
        attachment = next(iter(files.values()), None)
        if not field_key or not attachment:
            raise ValueError("Attachment upload is missing.")
        result = supabase_sync.save_attachment(
            token,
            int(lookup.get("year", 0)),
            int(lookup.get("month", 0)),
            int(lookup.get("weekNumber", 0)),
            field_key,
            str(attachment.get("filename") or "attachment"),
            str(attachment.get("mimeType") or "application/octet-stream"),
            bytes(attachment.get("content") or b""),
        )
        self.send_json({"fieldKey": field_key, "attachment": result})

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
    value = os.environ.get("GEMINI_API_KEY", "").strip()
    if not value:
        raise ValueError("GEMINI_API_KEY is not set. Add it in Vercel before using Book Theme Finder.")
    return value


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
