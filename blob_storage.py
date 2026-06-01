from __future__ import annotations

import base64
import copy
import os
import re
from pathlib import Path
from uuid import uuid4

try:
    from dotenv import load_dotenv
    from vercel.blob import BlobClient
except Exception:  # pragma: no cover - keeps local runs alive without optional deps.
    BlobClient = None
    load_dotenv = None


if load_dotenv:
    load_dotenv(".env.local")


def is_configured() -> bool:
    return bool(os.environ.get("BLOB_READ_WRITE_TOKEN") and BlobClient)


def _safe_path_part(value: str) -> str:
    name = Path(value or "attachment").name.strip() or "attachment"
    return re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-") or "attachment"


def _decode_data_url(value: str) -> bytes:
    if not value.startswith("data:"):
        return b""
    _, _, payload = value.partition(",")
    return base64.b64decode(payload) if payload else b""


def upload_attachment(filename: str, mime_type: str, content: bytes, folder: str = "planner-attachments") -> dict[str, object]:
    if not is_configured():
        raise RuntimeError("Vercel Blob storage is not configured.")
    safe_name = _safe_path_part(filename)
    pathname = f"{folder}/{uuid4().hex}-{safe_name}"
    blob = BlobClient().put(
        pathname,
        content,
        access="public",
        add_random_suffix=False,
        content_type=mime_type or "application/octet-stream",
    )
    return {
        "filename": filename or safe_name,
        "mimeType": mime_type or "application/octet-stream",
        "downloadUrl": blob.download_url,
        "url": blob.url,
        "pathname": blob.pathname,
    }


def upload_file_attachments(files: dict[str, dict[str, object]]) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    if not files:
        return result
    for field_key, item in files.items():
        result[field_key] = upload_attachment(
            str(item.get("filename") or "attachment"),
            str(item.get("mimeType") or "application/octet-stream"),
            bytes(item.get("content") or b""),
        )
    return result


def ensure_plan_attachment_urls(plans: list[dict[str, object]]) -> list[dict[str, object]]:
    if not is_configured():
        return plans

    result = copy.deepcopy(plans)
    for plan in result:
        attachments = plan.get("attachments") or {}
        if not isinstance(attachments, dict):
            continue
        for field_key, item in list(attachments.items()):
            if not isinstance(item, dict) or item.get("downloadUrl"):
                continue
            content = _decode_data_url(str(item.get("dataUrl") or ""))
            if not content:
                continue
            uploaded = upload_attachment(
                str(item.get("filename") or "attachment"),
                str(item.get("mimeType") or "application/octet-stream"),
                content,
            )
            attachments[field_key] = uploaded
    return result
