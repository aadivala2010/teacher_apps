#!/usr/bin/env python3
"""Transfer DOCX table cell text onto matching PDF table cells.

The preferred path detects table cell rectangles from vector lines in the PDF,
then maps DOCX table cells onto those rectangles in reading order. If the PDF
does not expose table lines as vector paths, a conservative DOCX-geometry
fallback is available for simple one-table documents.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import math
import re
import shutil
import subprocess
import sys
import threading
import unicodedata
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from docx import Document
from docx.table import _Cell
from docx.oxml.ns import qn
from lxml import etree
from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, ContentStream, DecodedStreamObject, DictionaryObject, NameObject


EMU_PER_POINT = 12700
DXA_PER_POINT = 20
WORD_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
OVERLAY_BEGIN = "% TABLE_APP_OVERLAY_BEGIN"
OVERLAY_END = "% TABLE_APP_OVERLAY_END"


@dataclass(frozen=True)
class CellText:
    table_index: int
    row_index: int
    col_index: int
    text: str
    highlighted: bool = False


@dataclass(frozen=True)
class Rect:
    page_index: int
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def width(self) -> float:
        return max(0.0, self.x1 - self.x0)

    @property
    def height(self) -> float:
        return max(0.0, self.y1 - self.y0)


def normalize_word_text(text: str) -> str:
    replacements = {
        "\u00ad": "",
        "\u200b": "",
        "\u200c": "",
        "\u200d": "",
        "\ufeff": "",
        "\u2010": "-",
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
    }
    chars: list[str] = []
    for char in text:
        if char in replacements:
            chars.append(replacements[char])
            continue
        category = unicodedata.category(char)
        if category == "Zs":
            chars.append(" ")
        elif category in {"Zl", "Zp"}:
            chars.append("\n")
        elif category.startswith("C") and char not in {"\n", "\r", "\t"}:
            chars.append(" ")
        else:
            chars.append(char)
    return "".join(chars)


def clean_cell_text(text: str) -> str:
    text = normalize_word_text(text)
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def extract_docx_cells(docx_path: Path) -> list[CellText]:
    return [cell for row in extract_docx_cell_rows(docx_path) for cell in row]


def is_highlighted_cell(tc) -> bool:
    shd = tc.find(".//w:tcPr/w:shd", WORD_NS)
    if shd is not None:
        fill = shd.get(qn("w:fill"))
        if fill and str(fill).upper() not in {"AUTO", "FFFFFF", "D9D9D9", "BFBFBF"}:
            return True
    highlights = tc.findall(".//w:highlight", WORD_NS)
    return any(node.get(qn("w:val"), "").lower() not in {"", "none"} for node in highlights)


def extract_docx_cell_rows(docx_path: Path) -> list[list[CellText]]:
    doc = Document(str(docx_path))
    rows: list[list[CellText]] = []
    for table_index, table in enumerate(doc.tables):
        for row_index, row in enumerate(table.rows):
            row_cells: list[CellText] = []
            for col_index, tc in enumerate(row._tr.tc_lst):
                cell = _Cell(tc, table)
                row_cells.append(
                    CellText(
                        table_index=table_index,
                        row_index=row_index,
                        col_index=col_index,
                        text=clean_cell_text(cell.text),
                        highlighted=is_highlighted_cell(tc),
                    )
                )
            rows.append(row_cells)
    return rows


def matrix_multiply(a: Sequence[float], b: Sequence[float]) -> tuple[float, ...]:
    a0, a1, a2, a3, a4, a5 = a
    b0, b1, b2, b3, b4, b5 = b
    return (
        a0 * b0 + a2 * b1,
        a1 * b0 + a3 * b1,
        a0 * b2 + a2 * b3,
        a1 * b2 + a3 * b3,
        a0 * b4 + a2 * b5 + a4,
        a1 * b4 + a3 * b5 + a5,
    )


def transform_point(matrix: Sequence[float], x: float, y: float) -> tuple[float, float]:
    a, b, c, d, e, f = matrix
    return a * x + c * y + e, b * x + d * y + f


def point_arg(value) -> float:
    return float(value.as_numeric() if hasattr(value, "as_numeric") else value)


def extract_pdf_line_segments(page) -> tuple[list[tuple[float, float, float]], list[tuple[float, float, float]]]:
    """Return horizontal (y, x0, x1) and vertical (x, y0, y1) vector lines."""
    stream = ContentStream(page.get_contents(), page.pdf)
    ctm_stack: list[tuple[float, ...]] = []
    ctm: tuple[float, ...] = (1, 0, 0, 1, 0, 0)
    current: tuple[float, float] | None = None
    horizontals: list[tuple[float, float, float]] = []
    verticals: list[tuple[float, float, float]] = []

    def add_segment(p0: tuple[float, float], p1: tuple[float, float]) -> None:
        x0, y0 = p0
        x1, y1 = p1
        if abs(y0 - y1) <= 0.75 and abs(x0 - x1) >= 4:
            y = (y0 + y1) / 2
            horizontals.append((y, min(x0, x1), max(x0, x1)))
        elif abs(x0 - x1) <= 0.75 and abs(y0 - y1) >= 4:
            x = (x0 + x1) / 2
            verticals.append((x, min(y0, y1), max(y0, y1)))

    for operands, operator in stream.operations:
        op = operator.decode("latin1") if isinstance(operator, bytes) else operator
        if op == "q":
            ctm_stack.append(ctm)
        elif op == "Q":
            ctm = ctm_stack.pop() if ctm_stack else (1, 0, 0, 1, 0, 0)
        elif op == "cm":
            local = tuple(point_arg(v) for v in operands[:6])
            ctm = matrix_multiply(ctm, local)
        elif op == "m":
            current = transform_point(ctm, point_arg(operands[0]), point_arg(operands[1]))
        elif op == "l" and current is not None:
            next_point = transform_point(ctm, point_arg(operands[0]), point_arg(operands[1]))
            add_segment(current, next_point)
            current = next_point
        elif op == "re":
            x, y, w, h = (point_arg(v) for v in operands[:4])
            p0 = transform_point(ctm, x, y)
            p1 = transform_point(ctm, x + w, y)
            p2 = transform_point(ctm, x + w, y + h)
            p3 = transform_point(ctm, x, y + h)
            add_segment(p0, p1)
            add_segment(p1, p2)
            add_segment(p2, p3)
            add_segment(p3, p0)
    return horizontals, verticals


def cluster(values: Iterable[float], tolerance: float = 2.0) -> list[float]:
    sorted_values = sorted(values)
    groups: list[list[float]] = []
    for value in sorted_values:
        if not groups or abs(value - groups[-1][-1]) > tolerance:
            groups.append([value])
        else:
            groups[-1].append(value)
    return [sum(group) / len(group) for group in groups]


def covers(segments: Sequence[tuple[float, float, float]], coord: float, a: float, b: float, tolerance: float = 2.5) -> bool:
    want0, want1 = min(a, b), max(a, b)
    for segment_coord, seg0, seg1 in segments:
        if abs(segment_coord - coord) <= tolerance and seg0 <= want0 + tolerance and seg1 >= want1 - tolerance:
            return True
    return False


def detect_pdf_cells(pdf_path: Path) -> list[Rect]:
    reader = PdfReader(str(pdf_path))
    all_rects: list[Rect] = []
    for page_index, page in enumerate(reader.pages):
        horizontals, verticals = extract_pdf_line_segments(page)
        xs = cluster(x for x, _, _ in verticals)
        ys = cluster(y for y, _, _ in horizontals)
        page_rects: list[Rect] = []
        y_coords = list(reversed(ys))
        for y_top, y_bottom in zip(y_coords, y_coords[1:]):
            if abs(y_top - y_bottom) < 5:
                continue
            for x_left, x_right in zip(xs, xs[1:]):
                if abs(x_right - x_left) < 5:
                    continue
                if (
                    covers(horizontals, y_top, x_left, x_right)
                    and covers(horizontals, y_bottom, x_left, x_right)
                    and covers(verticals, x_left, y_bottom, y_top)
                    and covers(verticals, x_right, y_bottom, y_top)
                ):
                    page_rects.append(Rect(page_index, x_left, y_bottom, x_right, y_top))
        all_rects.extend(page_rects)
    clip_rects = detect_pdf_clip_rect_cells(pdf_path)
    if len(clip_rects) > len(all_rects):
        return clip_rects
    return all_rects


def rect_contains(outer: Rect, inner: Rect, tolerance: float = 0.5) -> bool:
    outer_area = outer.width * outer.height
    inner_area = inner.width * inner.height
    return (
        outer.page_index == inner.page_index
        and outer.x0 <= inner.x0 + tolerance
        and outer.y0 <= inner.y0 + tolerance
        and outer.x1 >= inner.x1 - tolerance
        and outer.y1 >= inner.y1 - tolerance
        and outer_area > inner_area + 1
    )


def detect_pdf_clip_rect_cells(pdf_path: Path) -> list[Rect]:
    """Detect table cells from repeated PDF clipping rectangles.

    Some Word-exported PDFs store the table grid as an image but still emit
    clipping rectangles for each cell's text area. Keeping the outer rectangles
    and dropping nested text-run rectangles gives us stable cell boxes.
    """
    reader = PdfReader(str(pdf_path))
    result: list[Rect] = []
    for page_index, page in enumerate(reader.pages):
        stream = ContentStream(page.get_contents(), page.pdf)
        unique: list[Rect] = []
        seen: set[tuple[float, float, float, float]] = set()
        for operands, operator in stream.operations:
            op = operator.decode("latin1") if isinstance(operator, bytes) else operator
            if op != "re" or len(operands) < 4:
                continue
            x, y, w, h = (point_arg(v) for v in operands[:4])
            if w < 8 or h < 8:
                continue
            rect = Rect(page_index, x, y, x + w, y + h)
            key = (round(rect.x0, 2), round(rect.y0, 2), round(rect.x1, 2), round(rect.y1, 2))
            if key not in seen:
                seen.add(key)
                unique.append(rect)
        outer_rects = [rect for rect in unique if not any(rect_contains(other, rect) for other in unique)]
        result.extend(sorted(outer_rects, key=lambda rect: (rect.page_index, -rect.y1, rect.x0)))
    return result


def group_pdf_rows(rects: Sequence[Rect], tolerance: float = 2.0) -> list[list[Rect]]:
    rows: list[list[Rect]] = []
    for rect in sorted(rects, key=lambda item: (-item.y1, item.x0)):
        if rows and abs(rows[-1][0].y1 - rect.y1) <= tolerance:
            rows[-1].append(rect)
        else:
            rows.append([rect])
    for row in rows:
        row.sort(key=lambda item: item.x0)
    return rows


def union_rect(rects: Sequence[Rect]) -> Rect:
    return Rect(
        rects[0].page_index,
        min(rect.x0 for rect in rects),
        min(rect.y0 for rect in rects),
        max(rect.x1 for rect in rects),
        max(rect.y1 for rect in rects),
    )


def synthesize_five_column_row(row: Sequence[Rect]) -> list[Rect]:
    """Fill missing five-day columns from the template's repeated column grid."""
    if not row:
        return []
    page_index = row[0].page_index
    y0 = min(rect.y0 for rect in row)
    y1 = max(rect.y1 for rect in row)
    columns = [(22.08, 171.12), (171.6, 320.76), (321.36, 470.4), (470.88, 620.04), (620.52, 773.04)]
    return [Rect(page_index, x0, y0, x1, y1) for x0, x1 in columns]


def map_docx_rows_to_pdf_rects(docx_rows: Sequence[Sequence[CellText]], pdf_rects: Sequence[Rect]) -> list[tuple[CellText, Rect]]:
    pdf_rows = group_pdf_rows(pdf_rects)
    # Drop the footer-only row that sits near the bottom-right of this template.
    pdf_rows = [row for row in pdf_rows if not (len(row) == 1 and row[0].x0 > 600 and row[0].y1 < 50)]

    pairs: list[tuple[CellText, Rect]] = []
    for doc_row, pdf_row in zip(docx_rows, pdf_rows):
        working_pdf_row = list(pdf_row)
        if len(doc_row) > 1 and len(working_pdf_row) == len(doc_row) + 1:
            # The first visual row includes a title cell outside the DOCX table.
            working_pdf_row = working_pdf_row[1:]
        if len(doc_row) == 1 and len(working_pdf_row) > 1:
            if doc_row[0].highlighted:
                pairs.append((doc_row[0], working_pdf_row[0]))
            else:
                pairs.append((doc_row[0], union_rect(working_pdf_row)))
            continue
        if len(doc_row) == 5 and len(working_pdf_row) != 5:
            working_pdf_row = synthesize_five_column_row(working_pdf_row)
        for cell, rect in zip(doc_row, working_pdf_row):
            pairs.append((cell, rect))
    return pairs


def twips_to_points(value: int | None) -> float | None:
    return None if value is None else value / DXA_PER_POINT


def docx_geometry_fallback(docx_path: Path, pdf_path: Path) -> list[Rect]:
    """Approximate simple table geometry from DOCX XML.

    This fallback is intentionally conservative and is best for documents where
    tables begin near the top margin and are not mixed with complex flow content.
    """
    with zipfile.ZipFile(docx_path) as zf:
        document_xml = etree.fromstring(zf.read("word/document.xml"))
    reader = PdfReader(str(pdf_path))
    page = reader.pages[0]
    page_height = float(page.mediabox.height)

    section = document_xml.find(".//w:sectPr", WORD_NS)
    margin = section.find("w:pgMar", WORD_NS) if section is not None else None
    left_margin = twips_to_points(int(margin.get(f"{{{WORD_NS['w']}}}left"))) if margin is not None else 72
    top_margin = twips_to_points(int(margin.get(f"{{{WORD_NS['w']}}}top"))) if margin is not None else 72

    rects: list[Rect] = []
    cursor_y = page_height - (top_margin or 72)
    for tbl in document_xml.findall(".//w:tbl", WORD_NS):
        grid_cols = [
            int(col.get(f"{{{WORD_NS['w']}}}w"))
            for col in tbl.findall("w:tblGrid/w:gridCol", WORD_NS)
            if col.get(f"{{{WORD_NS['w']}}}w")
        ]
        if not grid_cols:
            continue
        col_widths = [w / DXA_PER_POINT for w in grid_cols]
        rows = tbl.findall("w:tr", WORD_NS)
        row_heights: list[float] = []
        for row in rows:
            height_el = row.find("w:trPr/w:trHeight", WORD_NS)
            height = None
            if height_el is not None and height_el.get(f"{{{WORD_NS['w']}}}val"):
                height = int(height_el.get(f"{{{WORD_NS['w']}}}val")) / DXA_PER_POINT
            row_heights.append(max(20.0, height or 24.0))

        y_top = cursor_y
        for row_index, row in enumerate(rows):
            y_bottom = y_top - row_heights[row_index]
            x = left_margin or 72
            for width in col_widths:
                rects.append(Rect(0, x, y_bottom, x + width, y_top))
                x += width
            y_top = y_bottom
        cursor_y = y_top - 12
    return rects


def load_layout_json(path: Path) -> list[Rect]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rects: list[Rect] = []
    for item in data["cells"]:
        rects.append(
            Rect(
                page_index=int(item.get("page", 0)),
                x0=float(item["x0"]),
                y0=float(item["y0"]),
                x1=float(item["x1"]),
                y1=float(item["y1"]),
            )
        )
    return rects


def pdf_text_width(text: str, font_size: float) -> float:
    """Approximate Helvetica text width in PDF points.

    This avoids a ReportLab dependency while staying conservative enough for
    table-cell wrapping. Wide glyphs count a bit more; narrow glyphs count less.
    """
    width_units = 0.0
    narrow = set(".,:;!|'ijlI[]() ")
    wide = set("MW@#%&")
    for char in text:
        if char in narrow:
            width_units += 0.28
        elif char in wide:
            width_units += 0.85
        else:
            width_units += 0.52
    return width_units * font_size


def pdf_literal(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", normalize_word_text(text))
    encoded = text.encode("cp1252", errors="replace")
    parts: list[str] = []
    for byte in encoded:
        if byte in (40, 41, 92) or byte < 32 or byte > 126:
            parts.append(f"\\{byte:03o}")
        else:
            parts.append(chr(byte))
    return "(" + "".join(parts) + ")"


def wrap_text(text: str, font_name: str, font_size: float, max_width: float) -> list[str]:
    wrapped: list[str] = []
    for raw_line in text.splitlines() or [""]:
        words = raw_line.split()
        if not words:
            wrapped.append("")
            continue
        line = words[0]
        for word in words[1:]:
            candidate = f"{line} {word}"
            if pdf_text_width(candidate, font_size) <= max_width:
                line = candidate
            else:
                wrapped.append(line)
                line = word
        wrapped.append(line)
    return wrapped


def fit_text(text: str, rect: Rect, font_name: str, max_font: float, min_font: float, padding: float) -> tuple[float, list[str]]:
    usable_width = max(1, rect.width - 2 * padding)
    usable_height = max(1, rect.height - 2 * padding)
    size = max_font
    while size >= min_font:
        lines = wrap_text(text, font_name, size, usable_width)
        line_height = size * 1.18
        if len(lines) * line_height <= usable_height:
            return size, lines
        size -= 0.5
    lines = wrap_text(text, font_name, min_font, usable_width)
    max_lines = max(1, int(usable_height // (min_font * 1.18)))
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        if lines:
            while lines[-1] and pdf_text_width(lines[-1] + "...", min_font) > usable_width:
                lines[-1] = lines[-1][:-1]
            lines[-1] = (lines[-1] + "...") if lines[-1] else "..."
    return min_font, lines


def ensure_text_font(page, writer: PdfWriter) -> None:
    resources = page.get("/Resources")
    if resources is None:
        resources = DictionaryObject()
        page[NameObject("/Resources")] = resources
    else:
        resources = resources.get_object()

    fonts = resources.get("/Font")
    if fonts is None:
        fonts = DictionaryObject()
        resources[NameObject("/Font")] = fonts
    else:
        fonts = fonts.get_object()

    if NameObject("/FTH") not in fonts:
        fonts[NameObject("/FTH")] = writer._add_object(
            DictionaryObject(
                {
                    NameObject("/Type"): NameObject("/Font"),
                    NameObject("/Subtype"): NameObject("/Type1"),
                    NameObject("/BaseFont"): NameObject("/Helvetica"),
                    NameObject("/Encoding"): NameObject("/WinAnsiEncoding"),
                }
            )
        )


def flatten_content_items(contents) -> list[object]:
    if contents is None:
        return []
    target = contents.get_object() if hasattr(contents, "get_object") else contents
    if isinstance(target, ArrayObject):
        flat: list[object] = []
        for item in target:
            flat.extend(flatten_content_items(item))
        return flat
    return [contents]


def stream_has_table_app_overlay(stream_obj) -> bool:
    try:
        data = stream_obj.get_object().get_data()
    except Exception:
        return False
    return OVERLAY_BEGIN.encode("ascii") in data and OVERLAY_END.encode("ascii") in data


def strip_previous_overlays(page) -> None:
    contents = page.get("/Contents")
    flat = flatten_content_items(contents)
    if not flat:
        return
    kept = []
    for item in flat:
        if not stream_has_table_app_overlay(item):
            kept.append(item)
    if not kept:
        if "/Contents" in page:
            del page["/Contents"]
    elif len(kept) == 1:
        page[NameObject("/Contents")] = kept[0]
    else:
        page[NameObject("/Contents")] = ArrayObject(kept)


def normalize_page_contents(page) -> None:
    contents = page.get("/Contents")
    if contents is None:
        return
    flat = flatten_content_items(contents)
    if not flat:
        return
    page[NameObject("/Contents")] = ArrayObject(flat)


def make_stream_ref(writer: PdfWriter, commands: str):
    stream = DecodedStreamObject()
    stream.set_data(commands.encode("latin-1", errors="replace"))
    return writer._add_object(stream)


def isolate_existing_page_contents(page, writer: PdfWriter) -> None:
    """Wrap original content in q/Q so our overlay starts with a clean state."""
    contents = page.get("/Contents")
    flat = flatten_content_items(contents)
    if not flat:
        return
    page[NameObject("/Contents")] = ArrayObject(
        [make_stream_ref(writer, "q\n"), *flat, make_stream_ref(writer, "\nQ\n")]
    )


def append_content_stream(page, commands: str, writer: PdfWriter) -> None:
    stream_ref = make_stream_ref(writer, commands)
    contents = page.get("/Contents")
    if contents is None:
        page[NameObject("/Contents")] = stream_ref
    elif isinstance(contents, ArrayObject):
        contents.append(stream_ref)
    else:
        page[NameObject("/Contents")] = ArrayObject([contents, stream_ref])


def draw_text_into_page(page, items: list[tuple[Rect, str]], args, writer: PdfWriter) -> None:
    if not items:
        return
    ensure_text_font(page, writer)
    commands: list[str] = [f"{OVERLAY_BEGIN}\n"]
    for rect, text in items:
        if not text:
            continue
        if args.cover_existing:
            commands.append(
                f"q 1 1 1 rg {rect.x0 + 0.5:.2f} {rect.y0 + 0.5:.2f} "
                f"{max(0, rect.width - 1):.2f} {max(0, rect.height - 1):.2f} re f Q\n"
            )
        size, lines = fit_text(text, rect, args.font, args.font_size, args.min_font_size, args.padding)
        line_height = size * 1.18
        total_height = len(lines) * line_height
        y = rect.y0 + (rect.height + total_height) / 2 - size
        for line in lines:
            commands.append(
                f"q BT /FTH {size:.2f} Tf 0 Tr 0 0 0 rg "
                f"{rect.x0 + args.padding:.2f} {y:.2f} Td {pdf_literal(line)} Tj ET Q\n"
            )
            y -= line_height
    commands.append(f"{OVERLAY_END}\n")
    append_content_stream(page, "".join(commands), writer)


def write_filled_pdf(pdf_path: Path, output_path: Path, cells: Sequence[CellText], rects: Sequence[Rect], args) -> None:
    reader = PdfReader(str(pdf_path))
    pairs = list(zip(cells, rects))
    if len(pairs) < len(cells):
        raise RuntimeError(f"Only mapped {len(pairs)} PDF cells for {len(cells)} DOCX cells.")

    page_rects: dict[int, list[tuple[Rect, str]]] = {}
    for cell, rect in pairs:
        page_rects.setdefault(rect.page_index, []).append((rect, cell.text))

    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    for index, page in enumerate(writer.pages):
        strip_previous_overlays(page)
        isolate_existing_page_contents(page, writer)
        draw_text_into_page(page, page_rects.get(index, []), args, writer)
    with output_path.open("wb") as fh:
        writer.write(fh)


def validate_output_pdf(input_pdf: Path, output_pdf: Path, cells: Sequence[CellText]) -> None:
    if not output_pdf.exists():
        raise RuntimeError("The updated PDF was not created.")
    if output_pdf.stat().st_size < 500:
        raise RuntimeError("The updated PDF is suspiciously small, so the original was left unchanged.")

    source_reader = PdfReader(str(input_pdf))
    output_reader = PdfReader(str(output_pdf))
    if len(output_reader.pages) != len(source_reader.pages):
        raise RuntimeError(
            f"The updated PDF has {len(output_reader.pages)} pages, but the original has {len(source_reader.pages)}."
        )

    for index, page in enumerate(output_reader.pages):
        if float(page.mediabox.width) <= 0 or float(page.mediabox.height) <= 0:
            raise RuntimeError(f"The updated PDF page {index + 1} has invalid dimensions.")

    expected_words = []
    for cell in cells:
        expected_words.extend(re.findall(r"[A-Za-z0-9]{3,}", cell.text)[:2])
        if len(expected_words) >= 5:
            break
    if expected_words:
        output_text = "\n".join((page.extract_text() or "") for page in output_reader.pages)
        matches = sum(1 for word in expected_words if word in output_text)
        if matches == 0:
            raise RuntimeError("The updated PDF did not contain any copied DOCX text, so the original was left unchanged.")


def next_backup_path(pdf_path: Path) -> Path:
    backup_path = pdf_path.with_name(f"{pdf_path.stem}.backup{pdf_path.suffix}")
    if not backup_path.exists():
        return backup_path
    for index in range(2, 1000):
        numbered = pdf_path.with_name(f"{pdf_path.stem}.backup-{index}{pdf_path.suffix}")
        if not numbered.exists():
            return numbered
    raise RuntimeError(f"Could not find an available backup name for {pdf_path}")


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("docx", type=Path, help="Source DOCX containing the table text.")
    parser.add_argument("pdf", type=Path, help="Target PDF with matching table cells.")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Optional output PDF path. By default, the provided PDF is updated in place.",
    )
    parser.add_argument("--no-backup", action="store_true", help="Do not create a backup when updating the provided PDF in place.")
    parser.add_argument("--layout-json", type=Path, help="Optional exact cell rectangles JSON.")
    parser.add_argument("--fallback-docx-geometry", action="store_true", help="Use approximate DOCX geometry if PDF cell detection fails.")
    parser.add_argument("--font", default="Helvetica", help="PDF font name.")
    parser.add_argument("--font-size", type=float, default=10.0, help="Starting font size.")
    parser.add_argument("--min-font-size", type=float, default=6.0, help="Smallest allowed font size.")
    parser.add_argument("--padding", type=float, default=3.0, help="Cell text padding in PDF points.")
    parser.add_argument("--cover-existing", action="store_true", help="White out each cell interior before drawing text.")
    parser.add_argument("--all-cells", action="store_true", help="Paste every DOCX table cell instead of only highlighted cells.")
    parser.add_argument("--report-json", type=Path, help="Optional run report path.")
    return parser.parse_args(argv)


def transfer_text(args: argparse.Namespace) -> dict[str, object]:
    docx_path = args.docx.resolve()
    pdf_path = args.pdf.resolve()
    output_path = (args.output.resolve() if args.output else pdf_path)
    in_place = output_path == pdf_path

    if not docx_path.exists():
        raise FileNotFoundError(docx_path)
    if not pdf_path.exists():
        raise FileNotFoundError(pdf_path)
    if output_path == docx_path:
        raise ValueError("Output path must not overwrite the DOCX input file.")

    docx_rows = extract_docx_cell_rows(docx_path)
    cells = [cell for row in docx_rows for cell in row]
    if args.layout_json:
        rects = load_layout_json(args.layout_json)
        method = "layout-json"
    else:
        rects = detect_pdf_cells(pdf_path)
        method = "pdf-detected-cells"
        if len(rects) < len(cells) and args.fallback_docx_geometry:
            rects = docx_geometry_fallback(docx_path, pdf_path)
            method = "docx-geometry-fallback"
        elif rects:
            pairs = map_docx_rows_to_pdf_rects(docx_rows, rects)
            if not args.all_cells:
                pairs = [(cell, rect) for cell, rect in pairs if cell.highlighted and cell.text]
            cells = [cell for cell, _ in pairs]
            rects = [rect for _, rect in pairs]
            method = "pdf-row-mapped-cells"

    write_path = output_path
    backup_path = None
    if in_place:
        if not args.no_backup:
            backup_path = next_backup_path(pdf_path)
            shutil.copy2(pdf_path, backup_path)
        write_path = pdf_path.with_name(f".{pdf_path.stem}.table-app-tmp{pdf_path.suffix}")

    write_filled_pdf(pdf_path, write_path, cells, rects, args)
    validate_output_pdf(pdf_path, write_path, cells)
    if in_place:
        shutil.move(str(write_path), str(pdf_path))

    report = {
        "docx": str(docx_path),
        "pdf": str(pdf_path),
        "output": str(output_path),
        "updated_in_place": in_place,
        "backup": str(backup_path) if backup_path else None,
        "method": method,
        "docx_cells": len(cells),
        "pdf_cells_used": min(len(cells), len(rects)),
        "pdf_cells_detected": len(rects),
    }
    return report


def launch_gui() -> int:
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox, ttk
    except Exception:
        return launch_windows_forms_gui()

    try:
        root = tk.Tk()
    except Exception:
        return launch_windows_forms_gui()
    root.title("DOCX Table Text to PDF")
    root.geometry("640x310")
    root.minsize(580, 300)

    docx_var = tk.StringVar()
    pdf_var = tk.StringVar()
    status_var = tk.StringVar(value="Select a filled DOCX and the PDF to update.")
    fallback_var = tk.BooleanVar(value=True)
    cover_var = tk.BooleanVar(value=False)

    def choose_docx() -> None:
        path = filedialog.askopenfilename(
            title="Select filled DOCX",
            filetypes=[("Word documents", "*.docx"), ("All files", "*.*")],
        )
        if path:
            docx_var.set(path)

    def choose_pdf() -> None:
        path = filedialog.askopenfilename(
            title="Select PDF to update",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
        )
        if path:
            pdf_var.set(path)

    def set_busy(is_busy: bool) -> None:
        state = "disabled" if is_busy else "normal"
        run_button.configure(state=state)
        docx_button.configure(state=state)
        pdf_button.configure(state=state)

    def run_transfer() -> None:
        docx_text = docx_var.get().strip()
        pdf_text = pdf_var.get().strip()
        if not docx_text or not pdf_text:
            messagebox.showerror("Missing files", "Please select both a filled DOCX and a PDF.")
            return

        args = argparse.Namespace(
            docx=Path(docx_text),
            pdf=Path(pdf_text),
            output=None,
            no_backup=False,
            layout_json=None,
            fallback_docx_geometry=fallback_var.get(),
            font="Helvetica",
            font_size=10.0,
            min_font_size=6.0,
            padding=3.0,
            cover_existing=cover_var.get(),
            all_cells=False,
            report_json=None,
        )

        def worker() -> None:
            try:
                report = transfer_text(args)
            except Exception as exc:
                root.after(0, lambda: show_error(exc))
                return
            root.after(0, lambda: show_success(report))

        set_busy(True)
        status_var.set("Copying DOCX table text into the PDF...")
        threading.Thread(target=worker, daemon=True).start()

    def restore_backup() -> None:
        pdf_text = pdf_var.get().strip()
        if not pdf_text:
            messagebox.showerror("Missing PDF", "Select the PDF first so I can find its backup.")
            return
        pdf_path = Path(pdf_text)
        backups = sorted(
            pdf_path.parent.glob(f"{pdf_path.stem}.backup*.pdf"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        if not backups:
            messagebox.showerror("No backup found", f"No backup PDF was found beside:\n{pdf_path}")
            return
        backup = backups[0]
        if not messagebox.askyesno("Restore backup", f"Restore this backup over the selected PDF?\n\n{backup}"):
            return
        shutil.copy2(backup, pdf_path)
        status_var.set("Backup restored.")
        messagebox.showinfo("Backup restored", f"Restored:\n{backup}")

    def show_error(exc: Exception) -> None:
        set_busy(False)
        status_var.set("Transfer failed.")
        messagebox.showerror("Transfer failed", str(exc))

    def show_success(report: dict[str, object]) -> None:
        set_busy(False)
        backup = report.get("backup")
        status_var.set("Done. The selected PDF was updated.")
        details = [
            "The selected PDF was updated in place.",
            f"Cells copied: {report.get('pdf_cells_used')} of {report.get('docx_cells')}",
        ]
        if backup:
            details.append(f"Backup created:\n{backup}")
        messagebox.showinfo("Transfer complete", "\n\n".join(details))

    outer = ttk.Frame(root, padding=18)
    outer.pack(fill="both", expand=True)
    outer.columnconfigure(1, weight=1)

    ttk.Label(outer, text="Filled DOCX").grid(row=0, column=0, sticky="w", pady=(0, 6))
    ttk.Entry(outer, textvariable=docx_var).grid(row=0, column=1, sticky="ew", padx=(10, 8), pady=(0, 6))
    docx_button = ttk.Button(outer, text="Browse...", command=choose_docx)
    docx_button.grid(row=0, column=2, pady=(0, 6))

    ttk.Label(outer, text="PDF to update").grid(row=1, column=0, sticky="w", pady=6)
    ttk.Entry(outer, textvariable=pdf_var).grid(row=1, column=1, sticky="ew", padx=(10, 8), pady=6)
    pdf_button = ttk.Button(outer, text="Browse...", command=choose_pdf)
    pdf_button.grid(row=1, column=2, pady=6)

    ttk.Checkbutton(
        outer,
        text="Use approximate DOCX layout if PDF table lines are not detected",
        variable=fallback_var,
    ).grid(row=2, column=1, columnspan=2, sticky="w", pady=(16, 4))

    ttk.Checkbutton(
        outer,
        text="Cover existing cell text before pasting",
        variable=cover_var,
    ).grid(row=3, column=1, columnspan=2, sticky="w", pady=4)

    run_button = ttk.Button(outer, text="Copy Text Into PDF", command=run_transfer)
    run_button.grid(row=4, column=1, sticky="e", pady=(22, 12))

    ttk.Button(outer, text="Restore Backup", command=restore_backup).grid(row=4, column=2, sticky="e", pady=(22, 12))

    ttk.Label(outer, textvariable=status_var, foreground="#444").grid(
        row=5, column=0, columnspan=3, sticky="ew", pady=(8, 0)
    )

    root.mainloop()
    return 0


def powershell_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def build_windows_forms_script(script_path: Path) -> str:
    script = str(script_path)
    return rf'''
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$scriptPath = {powershell_quote(script)}

$form = New-Object System.Windows.Forms.Form
$form.Text = "Lesson Plan Copier"
$form.Size = New-Object System.Drawing.Size(680, 330)
$form.MinimumSize = New-Object System.Drawing.Size(620, 330)
$form.StartPosition = "CenterScreen"
$form.Font = New-Object System.Drawing.Font("Segoe UI", 10)

$title = New-Object System.Windows.Forms.Label
$title.Text = "Lesson Plan Copier"
$title.Font = New-Object System.Drawing.Font("Segoe UI", 18, [System.Drawing.FontStyle]::Bold)
$title.AutoSize = $true
$title.Location = New-Object System.Drawing.Point(20, 18)
$form.Controls.Add($title)

$subtitle = New-Object System.Windows.Forms.Label
$subtitle.Text = "Copy highlighted cells from a filled DOCX into the matching PDF."
$subtitle.AutoSize = $true
$subtitle.ForeColor = [System.Drawing.Color]::FromArgb(75, 85, 99)
$subtitle.Location = New-Object System.Drawing.Point(22, 58)
$form.Controls.Add($subtitle)

function Add-FileRow($labelText, $top, $filter) {{
    $label = New-Object System.Windows.Forms.Label
    $label.Text = $labelText
    $label.AutoSize = $true
    $label.Location = New-Object System.Drawing.Point(24, $top)
    $form.Controls.Add($label)

    $box = New-Object System.Windows.Forms.TextBox
    $box.Location = New-Object System.Drawing.Point(135, ($top - 4))
    $box.Size = New-Object System.Drawing.Size(410, 28)
    $form.Controls.Add($box)

    $button = New-Object System.Windows.Forms.Button
    $button.Text = "Browse..."
    $button.Location = New-Object System.Drawing.Point(555, ($top - 5))
    $button.Size = New-Object System.Drawing.Size(90, 30)
    $button.Add_Click({{
        $dialog = New-Object System.Windows.Forms.OpenFileDialog
        $dialog.Filter = $filter
        if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {{
            $box.Text = $dialog.FileName
        }}
    }})
    $form.Controls.Add($button)
    return $box
}}

$docxBox = Add-FileRow "Filled DOCX" 102 "Word documents (*.docx)|*.docx|All files (*.*)|*.*"
$pdfBox = Add-FileRow "PDF to update" 145 "PDF files (*.pdf)|*.pdf|All files (*.*)|*.*"

$coverBox = New-Object System.Windows.Forms.CheckBox
$coverBox.Text = "Cover existing cell text before pasting"
$coverBox.AutoSize = $true
$coverBox.Location = New-Object System.Drawing.Point(135, 185)
$coverBox.Checked = $false
$form.Controls.Add($coverBox)

$status = New-Object System.Windows.Forms.Label
$status.Text = "Select both files, then click Copy Text Into PDF."
$status.AutoSize = $true
$status.ForeColor = [System.Drawing.Color]::FromArgb(75, 85, 99)
$status.Location = New-Object System.Drawing.Point(24, 254)
$form.Controls.Add($status)

$runButton = New-Object System.Windows.Forms.Button
$runButton.Text = "Copy Text Into PDF"
$runButton.Location = New-Object System.Drawing.Point(385, 218)
$runButton.Size = New-Object System.Drawing.Size(160, 34)
$form.Controls.Add($runButton)

$restoreButton = New-Object System.Windows.Forms.Button
$restoreButton.Text = "Restore Backup"
$restoreButton.Location = New-Object System.Drawing.Point(555, 218)
$restoreButton.Size = New-Object System.Drawing.Size(110, 34)
$restoreButton.Add_Click({{
    if (-not $pdfBox.Text) {{
        [System.Windows.Forms.MessageBox]::Show("Select the PDF first so I can find its backup.", "Missing PDF", "OK", "Error") | Out-Null
        return
    }}
    $pdf = Get-Item -LiteralPath $pdfBox.Text -ErrorAction SilentlyContinue
    if (-not $pdf) {{
        [System.Windows.Forms.MessageBox]::Show("The selected PDF does not exist.", "Missing PDF", "OK", "Error") | Out-Null
        return
    }}
    $pattern = "$($pdf.BaseName).backup*.pdf"
    $backup = Get-ChildItem -LiteralPath $pdf.DirectoryName -Filter $pattern -File | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $backup) {{
        [System.Windows.Forms.MessageBox]::Show("No backup PDF was found beside the selected PDF.", "No backup found", "OK", "Error") | Out-Null
        return
    }}
    $answer = [System.Windows.Forms.MessageBox]::Show("Restore this backup over the selected PDF?`n`n$($backup.FullName)", "Restore backup", "YesNo", "Question")
    if ($answer -eq [System.Windows.Forms.DialogResult]::Yes) {{
        Copy-Item -LiteralPath $backup.FullName -Destination $pdf.FullName -Force
        [System.Windows.Forms.MessageBox]::Show("Backup restored.", "Lesson Plan Copier", "OK", "Information") | Out-Null
        $status.Text = "Backup restored."
    }}
}})
$form.Controls.Add($restoreButton)

$runButton.Add_Click({{
    if (-not (Test-Path -LiteralPath $docxBox.Text) -or -not (Test-Path -LiteralPath $pdfBox.Text)) {{
        return
    }}
    $runButton.Enabled = $false
    $restoreButton.Enabled = $false
    try {{
        $argList = @($scriptPath, $docxBox.Text, $pdfBox.Text)
        if ($coverBox.Checked) {{ $argList += "--cover-existing" }}
        $output = & $scriptPath $docxBox.Text $pdfBox.Text 2>&1
        if ($LASTEXITCODE -ne 0) {{ throw ($output | Out-String) }}
        $status.Text = "Done. The selected PDF was updated."
        [System.Windows.Forms.MessageBox]::Show("The selected PDF was updated. A backup was created beside it.", "Transfer complete", "OK", "Information") | Out-Null
    }} catch {{
        $status.Text = "Transfer failed."
        [System.Windows.Forms.MessageBox]::Show("Transfer failed:`n`n$($_.Exception.Message)", "Lesson Plan Copier", "OK", "Error") | Out-Null
    }} finally {{
        $runButton.Enabled = $true
        $restoreButton.Enabled = $true
    }}
}})

[void]$form.ShowDialog()
'''


def launch_windows_forms_gui() -> int:
    script_path = Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve()
    ps_script = build_windows_forms_script(script_path)
    completed = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            ps_script,
        ],
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return completed.returncode


def windows_message(title: str, message: str, flags: int = 0) -> int:
    return ctypes.windll.user32.MessageBoxW(None, message, title, flags)


def windows_open_file(title: str, filter_text: str) -> str | None:
    class OPENFILENAMEW(ctypes.Structure):
        _fields_ = [
            ("lStructSize", ctypes.c_uint32),
            ("hwndOwner", ctypes.c_void_p),
            ("hInstance", ctypes.c_void_p),
            ("lpstrFilter", ctypes.c_wchar_p),
            ("lpstrCustomFilter", ctypes.c_wchar_p),
            ("nMaxCustFilter", ctypes.c_uint32),
            ("nFilterIndex", ctypes.c_uint32),
            ("lpstrFile", ctypes.c_wchar_p),
            ("nMaxFile", ctypes.c_uint32),
            ("lpstrFileTitle", ctypes.c_wchar_p),
            ("nMaxFileTitle", ctypes.c_uint32),
            ("lpstrInitialDir", ctypes.c_wchar_p),
            ("lpstrTitle", ctypes.c_wchar_p),
            ("Flags", ctypes.c_uint32),
            ("nFileOffset", ctypes.c_uint16),
            ("nFileExtension", ctypes.c_uint16),
            ("lpstrDefExt", ctypes.c_wchar_p),
            ("lCustData", ctypes.c_void_p),
            ("lpfnHook", ctypes.c_void_p),
            ("lpTemplateName", ctypes.c_wchar_p),
            ("pvReserved", ctypes.c_void_p),
            ("dwReserved", ctypes.c_uint32),
            ("FlagsEx", ctypes.c_uint32),
        ]

    buffer = ctypes.create_unicode_buffer(32768)
    ofn = OPENFILENAMEW()
    ofn.lStructSize = ctypes.sizeof(OPENFILENAMEW)
    ofn.lpstrFilter = filter_text
    ofn.lpstrFile = ctypes.cast(buffer, ctypes.c_wchar_p)
    ofn.nMaxFile = len(buffer)
    ofn.lpstrTitle = title
    ofn.Flags = 0x00001000 | 0x00000800 | 0x00000004
    ok = ctypes.windll.comdlg32.GetOpenFileNameW(ctypes.byref(ofn))
    return buffer.value if ok else None


def launch_windows_dialog_flow() -> int:
    docx = windows_open_file("Select filled DOCX", "Word documents\0*.docx\0All files\0*.*\0\0")
    if not docx:
        return 1
    pdf = windows_open_file("Select PDF to update", "PDF files\0*.pdf\0All files\0*.*\0\0")
    if not pdf:
        return 1
    args = argparse.Namespace(
        docx=Path(docx),
        pdf=Path(pdf),
        output=None,
        no_backup=False,
        layout_json=None,
        fallback_docx_geometry=True,
        font="Helvetica",
        font_size=10.0,
        min_font_size=6.0,
        padding=3.0,
        cover_existing=False,
        all_cells=False,
        report_json=None,
    )
    try:
        report = transfer_text(args)
    except Exception as exc:
        windows_message("Lesson Plan Copier", f"Transfer failed:\n\n{exc}", 0x10)
        return 1
    backup = report.get("backup")
    message = f"Done. Updated:\n{report.get('output')}"
    if backup:
        message += f"\n\nBackup created:\n{backup}"
    windows_message("Lesson Plan Copier", message, 0x40)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    actual_argv = list(sys.argv[1:] if argv is None else argv)
    if not actual_argv:
        return launch_gui()

    args = parse_args(actual_argv)
    report = transfer_text(args)
    if args.report_json:
        args.report_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
