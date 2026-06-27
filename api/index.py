from __future__ import annotations

import argparse
import json
import tempfile
import uuid
from email.parser import BytesParser
from email.policy import default
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import planner_db
import planner_docx
import planner_pdf
import blob_storage
import grid_pdf
import table_app
import supabase_sync
from web_app import generate_preschool_books


VERCEL_BODY_LIMIT_BYTES = 4_500_000


class handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        route = self.route_name()
        try:
            if route == "planner-save":
                self.handle_planner_save()
                return
            if route == "planner-upload-attachment":
                self.handle_planner_upload_attachment()
                return
            if route == "planner-load":
                self.handle_planner_load()
                return
            if route == "planner-template-save":
                self.handle_planner_template_save()
                return
            if route == "planner-template-load":
                self.handle_planner_template_load()
                return
            if route == "planner-export-pdf":
                self.handle_planner_export_pdf()
                return
            if route == "planner-export-docx":
                self.handle_planner_export_docx()
                return
            if route == "planner-export-database-docx":
                self.handle_planner_export_database_docx()
                return
            if route == "planner-export-saved-pdf":
                self.handle_planner_export_saved_pdf()
                return
            if route == "book-theme-finder":
                self.handle_book_theme_finder()
                return
            if route == "lesson-plan-copier":
                self.handle_lesson_plan_copier()
                return
            if route == "grid-pdf":
                self.handle_grid_pdf()
                return
            if route == "auth-signup":
                self.handle_auth_signup()
                return
            if route == "auth-login":
                self.handle_auth_login()
                return
            if route == "auth-me":
                self.handle_auth_me()
                return
            if route == "sync-save":
                self.handle_sync_save()
                return
            if route == "sync-load":
                self.handle_sync_load()
                return
            if route == "sync-list":
                self.handle_sync_list()
                return
            if route == "sync-delete":
                self.handle_sync_delete()
                return
            if route == "sync-attachment":
                self.handle_sync_attachment()
                return
            self.send_json({"error": "Unknown API route."}, HTTPStatus.NOT_FOUND)
        except Exception as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def do_GET(self) -> None:
        route = self.route_name()
        if route == "attachment":
            self.handle_attachment_download()
            return
        if route == "sync-attachment":
            self.handle_sync_attachment()
            return
        if route in {
            "book-theme-finder",
            "lesson-plan-copier",
            "grid-pdf",
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
            "index",
        }:
            self.send_json({"ok": True, "route": route, "method": "POST"})
            return
        self.send_json({"error": "Unknown API route."}, HTTPStatus.NOT_FOUND)

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
            self.send_json({"error": "Attachment id is missing."}, HTTPStatus.BAD_REQUEST)
            return
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

    def handle_planner_export_docx(self) -> None:
        payload = self.read_json_body(max_bytes=VERCEL_BODY_LIMIT_BYTES)
        result, filename = planner_docx.build_planner_docx(payload)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        self.send_header("Content-Length", str(len(result)))
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(result)

    def handle_planner_export_database_docx(self) -> None:
        payload = self.read_json_body(max_bytes=VERCEL_BODY_LIMIT_BYTES)
        plans = payload.get("savedWeeks") or []
        if not isinstance(plans, list) or not plans:
            raise ValueError("Select at least one saved week to download.")
        plans = blob_storage.ensure_plan_attachment_urls(plans)
        base_url = str(payload.get("baseUrl") or f"https://{self.headers.get('Host', '')}")
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

        self.send_json({"theme": theme, "books": generate_preschool_books(theme)})

    def handle_lesson_plan_copier(self) -> None:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length <= 0:
            raise ValueError("No files were uploaded.")
        if content_length > VERCEL_BODY_LIMIT_BYTES:
            raise ValueError(
                "This hosted version can only accept uploads up to about 4.5 MB total on Vercel. "
                "Use the local app for larger lesson-plan files."
            )

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
        _, files = self.parse_multipart_body(max_bytes=25 * 1024 * 1024)
        image_files = [value for key, value in files.items() if key.startswith("images")]
        result = grid_pdf.build_grid_pdf(image_files)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Length", str(len(result)))
        self.send_header("Content-Disposition", 'attachment; filename="2x2.pdf"')
        self.end_headers()
        self.wfile.write(result)

    def _get_auth_token(self) -> str:
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return auth[7:]
        return ""

    def handle_auth_signup(self) -> None:
        data = self.read_json_body()
        email = str(data.get("email", "")).strip()
        password = str(data.get("password", "")).strip()
        if not email or not password:
            raise ValueError("Email and password are required.")
        if len(password) < 6:
            raise ValueError("Password must be at least 6 characters.")
        result = supabase_sync.sign_up(email, password)
        self.send_json(result)

    def handle_auth_login(self) -> None:
        data = self.read_json_body()
        email = str(data.get("email", "")).strip()
        password = str(data.get("password", "")).strip()
        if not email or not password:
            raise ValueError("Email and password are required.")
        result = supabase_sync.sign_in(email, password)
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
        data = self.read_json_body()
        result = supabase_sync.save_plan(token, data)
        self.send_json({"plan": result})

    def handle_sync_load(self) -> None:
        token = self._get_auth_token()
        if not token:
            self.send_json({"error": "Authentication required."}, HTTPStatus.UNAUTHORIZED)
            return
        data = self.read_json_body()
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
        data = self.read_json_body()
        ok = supabase_sync.delete_plan(token, int(data["year"]), int(data["month"]), int(data["weekNumber"]))
        self.send_json({"ok": ok})

    def handle_sync_attachment(self) -> None:
        token = self._get_auth_token()
        if not token:
            self.send_json({"error": "Authentication required."}, HTTPStatus.UNAUTHORIZED)
            return
        parsed = urlparse(self.path)
        from urllib.parse import parse_qs, unquote
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

    def send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
