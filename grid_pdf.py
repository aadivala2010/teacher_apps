from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageOps, ImageSequence


SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".tif", ".tiff"}
PAGE_SIZE = (2550, 3300)
MARGIN = 120
GAP = 80
BACKGROUND = "white"


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
