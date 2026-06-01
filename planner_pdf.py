from __future__ import annotations

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

    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue(), output_filename(plan)
