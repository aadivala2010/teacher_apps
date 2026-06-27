from __future__ import annotations

import base64
import json
import os
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

try:
    from dotenv import load_dotenv
    load_dotenv(".env.local")
except Exception:
    pass

_SUPABASE_URL: str | None = None
_SUPABASE_SERVICE_KEY: str | None = None
_SUPABASE_ANON_KEY: str | None = None
_SUPABASE_CLIENT: Any = None
_SUPABASE_SERVICE_CLIENT: Any = None
_BUCKET_NAME = "plan-storage"


def _setup():
    global _SUPABASE_URL, _SUPABASE_SERVICE_KEY, _SUPABASE_ANON_KEY, _SUPABASE_CLIENT, _SUPABASE_SERVICE_CLIENT
    _SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip() or "https://vheanpauzuooflrmvrkw.supabase.co"
    _SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "").strip() or ""
    _SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "").strip() or ""

    if not _SUPABASE_ANON_KEY and not _SUPABASE_SERVICE_KEY:
        return

    if not _SUPABASE_ANON_KEY:
        _SUPABASE_ANON_KEY = _SUPABASE_SERVICE_KEY

    try:
        from supabase import create_client

        if _SUPABASE_CLIENT is None and _SUPABASE_ANON_KEY:
            _SUPABASE_CLIENT = create_client(_SUPABASE_URL, _SUPABASE_ANON_KEY)
        if _SUPABASE_SERVICE_CLIENT is None and _SUPABASE_SERVICE_KEY:
            _SUPABASE_SERVICE_CLIENT = create_client(_SUPABASE_URL, _SUPABASE_SERVICE_KEY)
    except Exception:
        pass


def is_configured() -> bool:
    if _SUPABASE_CLIENT is None:
        _setup()
    return _SUPABASE_CLIENT is not None


def _admin() -> Any:
    if not is_configured():
        raise RuntimeError("Supabase is not configured.")
    return _SUPABASE_SERVICE_CLIENT or _SUPABASE_CLIENT


def _client() -> Any:
    if not is_configured():
        raise RuntimeError("Supabase is not configured.")
    return _SUPABASE_CLIENT


def init_bucket() -> None:
    if not is_configured():
        return
    admin = _admin()
    try:
        admin.storage.get_bucket(_BUCKET_NAME)
    except Exception:
        try:
            admin.storage.create_bucket(_BUCKET_NAME)
        except Exception:
            pass


def _bucket() -> Any:
    return _admin().storage.from_(_BUCKET_NAME)


def sign_up(email: str, password: str) -> dict[str, Any]:
    admin = _admin()
    try:
        result = admin.auth.admin.create_user({
            "email": email,
            "password": password,
            "email_confirm": True,
        })
        if result and result.user:
            return sign_in(email, password)
    except Exception:
        pass

    try:
        users = admin.auth.admin.list_users()
        for u in users:
            if hasattr(u, "email") and u.email == email:
                if not u.email_confirmed_at:
                    admin.auth.admin.update_user_by_id(u.id, {"email_confirm": True})
                break
    except Exception:
        pass

    return sign_in(email, password)


def sign_in(email: str, password: str) -> dict[str, Any]:
    client = _client()
    try:
        result = client.auth.sign_in_with_password({"email": email, "password": password})
        return _auth_result(result)
    except Exception as exc:
        print(f"[supabase_sync] sign_in error for {email}: {exc}", flush=True)
        raise


def _auth_result(result: Any) -> dict[str, Any]:
    if not result:
        raise ValueError("Authentication returned no result.")
    user = result.user
    session = result.session
    if not user or not session:
        raise ValueError("Authentication failed.")
    return {
        "user": {
            "id": str(user.id),
            "email": user.email or "",
        },
        "session": {
            "access_token": session.access_token or "",
            "refresh_token": session.refresh_token or "",
            "expires_at": session.expires_at or 0,
        },
    }


def get_user(access_token: str) -> dict[str, Any] | None:
    client = _client()
    try:
        result = client.auth.get_user(access_token)
        if result and result.user:
            return {
                "id": str(result.user.id),
                "email": result.user.email or "",
            }
    except Exception:
        pass
    return None


def _plan_path(user_id: str, year: int, month: int, week_number: int) -> str:
    return f"{user_id}/plans/{year}-{month:02d}-{week_number}.json"


def _plan_list_prefix(user_id: str) -> str:
    return f"{user_id}/plans/"


def _parse_path_key(path: str) -> tuple[int, int, int] | None:
    name = path.rsplit("/", 1)[-1].replace(".json", "")
    parts = name.split("-")
    if len(parts) >= 3:
        try:
            return int(parts[0]), int(parts[1]), int(parts[2])
        except ValueError:
            pass
    return None


def save_plan(access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
    user = get_user(access_token)
    if not user:
        raise ValueError("Invalid access token.")
    init_bucket()

    plan_data = {
        "year": int(payload["year"]),
        "month": int(payload["month"]),
        "weekNumber": int(payload["weekNumber"]),
        "weekStart": payload.get("weekStart", ""),
        "weekEnd": payload.get("weekEnd", ""),
        "className": payload.get("className", ""),
        "programName": payload.get("programName", ""),
        "books": payload.get("books", ""),
        "outdoorLearning": payload.get("outdoorLearning", ""),
        "outdoorAssessment": payload.get("outdoorAssessment", ""),
        "activities": payload.get("activities") or {},
        "attachments": payload.get("attachments") or {},
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }

    path = _plan_path(user["id"], plan_data["year"], plan_data["month"], plan_data["weekNumber"])
    content = json.dumps(plan_data, ensure_ascii=True).encode("utf-8")

    try:
        _bucket().remove(path)
    except Exception:
        pass

    try:
        bucket = _bucket()
        bucket.upload(path, content, {"content-type": "application/json"})
    except Exception:
        pass

    result = dict(plan_data)
    result["id"] = 0
    return result


def load_plan(access_token: str, year: int, month: int, week_number: int) -> dict[str, Any] | None:
    user = get_user(access_token)
    if not user:
        raise ValueError("Invalid access token.")
    init_bucket()

    path = _plan_path(user["id"], year, month, week_number)
    try:
        content = _bucket().download(path)
        if isinstance(content, bytes):
            content = content.decode("utf-8")
        data = json.loads(content)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return None


def list_plans(access_token: str) -> list[dict[str, Any]]:
    user = get_user(access_token)
    if not user:
        raise ValueError("Invalid access token.")
    init_bucket()

    prefix = _plan_list_prefix(user["id"])
    plans: list[dict[str, Any]] = []

    try:
        bucket = _bucket()
        objects = bucket.list(prefix)
        for obj in objects:
            name = None
            if isinstance(obj, dict):
                name = obj.get("name", "")
            elif hasattr(obj, "name"):
                name = obj.name
            if not name or not str(name).endswith(".json"):
                continue
            full_path = prefix + str(name)
            try:
                content = bucket.download(full_path)
                if isinstance(content, bytes):
                    content = content.decode("utf-8")
                data = json.loads(content)
                if isinstance(data, dict):
                    plans.append(data)
            except Exception:
                pass
    except Exception:
        pass

    plans.sort(key=lambda p: (p.get("year", 0), p.get("month", 0), p.get("weekNumber", 0)))
    return plans


def delete_plan(access_token: str, year: int, month: int, week_number: int) -> bool:
    user = get_user(access_token)
    if not user:
        raise ValueError("Invalid access token.")
    init_bucket()

    path = _plan_path(user["id"], year, month, week_number)
    try:
        _bucket().remove(path)
        return True
    except Exception:
        pass
    return False


def save_attachment(
    access_token: str,
    owner_year: int,
    owner_month: int,
    owner_week_number: int,
    field_key: str,
    filename: str,
    mime_type: str,
    content: bytes,
) -> dict[str, Any]:
    user = get_user(access_token)
    if not user:
        raise ValueError("Invalid access token.")
    init_bucket()

    path = f"{user['id']}/attachments/{owner_year}-{owner_month:02d}-{owner_week_number:02d}/{field_key}_{filename}"
    try:
        _bucket().upload(path, content, {"content-type": mime_type, "upsert": "true"})
    except Exception:
        try:
            _bucket().update(path, content, {"content-type": mime_type, "upsert": "true"})
        except Exception:
            _bucket().remove(path)
            _bucket().upload(path, content, {"content-type": mime_type})

    import hashlib
    attachment_id = hashlib.md5(path.encode()).hexdigest()[:12]

    return {
        "fieldKey": field_key,
        "filename": filename,
        "mimeType": mime_type,
        "downloadUrl": f"/api/sync-attachment?path={quote(path, safe='')}",
        "attachmentId": attachment_id,
    }


def get_attachment(access_token: str, path: str) -> dict[str, Any] | None:
    user = get_user(access_token)
    if not user:
        raise ValueError("Invalid access token.")
    init_bucket()

    if not path.startswith(user["id"] + "/attachments/"):
        return None

    try:
        content = _bucket().download(path)
        if not isinstance(content, bytes):
            content = b""
        name = path.rsplit("/", 1)[-1]
        if "_" in name:
            _, _, filename = name.partition("_")
            if not filename:
                filename = name
        else:
            filename = name
        return {
            "id": 0,
            "filename": filename,
            "mimeType": "application/octet-stream",
            "content": content,
        }
    except Exception:
        pass
    return None
