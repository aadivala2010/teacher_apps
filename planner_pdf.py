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

LINE_HEIGHT_FACTOR = 1.25
MIN_FONT_SIZE = 4.0
PAD_X = 4.0  # left+right widget padding
PAD_Y = 4.0  # top+bottom widget padding

# Boxes that sit side by side in one row share one font size, so a row always
# looks uniform — but a short row (Centers) can't starve a tall row (Circle
# Time) into tiny text with half the box left empty. Single-line banner fields
# are excluded: their boxes are too short for the multiline height math; they
# only shrink if their text overflows the width.
SINGLE_LINE_FIELDS = {"Week", "Class", "Program", "Books"}
UNIFORM_MAX_SIZE = 12.0

# The routines row is the same every week, so it isn't part of the plan data.
ROUTINES_TEXT = (
    'Calendar and weather. Songs: "Days of the Week", "Months in a Year", '
    'Winter songs, Spanish vocabulary. Create our letter of the week word list. '
    "Review our sight words."
)


def _row_of(name: str) -> str | None:
    if name.startswith("Circle Time") and "Routines" not in name:
        return "circle"
    if name.startswith("Small Group"):
        return "sg1" if name.endswith("1") else "sg2"
    if name in {"Dramatic PlayRow1", "ConstructionRow1", "MusicRow1", "ArtRow1", "WritingRow1",
                "Manipulative CenterRow1", "Science", "SensoryRow1", "L&L"}:
        return "centers"
    if name in SINGLE_LINE_FIELDS:
        return None
    return name  # Outdoor Learning etc.: a row of its own

# Standard Helvetica AFM advance widths (1/1000 em) for ASCII — the exact
# metrics of the /Helv font the fields render with, so wrapping is computed
# the same way the PDF viewer computes it.
_HELV_WIDTHS = {
    " ": 278, "!": 278, '"': 355, "#": 556, "$": 556, "%": 889, "&": 667, "'": 191,
    "(": 333, ")": 333, "*": 389, "+": 584, ",": 278, "-": 333, ".": 278, "/": 278,
    "0": 556, "1": 556, "2": 556, "3": 556, "4": 556, "5": 556, "6": 556, "7": 556,
    "8": 556, "9": 556, ":": 278, ";": 278, "<": 584, "=": 584, ">": 584, "?": 556,
    "@": 1015, "A": 667, "B": 667, "C": 722, "D": 722, "E": 667, "F": 611, "G": 778,
    "H": 722, "I": 278, "J": 500, "K": 667, "L": 556, "M": 833, "N": 722, "O": 778,
    "P": 667, "Q": 778, "R": 722, "S": 667, "T": 611, "U": 722, "V": 667, "W": 944,
    "X": 667, "Y": 667, "Z": 611, "[": 278, "\\": 278, "]": 278, "^": 469, "_": 556,
    "`": 333, "a": 556, "b": 556, "c": 500, "d": 556, "e": 556, "f": 278, "g": 556,
    "h": 556, "i": 222, "j": 222, "k": 500, "l": 222, "m": 833, "n": 556, "o": 556,
    "p": 556, "q": 556, "r": 333, "s": 500, "t": 278, "u": 556, "v": 500, "w": 722,
    "x": 500, "y": 500, "z": 500, "{": 334, "|": 260, "}": 334, "~": 584,
}
_SPACE_W = 278


def _text_units(text: str) -> float:
    return sum(_HELV_WIDTHS.get(ch, 556) for ch in text)


def _split_long_word(word: str, budget_units: float) -> list[str]:
    """Break a word wider than the whole line into chunks that fit, like the renderer does."""
    chunks: list[str] = []
    cur, cur_w = "", 0.0
    for ch in word:
        w = _HELV_WIDTHS.get(ch, 556)
        if cur and cur_w + w > budget_units:
            chunks.append(cur)
            cur, cur_w = ch, w
        else:
            cur += ch
            cur_w += w
    chunks.append(cur)
    return chunks


def _wrap_to_lines(text: str, budget_units: float) -> list[str]:
    """Word-wrap text into lines at most `budget_units` wide (1/1000 em units)."""
    lines: list[str] = []
    for para in str(text).split("\n"):
        words = [chunk for word in para.split(" ") for chunk in _split_long_word(word, budget_units)]
        cur_words: list[str] = []
        cur_w = 0.0
        for word in words:
            w = _text_units(word)
            if cur_words and cur_w + _SPACE_W + w > budget_units:
                lines.append(" ".join(cur_words))
                cur_words, cur_w = [word], w
            else:
                cur_words.append(word)
                cur_w += (_SPACE_W if cur_w else 0) + w
        lines.append(" ".join(cur_words))
    return lines


def _wrapped_line_count(text: str, budget_units: float) -> int:
    """Lines needed to word-wrap text into a line `budget_units` wide (1/1000 em units)."""
    return len(_wrap_to_lines(text, budget_units))


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
        "Circle Time  Routines": ROUTINES_TEXT,
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
    if not str(text).strip():
        return max_size

    usable_width = max(1.0, field_width - PAD_X)
    usable_height = max(1.0, field_height - PAD_Y)
    lo, hi = MIN_FONT_SIZE, max_size
    for _ in range(12):
        mid = (lo + hi) / 2
        lines_needed = _wrapped_line_count(text, usable_width * 1000.0 / mid)
        if lines_needed * LINE_HEIGHT_FACTOR * mid <= usable_height:
            lo = mid
        else:
            hi = mid
    # Always round DOWN so the result definitely fits
    return math.floor(lo * 10) / 10


def _auto_fit_text_fields(writer: PdfWriter, field_values: dict[str, str]) -> list[tuple]:
    fields_obj = writer.root_object.get("/AcroForm")
    if fields_obj is None:
        return []
    field_entries = fields_obj.get("/Fields")
    if field_entries is None:
        return []

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

    from pypdf.generic import NameObject, NumberObject, create_string_object

    _walk_fields(field_entries)

    # One shared size for every content box: the largest size (capped at the
    # Small Group style's 8pt) at which the fullest box still fits.
    row_sizes: dict[str, float] = {}
    for _, name, _, _, width, height in collected:
        text = field_values.get(name)
        row = _row_of(name)
        if not text or row is None:
            continue
        size = _optimal_font_size(text, width, height, UNIFORM_MAX_SIZE)
        row_sizes[row] = min(row_sizes.get(row, UNIFORM_MAX_SIZE), size)

    # Always /Helv: the template's fields declare Calibri, which pypdf has no
    # width data for — appearance streams then silently fall back to Helvetica
    # while viewers that regenerate use real Calibri, so boxes render in
    # visibly different fonts. Helv is a standard font every renderer agrees on.
    sized: list[tuple] = []
    for entry, name, _, current_size, width, height in collected:
        row = _row_of(name)
        text = field_values.get(name)
        if row is None:
            new_size = current_size
            if text:
                width_fit = math.floor((width - PAD_X) * 1000.0 / _text_units(text) * 10) / 10
                new_size = max(MIN_FONT_SIZE, min(current_size, width_fit))
        else:
            new_size = row_sizes.get(row, UNIFORM_MAX_SIZE)
            # Bake explicit newlines and the multiline flag into the field, because
            # printers/browsers use the stored appearance stream, which never
            # word-wraps on its own — relying on the viewer to re-wrap is what made
            # printed plans show one long clipped line.
            entry[NameObject("/Ff")] = NumberObject(int(entry.get("/Ff", 0)) | 4096)
            if text:
                field_values[name] = "\n".join(_wrap_to_lines(text, (width - PAD_X) * 1000.0 / new_size))
        entry[NameObject("/DA")] = create_string_object(f"/Helv {new_size} Tf 0 g")
        sized.append((entry, name, new_size, width, height))
    return sized


def _pdf_escape(line: str) -> str:
    out = line.encode("latin-1", "replace").decode("latin-1")
    for ch in ("\\", "(", ")"):
        out = out.replace(ch, "\\" + ch)
    return out


def _write_appearances(writer: PdfWriter, sized: list[tuple], field_values: dict[str, str]) -> None:
    """Draw each text field's own appearance stream, one Tj per wrapped line.

    pypdf's generated appearances put the whole value on a single clipped line
    and hex-encode some of them as UTF-16 against a simple font, so viewers that
    render the stored appearance instead of regenerating it (iOS Safari/Files,
    most printers) showed clipped, letter-spaced garbage. With real appearances
    baked in, /NeedAppearances is off and every viewer draws the same thing.
    """
    from pypdf.generic import (
        ArrayObject,
        BooleanObject,
        DecodedStreamObject,
        DictionaryObject,
        FloatObject,
        NameObject,
    )

    acroform = writer.root_object["/AcroForm"]
    resources = acroform.get("/DR", DictionaryObject())

    for entry, name, size, width, height in sized:
        lines = str(field_values.get(name) or "").split("\n")
        ops = [
            "/Tx BMC",
            "q",
            f"1 1 {width - 2:.2f} {height - 2:.2f} re W n",
            "BT",
            f"/Helv {size} Tf 0 g",
            f"{PAD_X / 2:.2f} {height - PAD_Y / 2 - size:.2f} Td",
            f"{size * LINE_HEIGHT_FACTOR:.2f} TL",
        ]
        for line in lines:
            ops.append(f"({_pdf_escape(line)}) Tj T*")
        ops += ["ET", "Q", "EMC"]

        stream = DecodedStreamObject()
        stream.set_data("\n".join(ops).encode("latin-1"))
        stream[NameObject("/Type")] = NameObject("/XObject")
        stream[NameObject("/Subtype")] = NameObject("/Form")
        stream[NameObject("/BBox")] = ArrayObject(
            [FloatObject(0), FloatObject(0), FloatObject(width), FloatObject(height)]
        )
        stream[NameObject("/Resources")] = resources
        ap = DictionaryObject()
        ap[NameObject("/N")] = writer._add_object(stream)
        entry[NameObject("/AP")] = ap

    acroform[NameObject("/NeedAppearances")] = BooleanObject(False)


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
    field_values = _field_map(plan)

    sized = _auto_fit_text_fields(writer, field_values)

    for page in writer.pages:
        writer.update_page_form_field_values(page, field_values, auto_regenerate=True)

    # After update_page_form_field_values, which overwrites /AP with its own.
    _write_appearances(writer, sized, field_values)

    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue(), output_filename(plan)


def _self_check() -> None:
    """Appearance streams must hold the real, wrapped, latin-1 text — not UTF-16 hex."""
    long_text = "Children explore the winter sensory bin with scoops and tongs while naming what they find."
    data, _ = build_planner_pdf(
        {"monthLabel": "January", "weekNumber": "2", "className": "Room 3",
         "activities": {"circle_time": {"monday": {"text": long_text}}}}
    )
    reader = PdfReader(BytesIO(data))
    assert reader.trailer["/Root"]["/AcroForm"]["/NeedAppearances"].value is False

    streams = {}

    def walk(entries):
        for ref in entries:
            entry = ref.get_object()
            if entry.get("/Kids"):
                walk(entry["/Kids"])
            elif entry.get("/FT") == "/Tx" and entry.get("/AP"):
                streams[str(entry.get("/T"))] = entry["/AP"]["/N"].get_data().decode("latin-1")

    walk(reader.trailer["/Root"]["/AcroForm"]["/Fields"])
    circle = streams["Circle Time Mon"]
    assert "(Children explore the winter" in circle, circle
    assert circle.count(") Tj") > 1, "long text must be drawn as several wrapped lines"
    assert "sight words.) Tj" in streams["Circle Time  Routines"], "routines text must not be clipped"
    print("ok")


if __name__ == "__main__":
    _self_check()
