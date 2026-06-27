from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


if os.environ.get("VERCEL"):
    DB_PATH = Path("/tmp") / "teacher_planner.db"
else:
    DB_PATH = Path(__file__).resolve().parent / "data" / "teacher_planner.db"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                year INTEGER NOT NULL,
                month INTEGER NOT NULL,
                week_number INTEGER NOT NULL,
                week_start TEXT NOT NULL,
                week_end TEXT NOT NULL,
                class_name TEXT NOT NULL DEFAULT '',
                program_name TEXT NOT NULL DEFAULT '',
                books TEXT NOT NULL DEFAULT '',
                outdoor_learning TEXT NOT NULL DEFAULT '',
                outdoor_assessment TEXT NOT NULL DEFAULT '',
                activities_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(year, month, week_number)
            );

            CREATE TABLE IF NOT EXISTS templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                month INTEGER NOT NULL,
                week_number INTEGER NOT NULL,
                template_name TEXT NOT NULL DEFAULT '',
                class_name TEXT NOT NULL DEFAULT '',
                program_name TEXT NOT NULL DEFAULT '',
                books TEXT NOT NULL DEFAULT '',
                outdoor_learning TEXT NOT NULL DEFAULT '',
                outdoor_assessment TEXT NOT NULL DEFAULT '',
                activities_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(month, week_number)
            );

            CREATE TABLE IF NOT EXISTS attachments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_type TEXT NOT NULL,
                owner_id INTEGER NOT NULL,
                field_key TEXT NOT NULL,
                filename TEXT NOT NULL,
                mime_type TEXT NOT NULL,
                content BLOB NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(owner_type, owner_id, field_key)
            );
            """
        )


def _attachment_map(conn: sqlite3.Connection, owner_type: str, owner_id: int) -> dict[str, dict[str, object]]:
    rows = conn.execute(
        """
        SELECT id, field_key, filename, mime_type
        FROM attachments
        WHERE owner_type = ? AND owner_id = ?
        ORDER BY field_key
        """,
        (owner_type, owner_id),
    ).fetchall()
    result: dict[str, dict[str, object]] = {}
    for row in rows:
        result[row["field_key"]] = {
            "id": row["id"],
            "filename": row["filename"],
            "mimeType": row["mime_type"],
            "downloadUrl": f"/api/attachment?id={row['id']}",
        }
    return result


def _serialize_plan(conn: sqlite3.Connection, row: sqlite3.Row) -> dict[str, object]:
    return {
        "id": row["id"],
        "year": row["year"],
        "month": row["month"],
        "weekNumber": row["week_number"],
        "weekStart": row["week_start"],
        "weekEnd": row["week_end"],
        "className": row["class_name"],
        "programName": row["program_name"],
        "books": row["books"],
        "outdoorLearning": row["outdoor_learning"],
        "outdoorAssessment": row["outdoor_assessment"],
        "activities": json.loads(row["activities_json"] or "{}"),
        "attachments": _attachment_map(conn, "plan", row["id"]),
        "updatedAt": row["updated_at"],
    }


def _serialize_template(conn: sqlite3.Connection, row: sqlite3.Row) -> dict[str, object]:
    return {
        "id": row["id"],
        "month": row["month"],
        "weekNumber": row["week_number"],
        "templateName": row["template_name"],
        "className": row["class_name"],
        "programName": row["program_name"],
        "books": row["books"],
        "outdoorLearning": row["outdoor_learning"],
        "outdoorAssessment": row["outdoor_assessment"],
        "activities": json.loads(row["activities_json"] or "{}"),
        "attachments": _attachment_map(conn, "template", row["id"]),
        "updatedAt": row["updated_at"],
    }


def _replace_attachment(
    conn: sqlite3.Connection,
    owner_type: str,
    owner_id: int,
    field_key: str,
    filename: str,
    mime_type: str,
    content: bytes,
) -> None:
    now = utc_now()
    existing = conn.execute(
        """
        SELECT id FROM attachments
        WHERE owner_type = ? AND owner_id = ? AND field_key = ?
        """,
        (owner_type, owner_id, field_key),
    ).fetchone()
    if existing:
        conn.execute(
            """
            UPDATE attachments
            SET filename = ?, mime_type = ?, content = ?, updated_at = ?
            WHERE id = ?
            """,
            (filename, mime_type, content, now, existing["id"]),
        )
        return
    conn.execute(
        """
        INSERT INTO attachments (
            owner_type, owner_id, field_key, filename, mime_type, content, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (owner_type, owner_id, field_key, filename, mime_type, content, now, now),
    )


def _remove_attachments(
    conn: sqlite3.Connection,
    owner_type: str,
    owner_id: int,
    field_keys: list[str],
) -> None:
    if not field_keys:
        return
    conn.executemany(
        """
        DELETE FROM attachments
        WHERE owner_type = ? AND owner_id = ? AND field_key = ?
        """,
        [(owner_type, owner_id, field_key) for field_key in field_keys],
    )


def save_plan(payload: dict[str, object], attachments: dict[str, dict[str, object]]) -> dict[str, object]:
    init_db()
    now = utc_now()
    clear_attachment_fields = list(payload.get("clearAttachmentFields") or [])
    with connect() as conn:
        existing = conn.execute(
            """
            SELECT * FROM plans
            WHERE year = ? AND month = ? AND week_number = ?
            """,
            (payload["year"], payload["month"], payload["weekNumber"]),
        ).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE plans
                SET week_start = ?,
                    week_end = ?,
                    class_name = ?,
                    program_name = ?,
                    books = ?,
                    outdoor_learning = ?,
                    outdoor_assessment = ?,
                    activities_json = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    payload["weekStart"],
                    payload["weekEnd"],
                    payload.get("className", ""),
                    payload.get("programName", ""),
                    payload.get("books", ""),
                    payload.get("outdoorLearning", ""),
                    payload.get("outdoorAssessment", ""),
                    json.dumps(payload.get("activities") or {}, ensure_ascii=True),
                    now,
                    existing["id"],
                ),
            )
            plan_id = existing["id"]
        else:
            cursor = conn.execute(
                """
                INSERT INTO plans (
                    year, month, week_number, week_start, week_end, class_name, program_name,
                    books, outdoor_learning, outdoor_assessment, activities_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["year"],
                    payload["month"],
                    payload["weekNumber"],
                    payload["weekStart"],
                    payload["weekEnd"],
                    payload.get("className", ""),
                    payload.get("programName", ""),
                    payload.get("books", ""),
                    payload.get("outdoorLearning", ""),
                    payload.get("outdoorAssessment", ""),
                    json.dumps(payload.get("activities") or {}, ensure_ascii=True),
                    now,
                    now,
                ),
            )
            plan_id = int(cursor.lastrowid)

        _remove_attachments(conn, "plan", plan_id, clear_attachment_fields)
        for field_key, item in attachments.items():
            _replace_attachment(
                conn,
                "plan",
                plan_id,
                field_key,
                str(item["filename"]),
                str(item["mimeType"]),
                bytes(item["content"]),
            )
        row = conn.execute("SELECT * FROM plans WHERE id = ?", (plan_id,)).fetchone()
        return _serialize_plan(conn, row)


def load_plan(year: int, month: int, week_number: int) -> dict[str, object] | None:
    try:
        init_db()
        with connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM plans
                WHERE year = ? AND month = ? AND week_number = ?
                """,
                (year, month, week_number),
            ).fetchone()
            if not row:
                return None
            return _serialize_plan(conn, row)
    except Exception:
        return None


def save_template(payload: dict[str, object], attachments: dict[str, dict[str, object]]) -> dict[str, object]:
    init_db()
    now = utc_now()
    clear_attachment_fields = list(payload.get("clearAttachmentFields") or [])
    with connect() as conn:
        existing = conn.execute(
            """
            SELECT * FROM templates
            WHERE month = ? AND week_number = ?
            """,
            (payload["month"], payload["weekNumber"]),
        ).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE templates
                SET template_name = ?,
                    class_name = ?,
                    program_name = ?,
                    books = ?,
                    outdoor_learning = ?,
                    outdoor_assessment = ?,
                    activities_json = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    payload.get("templateName", ""),
                    payload.get("className", ""),
                    payload.get("programName", ""),
                    payload.get("books", ""),
                    payload.get("outdoorLearning", ""),
                    payload.get("outdoorAssessment", ""),
                    json.dumps(payload.get("activities") or {}, ensure_ascii=True),
                    now,
                    existing["id"],
                ),
            )
            template_id = existing["id"]
        else:
            cursor = conn.execute(
                """
                INSERT INTO templates (
                    month, week_number, template_name, class_name, program_name, books,
                    outdoor_learning, outdoor_assessment, activities_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["month"],
                    payload["weekNumber"],
                    payload.get("templateName", ""),
                    payload.get("className", ""),
                    payload.get("programName", ""),
                    payload.get("books", ""),
                    payload.get("outdoorLearning", ""),
                    payload.get("outdoorAssessment", ""),
                    json.dumps(payload.get("activities") or {}, ensure_ascii=True),
                    now,
                    now,
                ),
            )
            template_id = int(cursor.lastrowid)

        _remove_attachments(conn, "template", template_id, clear_attachment_fields)
        for field_key, item in attachments.items():
            _replace_attachment(
                conn,
                "template",
                template_id,
                field_key,
                str(item["filename"]),
                str(item["mimeType"]),
                bytes(item["content"]),
            )
        row = conn.execute("SELECT * FROM templates WHERE id = ?", (template_id,)).fetchone()
        return _serialize_template(conn, row)


def load_template(month: int, week_number: int) -> dict[str, object] | None:
    try:
        init_db()
        with connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM templates
                WHERE month = ? AND week_number = ?
                """,
                (month, week_number),
            ).fetchone()
            if not row:
                return None
            return _serialize_template(conn, row)
    except Exception:
        return None


def get_attachment(attachment_id: int) -> dict[str, object] | None:
    init_db()
    with connect() as conn:
        row = conn.execute(
            """
            SELECT id, filename, mime_type, content
            FROM attachments
            WHERE id = ?
            """,
            (attachment_id,),
        ).fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "filename": row["filename"],
            "mimeType": row["mime_type"],
            "content": row["content"],
        }
