from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from activity_descriptor_pptx import _format_date_long

ASSETS = Path(__file__).resolve().parent / "assets"
BG_PATH = ASSETS / "templates" / "activity_descriptor_bg.png"  # slide rendered at 300 DPI with content boxes blanked
TIMES_PATH = ASSETS / "fonts" / "times.ttf"
TWCEN_PATH = ASSETS / "fonts" / "twcenmt.ttf"

DPI = 300
SLIDE_WIDTH_EMU = 7772400  # 8.5in x 11in slide, same as the pptx template
PX_PER_EMU = 2550 / SLIDE_WIDTH_EMU
PX_PER_PT = DPI / 72.0

FONT_PT = 12.0
MIN_FONT_PT = 8.0
LINE_HEIGHT_FACTOR = 1.1
LINE_SPACING_AFTER_PT = 3.0
MARGIN_EMU = 36576  # text-box inset on every side

# Text-box rects from templates/activity_descriptor.pptx (EMU): left, top, width, bottom.
# Bottoms are capped at the colored layout card behind each box where the card is tighter.
DATE_BOX = (1463066, 2606666, 5240338, 3006717)
CONTENT_BOXES = {
    "activity": (753156, 3370619, 6283325, 5603630),
    "skills": (753156, 6136630, 6283325, 8100367),
    "links": (753156, 8500441, 6194425, 9606587),
}


def _font(path: Path, size_pt: float) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), int(round(size_pt * PX_PER_PT)))


def _wrap(text: str, font: ImageFont.FreeTypeFont, width_px: float) -> list[str]:
    """Word-wrap each \n-paragraph to the box width using real font metrics."""
    lines: list[str] = []
    for para in text.split("\n"):
        cur = ""
        for word in para.split(" "):
            trial = f"{cur} {word}" if cur else word
            if cur and font.getlength(trial) > width_px:
                lines.append(cur)
                cur = word
            else:
                cur = trial
        lines.append(cur)
    return lines


def _fit_size_pt(text: str, box: tuple[int, int, int, int]) -> float:
    """Largest size in [MIN_FONT_PT, FONT_PT] (0.5pt steps) whose wrapped text fits the box height."""
    left, top, width, bottom = box
    inner_w = (width - 2 * MARGIN_EMU) * PX_PER_EMU
    inner_h = (bottom - top - 2 * MARGIN_EMU) * PX_PER_EMU
    paragraphs = text.split("\n")
    size = FONT_PT
    while size > MIN_FONT_PT:
        font = _font(TIMES_PATH, size)
        n_lines = len(_wrap(text, font, inner_w))
        height = (n_lines * size * LINE_HEIGHT_FACTOR + len(paragraphs) * LINE_SPACING_AFTER_PT) * PX_PER_PT
        if height <= inner_h:
            return size
        size -= 0.5
    return MIN_FONT_PT


def _draw_text(draw: ImageDraw.ImageDraw, text: str, box: tuple[int, int, int, int], font: ImageFont.FreeTypeFont, size_pt: float) -> None:
    left, top, width, _ = box
    x = (left + MARGIN_EMU) * PX_PER_EMU
    y = (top + MARGIN_EMU) * PX_PER_EMU
    inner_w = (width - 2 * MARGIN_EMU) * PX_PER_EMU
    for para in text.split("\n"):
        for line in _wrap(para, font, inner_w):
            draw.text((x, y), line, font=font, fill=(0, 0, 0))
            y += size_pt * LINE_HEIGHT_FACTOR * PX_PER_PT
        y += LINE_SPACING_AFTER_PT * PX_PER_PT


def build_activity_descriptor_pdf(payload: dict) -> tuple[bytes, str]:
    raw_date = str(payload.get("date", ""))
    activities = payload.get("activities", [])
    skills = payload.get("skills", [])
    links = payload.get("links", [])

    texts = {
        "activity": "\n".join(a for a in activities if a),
        "skills": "\n".join(f"- {s}" for s in skills if s),
        "links": "\n".join(f"• {l}" for l in links if l),
    }

    img = Image.open(BG_PATH).convert("RGB")
    draw = ImageDraw.Draw(img)

    date_str = _format_date_long(raw_date)
    if date_str:
        _draw_text(draw, date_str, DATE_BOX, _font(TWCEN_PATH, FONT_PT), FONT_PT)

    # One shared size for all content boxes: whatever the fullest box needs.
    shared = min((_fit_size_pt(t, CONTENT_BOXES[k]) for k, t in texts.items() if t), default=FONT_PT)
    font = _font(TIMES_PATH, shared)
    for key, text in texts.items():
        if text:
            _draw_text(draw, text, CONTENT_BOXES[key], font, shared)

    buf = BytesIO()
    img.save(buf, "PDF", resolution=float(DPI))
    return buf.getvalue(), f"activity_descriptor_{raw_date or 'export'}.pdf"
