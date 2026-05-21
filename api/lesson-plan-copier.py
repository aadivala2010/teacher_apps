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

import table_app


VERCEL_BODY_LIMIT_BYTES = 4_500_000


class handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        try:
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
