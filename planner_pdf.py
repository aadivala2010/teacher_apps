from __future__ import annotations

import base64
import re
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.generic import (
    ArrayObject,
    DecodedStreamObject,
    DictionaryObject,
    FloatObject,
    NameObject,
    NumberObject,
    TextStringObject,
)


TEMPLATE_PATH = Path(__file__).resolve().parent / "assets" / "templates" / "lesson-plan-template.pdf"

DAY_KEYS = ["monday", "tuesday", "wednesday", "thursday", "friday"]
DAY_LABELS = ["Mon", "Tues", "Wed", "Thurs", "Fri"]
CENTER_LABELS = {
    "dramatic_play": "Dramatic Play",
    "construction": "Construction",
    "music": "Music",
    "art": "Art",
    "writing": "Writing",
    "manipulative_center": "Manipulative Center",
    "science": "Science",
    "sensory": "Sensory",
    "language_literacy": "Language & Literacy",
}
ATTACHMENT_ORDER = (
    [(f"circle_time.{key}", f"Circle Time - {label}") for key, label in zip(DAY_KEYS, DAY_LABELS)]
    + [(f"small_group_1.{key}", f"Small Group 1 - {label}") for key, label in zip(DAY_KEYS, DAY_LABELS)]
    + [(f"small_group_2.{key}", f"Small Group 2 - {label}") for key, label in zip(DAY_KEYS, DAY_LABELS)]
    + [("outdoor_learning", "Outdoor Learning")]
    + [(f"centers.{key}", f"Centers - {label}") for key, label in CENTER_LABELS.items()]
)


def _activity_text(plan: dict[str, object], section_name: str, key: str) -> str:
    activities = plan.get("activities") or {}
    section = activities.get(section_name) or {}
    item = section.get(key) or {}
    return str(item.get("text") or "")


def _activity_assessment(plan: dict[str, object], section_name: str, key: str) -> str:
    activities = plan.get("activities") or {}
    section = activities.get(section_name) or {}
    item = section.get(key) or {}
    return str(item.get("assessment") or "")


def _normalize_choice(value: str) -> str:
    allowed = {"Checklist", "Observation with Notes", "Portfolio"}
    return value if value in allowed else ""


def _week_label(plan: dict[str, object]) -> str:
    month_label = str(plan.get("monthLabel") or "").strip()
    week_number = str(plan.get("weekNumber") or "").strip()
    if month_label and week_number:
        return f"{month_label} - Week {week_number}"
    if week_number:
        return f"Week {week_number}"
    return ""


def _field_map(plan: dict[str, object]) -> dict[str, str]:
    field_values = {
        "Week": _week_label(plan),
        "Class": str(plan.get("className") or ""),
        "Program": str(plan.get("programName") or ""),
        "Books": str(plan.get("books") or ""),
        "Circle Time  Routines": "",
        "Outdoor Learning": str(plan.get("outdoorLearning") or ""),
        "OLE Assessment": _normalize_choice(str(plan.get("outdoorAssessment") or "")),
        "Dramatic PlayRow1": _activity_text(plan, "centers", "dramatic_play"),
        "ConstructionRow1": _activity_text(plan, "centers", "construction"),
        "MusicRow1": _activity_text(plan, "centers", "music"),
        "ArtRow1": _activity_text(plan, "centers", "art"),
        "WritingRow1": _activity_text(plan, "centers", "writing"),
        "Manipulative CenterRow1": _activity_text(plan, "centers", "manipulative_center"),
        "Science": _activity_text(plan, "centers", "science"),
        "SensoryRow1": _activity_text(plan, "centers", "sensory"),
        "L&L": _activity_text(plan, "centers", "language_literacy"),
        "Dramatic Play": _normalize_choice(_activity_assessment(plan, "centers", "dramatic_play")),
        "Construction": _normalize_choice(_activity_assessment(plan, "centers", "construction")),
        "Music": _normalize_choice(_activity_assessment(plan, "centers", "music")),
        "Art": _normalize_choice(_activity_assessment(plan, "centers", "art")),
        "Writing": _normalize_choice(_activity_assessment(plan, "centers", "writing")),
        "Manipulative Center": _normalize_choice(_activity_assessment(plan, "centers", "manipulative_center")),
        "Science Assessment": _normalize_choice(_activity_assessment(plan, "centers", "science")),
        "Sensory": _normalize_choice(_activity_assessment(plan, "centers", "sensory")),
        "Language & Literacy": _normalize_choice(_activity_assessment(plan, "centers", "language_literacy")),
    }

    for index, day_key in enumerate(DAY_KEYS):
        day_label = DAY_LABELS[index]
        field_values[f"Circle Time {'Mon' if day_key == 'monday' else day_label}"] = _activity_text(
            plan, "circle_time", day_key
        )

    field_values["Circle Time Tues"] = _activity_text(plan, "circle_time", "tuesday")
    field_values["Circle Time Wed"] = _activity_text(plan, "circle_time", "wednesday")
    field_values["Circle Time Thurs"] = _activity_text(plan, "circle_time", "thursday")
    field_values["Circle Time Fri"] = _activity_text(plan, "circle_time", "friday")

    field_values["Circle Time Monday Assessment"] = _normalize_choice(
        _activity_assessment(plan, "circle_time", "monday")
    )
    field_values["Circle Time Tuesday Assessment"] = _normalize_choice(
        _activity_assessment(plan, "circle_time", "tuesday")
    )
    field_values["Circle Time Wed Assessment"] = _normalize_choice(
        _activity_assessment(plan, "circle_time", "wednesday")
    )
    field_values["Circle Time Thurs Assessment"] = _normalize_choice(
        _activity_assessment(plan, "circle_time", "thursday")
    )
    field_values["Circle Time Friday Assessment"] = _normalize_choice(
        _activity_assessment(plan, "circle_time", "friday")
    )

    for index, day_key in enumerate(DAY_KEYS):
        day_label = DAY_LABELS[index]
        field_values[f"Small Group Learning Experiences {day_label} 1"] = _activity_text(
            plan, "small_group_1", day_key
        )
        field_values[f"Small Group Learning Experiences {day_label} 2"] = _activity_text(
            plan, "small_group_2", day_key
        )
        field_values[f"SG {day_label} 1"] = _normalize_choice(_activity_assessment(plan, "small_group_1", day_key))
        field_values[f"SG {day_label} 2"] = _normalize_choice(_activity_assessment(plan, "small_group_2", day_key))

    return field_values


def output_filename(plan: dict[str, object]) -> str:
    month_label = str(plan.get("monthLabel") or "Month").strip().replace("/", "-")
    week_number = str(plan.get("weekNumber") or "Week").strip()
    class_name = str(plan.get("className") or "Class").strip().replace("/", "-")
    return f"Lesson Plan - {month_label} - Week {week_number} - {class_name or 'Class'}.pdf"


def _pdf_literal(text: str) -> str:
    encoded = text.encode("latin-1", errors="replace")
    escaped = []
    for byte in encoded:
        if byte in (40, 41, 92) or byte < 32 or byte > 126:
            escaped.append(f"\\{byte:03o}")
        else:
            escaped.append(chr(byte))
    return "(" + "".join(escaped) + ")"


def _safe_pdf_filename(filename: str) -> str:
    value = Path(filename or "attachment").name.strip() or "attachment"
    return re.sub(r"[\r\n\t]", " ", value)


def _attachment_label(field_key: str) -> str:
    for key, label in ATTACHMENT_ORDER:
        if key == field_key:
            return label
    return field_key.replace(".", " - ").replace("_", " ").title()


def _decode_data_url(value: str) -> bytes:
    if not value.startswith("data:"):
        return b""
    _, _, payload = value.partition(",")
    if not payload:
        return b""
    return base64.b64decode(payload)


def _attachment_items(plan: dict[str, object]) -> list[dict[str, object]]:
    attachments = plan.get("attachments") or {}
    if not isinstance(attachments, dict):
        return []

    ordered_keys = [key for key, _ in ATTACHMENT_ORDER if key in attachments]
    ordered_keys.extend(sorted(key for key in attachments if key not in ordered_keys))

    result = []
    for field_key in ordered_keys:
        item = attachments.get(field_key) or {}
        if not isinstance(item, dict):
            continue
        content = _decode_data_url(str(item.get("dataUrl") or ""))
        if not content:
            continue
        filename = _safe_pdf_filename(str(item.get("filename") or "attachment"))
        result.append(
            {
                "fieldKey": field_key,
                "label": _attachment_label(field_key),
                "filename": filename,
                "mimeType": str(item.get("mimeType") or "application/octet-stream"),
                "content": content,
            }
        )
    return result


def _add_text_page(writer: PdfWriter, lines: list[str]) -> object:
    page = writer.add_blank_page(width=792, height=612)
    resources = DictionaryObject()
    fonts = DictionaryObject()
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
            NameObject("/Encoding"): NameObject("/WinAnsiEncoding"),
        }
    )
    fonts[NameObject("/F1")] = writer._add_object(font)
    resources[NameObject("/Font")] = fonts
    page[NameObject("/Resources")] = resources

    y = 560
    operations = ["BT", "/F1 18 Tf", f"56 {y} Td", _pdf_literal(lines[0]) + " Tj", "ET"]
    y -= 34
    for line in lines[1:]:
        operations.extend(["BT", "/F1 10 Tf", f"56 {y} Td", _pdf_literal(line[:110]) + " Tj", "ET"])
        y -= 22

    stream = DecodedStreamObject()
    stream.set_data("\n".join(operations).encode("latin-1"))
    page[NameObject("/Contents")] = writer._add_object(stream)
    return page


def _add_file_attachment_annotation(writer: PdfWriter, page: object, embedded_file: object, x: float, y: float, label: str) -> None:
    annotation = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Annot"),
            NameObject("/Subtype"): NameObject("/FileAttachment"),
            NameObject("/Rect"): ArrayObject([FloatObject(x), FloatObject(y), FloatObject(x + 18), FloatObject(y + 18)]),
            NameObject("/Contents"): TextStringObject(label),
            NameObject("/Name"): NameObject("/PushPin"),
            NameObject("/FS"): embedded_file.pdf_object.indirect_reference,
            NameObject("/F"): NumberObject(4),
        }
    )
    writer.add_annotation(page, annotation)


def _append_attachments_page(writer: PdfWriter, plan: dict[str, object]) -> None:
    items = _attachment_items(plan)
    items_per_page = 20
    if not items:
        return

    for page_index, offset in enumerate(range(0, len(items), items_per_page), start=1):
        page_items = items[offset : offset + items_per_page]
        title = "Attachments" if len(items) <= items_per_page else f"Attachments {page_index}"
        lines = [title, "Open the file attachment icons below, or use your PDF reader's attachments panel."]
        for index, item in enumerate(page_items, start=offset + 1):
            lines.append(f"{index}. {item['label']}: {item['filename']}")
        page = _add_text_page(writer, lines)

        y = 500
        for item in page_items:
            embedded = writer.add_attachment(str(item["filename"]), bytes(item["content"]))
            embedded.description = TextStringObject(str(item["label"]))
            subtype = "/" + str(item["mimeType"]).replace("/", "#2F")
            embedded.subtype = NameObject(subtype)
            _add_file_attachment_annotation(writer, page, embedded, 58, y - 4, f"{item['label']}: {item['filename']}")
            y -= 22


def build_planner_pdf(plan: dict[str, object]) -> tuple[bytes, str]:
    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"Template PDF was not found at {TEMPLATE_PATH}")

    reader = PdfReader(str(TEMPLATE_PATH))
    writer = PdfWriter()
    writer.append(reader)
    writer.set_need_appearances_writer()
    field_values = _field_map(plan)

    for page in writer.pages:
        writer.update_page_form_field_values(page, field_values, auto_regenerate=True)
    _append_attachments_page(writer, plan)

    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue(), output_filename(plan)
