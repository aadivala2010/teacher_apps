from __future__ import annotations

from io import BytesIO
from pathlib import Path

from pptx import Presentation
from pptx.util import Pt


TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "activity_descriptor.pptx"

LINKS_TEXT = (
    "Language and Literacy\n"
    "Wellness\n"
    "Creative Expression\n"
    "Mathematics\n"
    "Social Emotional"
)


def _set_text_box(shape, text: str) -> None:
    """Replace text in a shape's text frame, preserving first-run formatting."""
    tf = shape.text_frame

    # Grab formatting from the first run of the first paragraph if it exists
    first_run = None
    if tf.paragraphs and tf.paragraphs[0].runs:
        first_run = tf.paragraphs[0].runs[0]

    # Clear all existing paragraphs except the first
    for para in tf.paragraphs[1:]:
        p_elem = para._p
        p_elem.getparent().remove(p_elem)

    lines = text.split("\n")
    first_para = tf.paragraphs[0]

    # Clear runs from the first paragraph
    for run in first_para.runs:
        r_elem = run._r
        r_elem.getparent().remove(r_elem)

    # Add the first line to the existing paragraph
    run0 = first_para.add_run()
    run0.text = lines[0]
    if first_run:
        run0.font.bold = first_run.font.bold
        run0.font.size = first_run.font.size

    # Add subsequent lines as new paragraphs
    from pptx.oxml.ns import qn
    from lxml import etree
    from copy import deepcopy

    first_p_elem = first_para._p
    parent = first_p_elem.getparent()

    for line in lines[1:]:
        new_p = deepcopy(first_p_elem)
        # Remove all runs from the copied element and add fresh one
        for r in new_p.findall(qn("a:r")):
            new_p.remove(r)
        run_elem = deepcopy(first_p_elem.findall(qn("a:r"))[0]) if first_p_elem.findall(qn("a:r")) else etree.SubElement(new_p, qn("a:r"))
        # Set the text
        t_elem = run_elem.find(qn("a:t"))
        if t_elem is None:
            t_elem = etree.SubElement(run_elem, qn("a:t"))
        t_elem.text = line
        new_p.append(run_elem)
        parent.append(new_p)


def build_activity_descriptor_pptx(payload: dict) -> tuple[bytes, str]:
    date_str = str(payload.get("date", ""))
    activities = payload.get("activities", [])
    skills = payload.get("skills", [])

    prs = Presentation(str(TEMPLATE_PATH))
    slide = prs.slides[0]

    for shape in slide.shapes:
        if not shape.has_text_frame:
            continue
        name = shape.name
        if name == "Text Box 18":
            _set_text_box(shape, date_str)
        elif name == "Text Box 19":
            text = "\n".join(a for a in activities if a)
            _set_text_box(shape, text)
        elif name == "Text Box 20":
            text = "\n".join(s for s in skills if s)
            _set_text_box(shape, text)
        # Text Box 21 (Links) is intentionally left unchanged

    buf = BytesIO()
    prs.save(buf)
    buf.seek(0)
    filename = f"activity_descriptor_{date_str or 'export'}.pptx"
    return buf.read(), filename
