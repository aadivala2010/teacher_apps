from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageOps, ImageSequence


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
GRID_CELL_ASPECT = 3 / 2  # width:height

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


def _grid_cell_boxes(
    page_size: tuple[int, int], margin: int, gap: int, cols: int, rows: int, aspect: float
) -> list[tuple[int, int, int, int]]:
    """Largest uniform cols x rows grid of `aspect` (w:h) cells that fits the page, centered
    on whichever axis has leftover room."""
    page_width, page_height = page_size
    avail_width = page_width - 2 * margin
    avail_height = page_height - 2 * margin

    cell_width = (avail_width - (cols - 1) * gap) / cols
    cell_height = cell_width / aspect
    if rows * cell_height + (rows - 1) * gap > avail_height:
        cell_height = (avail_height - (rows - 1) * gap) / rows
        cell_width = cell_height * aspect

    total_width = cols * cell_width + (cols - 1) * gap
    total_height = rows * cell_height + (rows - 1) * gap
    origin_x = margin + (avail_width - total_width) / 2
    origin_y = margin + (avail_height - total_height) / 2

    boxes = []
    for row in range(rows):
        for col in range(cols):
            x = origin_x + col * (cell_width + gap)
            y = origin_y + row * (cell_height + gap)
            boxes.append((int(x), int(y), int(cell_width), int(cell_height)))
    return boxes


def build_grid_3x4_pdf(slot_files: list[dict[str, object] | None]) -> bytes:
    if not any(slot_files):
        raise ValueError("Upload at least one supported image.")

    boxes = _grid_cell_boxes(PAGE_SIZE_A4, MARGIN, GAP, GRID_COLS, GRID_ROWS, GRID_CELL_ASPECT)
    page = Image.new("RGB", PAGE_SIZE_A4, BACKGROUND)
    for slot, file in zip(boxes, slot_files):
        if not file:
            continue
        x, y, cell_width, cell_height = slot
        image = _prepare_image(bytes(file.get("content") or b""), (cell_width, cell_height))
        x += (cell_width - image.width) // 2
        y += (cell_height - image.height) // 2
        page.paste(image, (x, y))

    output = BytesIO()
    page.save(output, format="PDF", resolution=300.0)
    return output.getvalue()
