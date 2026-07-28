from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageDraw, ImageOps, ImageSequence


SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".tif", ".tiff"}
PAGE_SIZE = (2550, 3300)
MARGIN = 120
GAP = 80
BACKGROUND = "white"
MAX_UPLOAD_BYTES = 1_048_576
MAX_DIMENSION = 1920

PAGE_SIZE_A4 = (2481, 3508)  # 210mm x 297mm at 300dpi
GRID_COLS = 3
GRID_ROWS = 4
GRID_SLOTS = GRID_COLS * GRID_ROWS
GRID_DPI = 200  # 200dpi keeps the PDF under Vercel's 4.5MB response limit
GRID_PAGE_SIZE = (1654, 2339)  # 210mm x 297mm at 200dpi
GRID_MARGIN = 63  # ~8mm
GRID_BORDER = 2

TWO_PER_PAGE_MARGIN = 60
TWO_PER_PAGE_GAP = 9  # ~3 CSS px (96dpi) scaled to this canvas's 300dpi


def compress_image_bytes(content: bytes, max_bytes: int = MAX_UPLOAD_BYTES) -> bytes:
    try:
        with Image.open(BytesIO(content)) as img:
            if img.format and img.format.upper() in ("GIF", "SVG"):
                return content
            if len(content) <= max_bytes:
                return content
            image = _first_frame(img)
            image = ImageOps.exif_transpose(image)
            if image.mode not in {"RGB", "L"}:
                image = image.convert("RGBA")
                background = Image.new("RGBA", image.size, BACKGROUND)
                background.alpha_composite(image)
                image = background.convert("RGB")
            else:
                image = image.convert("RGB")
            w, h = image.size
            if w > MAX_DIMENSION or h > MAX_DIMENSION:
                scale = min(MAX_DIMENSION / w, MAX_DIMENSION / h)
                w, h = int(w * scale), int(h * scale)
                image = image.resize((w, h), Image.Resampling.LANCZOS)
            quality = 85
            output = BytesIO()
            while quality > 10:
                output.seek(0)
                output.truncate(0)
                image.save(output, format="JPEG", quality=quality)
                if output.tell() <= max_bytes:
                    break
                quality -= 10
            return output.getvalue()
    except Exception:
        return content


def is_supported_image(filename: str) -> bool:
    lower = filename.lower()
    return any(lower.endswith(extension) for extension in SUPPORTED_EXTENSIONS)


def _first_frame(image: Image.Image) -> Image.Image:
    try:
        frame = next(ImageSequence.Iterator(image))
        return frame.copy()
    except Exception:
        return image.copy()


def _prepare_image(content: bytes, cell_size: tuple[int, int]) -> Image.Image:
    with Image.open(BytesIO(content)) as source:
        image = _first_frame(source)
        image = ImageOps.exif_transpose(image)
        if image.mode not in {"RGB", "L"}:
            image = image.convert("RGBA")
            background = Image.new("RGBA", image.size, BACKGROUND)
            background.alpha_composite(image)
            image = background.convert("RGB")
        else:
            image = image.convert("RGB")
    return ImageOps.contain(image, cell_size, method=Image.Resampling.LANCZOS)


def build_grid_pdf(files: list[dict[str, object]]) -> bytes:
    images = [file for file in files if is_supported_image(str(file.get("filename") or ""))]
    if not images:
        raise ValueError("Upload at least one supported image.")

    page_width, page_height = PAGE_SIZE
    cell_width = (page_width - (MARGIN * 2) - GAP) // 2
    cell_height = (page_height - (MARGIN * 2) - GAP) // 2
    positions = [
        (MARGIN, MARGIN),
        (MARGIN + cell_width + GAP, MARGIN),
        (MARGIN, MARGIN + cell_height + GAP),
        (MARGIN + cell_width + GAP, MARGIN + cell_height + GAP),
    ]

    pages: list[Image.Image] = []
    for start in range(0, len(images), 4):
        page = Image.new("RGB", PAGE_SIZE, BACKGROUND)
        for index, file in enumerate(images[start : start + 4]):
            image = _prepare_image(bytes(file.get("content") or b""), (cell_width, cell_height))
            x, y = positions[index]
            x += (cell_width - image.width) // 2
            y += (cell_height - image.height) // 2
            page.paste(image, (x, y))
        pages.append(page)

    output = BytesIO()
    pages[0].save(output, format="PDF", save_all=True, append_images=pages[1:], resolution=300.0)
    return output.getvalue()


def build_two_per_page_pdf(files: list[dict[str, object]], stacked: bool) -> bytes:
    images = [file for file in files if is_supported_image(str(file.get("filename") or ""))]
    if not images:
        raise ValueError("Upload at least one supported image.")

    page_width, page_height = PAGE_SIZE_A4
    avail_width = page_width - 2 * TWO_PER_PAGE_MARGIN
    avail_height = page_height - 2 * TWO_PER_PAGE_MARGIN
    if stacked:
        cell_width = avail_width
        cell_height = (avail_height - TWO_PER_PAGE_GAP) // 2
        positions = [
            (TWO_PER_PAGE_MARGIN, TWO_PER_PAGE_MARGIN),
            (TWO_PER_PAGE_MARGIN, TWO_PER_PAGE_MARGIN + cell_height + TWO_PER_PAGE_GAP),
        ]
    else:
        cell_width = (avail_width - TWO_PER_PAGE_GAP) // 2
        cell_height = avail_height
        positions = [
            (TWO_PER_PAGE_MARGIN, TWO_PER_PAGE_MARGIN),
            (TWO_PER_PAGE_MARGIN + cell_width + TWO_PER_PAGE_GAP, TWO_PER_PAGE_MARGIN),
        ]

    pages: list[Image.Image] = []
    for start in range(0, len(images), 2):
        page = Image.new("RGB", PAGE_SIZE_A4, BACKGROUND)
        for index, file in enumerate(images[start : start + 2]):
            image = _prepare_image(bytes(file.get("content") or b""), (cell_width, cell_height))
            x, y = positions[index]
            x += (cell_width - image.width) // 2
            y += (cell_height - image.height) // 2
            page.paste(image, (x, y))
        pages.append(page)

    output = BytesIO()
    pages[0].save(output, format="PDF", save_all=True, append_images=pages[1:], resolution=300.0)
    return output.getvalue()


def build_grid_3x4_pdf(slot_files: list[dict[str, object] | None]) -> bytes:
    """One A4 portrait page: 3 columns x 4 rows of bordered cells filling the page,
    each photo scaled to fit inside its own cell."""
    if not any(slot_files):
        raise ValueError("Upload at least one supported image.")

    slots = (list(slot_files) + [None] * GRID_SLOTS)[:GRID_SLOTS]
    page_width, page_height = GRID_PAGE_SIZE
    cell_width = (page_width - 2 * GRID_MARGIN) / GRID_COLS
    cell_height = (page_height - 2 * GRID_MARGIN) / GRID_ROWS

    page = Image.new("RGB", GRID_PAGE_SIZE, BACKGROUND)
    draw = ImageDraw.Draw(page)
    for index, file in enumerate(slots):
        col, row = index % GRID_COLS, index // GRID_COLS
        left = int(GRID_MARGIN + col * cell_width)
        top = int(GRID_MARGIN + row * cell_height)
        right = int(GRID_MARGIN + (col + 1) * cell_width)
        bottom = int(GRID_MARGIN + (row + 1) * cell_height)
        draw.rectangle((left, top, right, bottom), outline="black", width=GRID_BORDER)
        if not file:
            continue
        inner = (right - left - 2 * GRID_BORDER, bottom - top - 2 * GRID_BORDER)
        image = _prepare_image(bytes(file.get("content") or b""), inner)
        page.paste(
            image,
            (
                left + GRID_BORDER + (inner[0] - image.width) // 2,
                top + GRID_BORDER + (inner[1] - image.height) // 2,
            ),
        )

    output = BytesIO()
    page.save(output, format="PDF", resolution=float(GRID_DPI), quality=80)
    return output.getvalue()
