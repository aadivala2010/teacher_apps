from __future__ import annotations

import math
import re
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader, PdfWriter


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

# Average character width as a fraction of font size for Calibri/Helvetica
CHAR_WIDTH_FACTOR = 0.50
LINE_HEIGHT_FACTOR = 1.35
MIN_FONT_SIZE = 4.0

# All content boxes share one font size (the Small Group / Learning Experiences
# style, Calibri 8) so the page looks uniform; only these header fields keep
# their own independent size.
HEADER_FIELDS = {"Week", "Class", "Program"}
UNIFORM_MAX_SIZE = 8.0


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


def _optimal_font_size(text: str, field_width: float, field_height: float, max_size: float) -> float:
    text_len = len(str(text))
    if text_len == 0:
        return max_size

    # Safety margin: reserve 3pt at top and bottom
    usable_height = max(1.0, field_height - 6.0)
    lo, hi = MIN_FONT_SIZE, max_size
    for _ in range(12):
        mid = (lo + hi) / 2
        chars_per_line = max(1, field_width / (CHAR_WIDTH_FACTOR * mid))
        lines_needed = (text_len + chars_per_line - 1) // chars_per_line
        height_needed = lines_needed * LINE_HEIGHT_FACTOR * mid
        if height_needed <= usable_height:
            lo = mid
        else:
            hi = mid
    # Always round DOWN so the result definitely fits
    return math.floor(lo * 10) / 10


def _auto_fit_text_fields(writer: PdfWriter, field_values: dict[str, str]) -> None:
    fields_obj = writer.root_object.get("/AcroForm")
    if fields_obj is None:
        return
    field_entries = fields_obj.get("/Fields")
    if field_entries is None:
        return

    re_da = re.compile(r"^\s*/(\w+)\s+([\d.]+)\s+Tf\s")
    collected: list[tuple[object, str, str, float, float, float]] = []

    def _walk_fields(entries: list) -> None:
        for entry_ref in entries:
            entry = entry_ref.get_object()
            kids = entry.get("/Kids")
            if kids:
                _walk_fields(kids)
                continue
            name = entry.get("/T")
            if not name or not isinstance(name, str):
                continue
            if entry.get("/FT") != "/Tx":
                continue
            rect = entry.get("/Rect")
            if not rect:
                continue
            x1, y1, x2, y2 = rect
            width = float(x2) - float(x1)
            height = float(y2) - float(y1)
            if width <= 0 or height <= 0:
                continue
            m = re_da.match(str(entry.get("/DA", "")))
            if not m:
                continue
            collected.append((entry, name, m.group(1), float(m.group(2)), width, height))

    try:
        from pypdf.generic import NameObject, create_string_object
    except ImportError:
        return
    _walk_fields(field_entries)

    # One shared size for every content box: the largest size (capped at the
    # Small Group style's 8pt) at which the fullest box still fits.
    uniform_size = UNIFORM_MAX_SIZE
    for _, name, _, _, width, height in collected:
        text = field_values.get(name)
        if not text or name in HEADER_FIELDS:
            continue
        uniform_size = min(uniform_size, _optimal_font_size(text, width, height, UNIFORM_MAX_SIZE))

    for entry, name, font_name, current_size, width, height in collected:
        if name in HEADER_FIELDS:
            text = field_values.get(name)
            if not text:
                continue
            new_size = _optimal_font_size(text, width, height, current_size)
            if new_size >= current_size:
                continue
        else:
            new_size = uniform_size
        entry[NameObject("/DA")] = create_string_object(f"/{font_name} {new_size} Tf 0 g")


def output_filename(plan: dict[str, object]) -> str:
    month_label = str(plan.get("monthLabel") or "Month").strip().replace("/", "-")
    week_number = str(plan.get("weekNumber") or "Week").strip()
    class_name = str(plan.get("className") or "Class").strip().replace("/", "-")
    return f"Lesson Plan - {month_label} - Week {week_number} - {class_name or 'Class'}.pdf"


def build_planner_pdf(plan: dict[str, object]) -> tuple[bytes, str]:
    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"Template PDF was not found at {TEMPLATE_PATH}")

    reader = PdfReader(str(TEMPLATE_PATH))
    writer = PdfWriter()
    writer.append(reader)
    writer.set_need_appearances_writer()
    field_values = _field_map(plan)

    _auto_fit_text_fields(writer, field_values)

    for page in writer.pages:
        writer.update_page_form_field_values(page, field_values, auto_regenerate=True)

    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue(), output_filename(plan)
